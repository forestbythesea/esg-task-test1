import json
import re
from typing import Any

from openai import OpenAI

from app.core.config import get_settings
from app.models.schemas import Confidence, QuestionAnswer, RiskScore, RiskScoreList, Source, Summary
from app.services.guardrails import sanitize_for_prompt
from app.services.observability import TraceRecorder, TraceResult
from app.services.openai_status import get_openai_client, require_valid_openai_model
from app.services.retrieval import quote_from_chunk


def rough_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def source_from_chunk(chunk: dict) -> Source:
    return Source(
        document_name=chunk["document_name"],
        page=int(chunk["page"]),
        quote=quote_from_chunk(chunk["text"]),
    )


def format_context(chunks: list[dict], limit: int = 1200) -> str:
    blocks = []
    for index, chunk in enumerate(chunks, start=1):
        header = (
            f"[source_id={index}; document_name={chunk['document_name']}; "
            f"page={int(chunk['page'])}]"
        )
        blocks.append(f"{header}\n{sanitize_for_prompt(chunk['text'], limit)}")
    return "\n\n".join(blocks)


DIMENSION_SIGNALS = {
    "Environmental": ["climate", "emission", "biodiversity", "pollution", "waste", "water"],
    "Social": ["employee", "safety", "community", "customer", "training", "diversity"],
    "Governance": ["board", "audit", "compliance", "ethics", "policy", "governance"],
    "Security/Data": ["data", "security", "privacy", "cyber", "information", "gdpr"],
    "Energy": ["energy", "renewable", "efficiency", "electricity", "fuel", "transition"],
    "Risk Management": ["risk", "control", "mitigation", "management", "assessment", "internal audit"],
}

COMMITMENT_SIGNALS = [
    "target",
    "commit",
    "policy",
    "approved",
    "monitor",
    "measure",
    "reduce",
    "improve",
    "ensure",
    "responsible",
    "management",
    "control",
]

WEAKNESS_SIGNALS = ["not found", "limited", "missing", "risk", "exposure", "uncertain", "challenge"]


def clean_sentence(text: str) -> str:
    sentence = re.sub(r"\s+", " ", text).strip(" -•")
    noise_markers = [
        "Translation of the company",
        "RISK MANAGEMENT PROCESS",
        "RISK MANAGEMENT AND INTERNAL CONTROLS",
        "ENEFIT EESTI ENERGIA ANNUAL REPORT",
        "S E C O N D P A R T Y O P I N I O N",
    ]
    for marker in noise_markers:
        if marker in sentence:
            sentence = sentence.split(marker, 1)[0].strip()
    sentence = re.sub(r",? as detailed in the \d+\s*$", ".", sentence, flags=re.I)
    return sentence


def relevant_sentences(chunks: list[dict], query: str, limit: int = 3) -> list[str]:
    query_terms = {
        term.lower()
        for term in re.findall(r"[a-zA-Z][a-zA-Z\-]{3,}", query)
        if term.lower() not in {"what", "main", "company", "commitment", "commitments"}
    }
    candidates: list[tuple[float, str]] = []
    for chunk in chunks:
        for raw_sentence in re.split(r"(?<=[.!?])\s+", chunk["text"]):
            sentence = clean_sentence(raw_sentence)
            if len(sentence.split()) < 8:
                continue
            if not sentence.endswith((".", "!", "?")) and len(sentence.split()) > 34:
                continue
            sentence_lower = sentence.lower()
            if "translation of the company" in sentence_lower:
                continue
            overlap = sum(1 for term in query_terms if term in sentence_lower)
            signal = sum(1 for term in COMMITMENT_SIGNALS if term in sentence_lower)
            chunk_score = float(chunk.get("score", 0))
            score = overlap * 4 + signal + min(chunk_score, 3)
            if score > 0:
                candidates.append((score, sentence))
    candidates.sort(key=lambda item: item[0], reverse=True)
    selected: list[str] = []
    seen: set[str] = set()
    for _, sentence in candidates:
        key = sentence[:90].lower()
        if key not in seen:
            selected.append(sentence)
            seen.add(key)
        if len(selected) == limit:
            break
    return selected


def synthesize_evidence_answer(question: str, chunks: list[dict]) -> str:
    sentences = relevant_sentences(chunks, question, limit=3)
    if not sentences:
        return f"The retrieved evidence is relevant but thin: {quote_from_chunk(chunks[0]['text'], 320)}"
    if "risk management" in question.lower():
        lead = "The report frames risk management as a governed control process"
    elif "energy" in question.lower():
        lead = "The report links energy management to operational efficiency and transition actions"
    elif "data security" in question.lower() or "security" in question.lower():
        lead = "The report treats data and security as a control area"
    elif "purpose" in question.lower() or "activities" in question.lower():
        lead = "The report describes the company through its operating activities and strategic role"
    else:
        lead = "The report evidence points to a focused set of commitments"
    return f"{lead}: " + " ".join(sentences)


def score_dimension(dimension: str, chunks: list[dict]) -> tuple[int, Confidence, str]:
    if not chunks:
        return 32, "low", f"No meaningful source evidence was retrieved for {dimension.lower()} risk controls."
    text = " ".join(chunk["text"] for chunk in chunks[:4]).lower()
    avg_relevance = sum(float(chunk.get("score", 0)) for chunk in chunks[:4]) / min(len(chunks), 4)
    signal_hits = sum(1 for term in DIMENSION_SIGNALS[dimension] if term in text)
    commitment_hits = sum(1 for term in COMMITMENT_SIGNALS if term in text)
    weakness_hits = sum(1 for term in WEAKNESS_SIGNALS if term in text)
    pages = len({chunk["page"] for chunk in chunks[:5]})
    raw = 38 + min(avg_relevance * 9, 22) + signal_hits * 5 + min(commitment_hits, 7) * 3 + pages * 2
    raw -= min(weakness_hits, 4) * 3
    score = max(25, min(94, round(raw)))
    confidence: Confidence = "high" if score >= 78 and len(chunks) >= 3 else "medium"
    if score < 55 or len(chunks) < 2:
        confidence = "low"
    rationale = (
        f"{dimension} score reflects {signal_hits} topic signals, {min(commitment_hits, 7)} "
        f"commitment/control signals, and evidence across {pages} page(s)."
    )
    if weakness_hits:
        rationale += f" It is moderated for {weakness_hits} risk or uncertainty signal(s)."
    return score, confidence, rationale


class LLMService:
    def __init__(self) -> None:
        self.settings = get_settings()
        require_valid_openai_model()
        self.client: OpenAI = get_openai_client()

    def _responses_json(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        route: str,
        step: str,
        reasoning_effort: str,
        run_id: str | None = None,
        user_id: int | None = None,
    ) -> tuple[dict[str, Any], TraceResult]:
        recorder = TraceRecorder(
            route=route,
            step=step,
            model=self.settings.openai_model,
            reasoning_effort=reasoning_effort,
            run_id=run_id,
            user_id=user_id,
        )
        try:
            response = self.client.responses.create(
                model=self.settings.openai_model,
                input=prompt,
                reasoning={"effort": reasoning_effort},
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "structured_esg_response",
                        "schema": schema,
                        "strict": True,
                    }
                },
            )
            output = json.loads(response.output_text)
            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "input_tokens", rough_tokens(prompt)) if usage else rough_tokens(prompt)
            completion_tokens = getattr(usage, "output_tokens", rough_tokens(response.output_text)) if usage else rough_tokens(response.output_text)
            trace = recorder.finish(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
            return output, trace
        except Exception as exc:  # pragma: no cover - external API path
            trace = recorder.finish(
                prompt_tokens=rough_tokens(prompt),
                completion_tokens=0,
                status="error",
                error=str(exc),
            )
            raise

    def summarize(
        self, company_name: str, chunks: list[dict], run_id: str | None = None
    ) -> tuple[Summary, TraceResult]:
        prompt_context = format_context(chunks[:6])
        prompt = (
            f"Create a short ESG/annual-report summary for {company_name}. "
            "Cover main business, ESG topics, and strategic themes. "
            "For every source, copy the exact document_name, page, and a short exact quote from context.\n\n"
            f"{prompt_context}"
        )
        schema = Summary.model_json_schema()
        data, trace = self._responses_json(
            prompt=prompt,
            schema=schema,
            route="/api/ingest/run",
            step="summary",
            reasoning_effort="medium",
            run_id=run_id,
        )
        return Summary.model_validate(data), trace

    def answer_question(
        self,
        company_name: str,
        question: str,
        chunks: list[dict],
        run_id: str | None = None,
    ) -> tuple[QuestionAnswer, TraceResult]:
        prompt_context = format_context(chunks)
        prompt = (
            f"Answer using only context for {company_name}. If unsupported, return not_found. "
            "For every source, copy the exact document_name, page, and a short exact quote from context. "
            f"Question: {question}\n\n{prompt_context}"
        )
        schema = QuestionAnswer.model_json_schema()
        data, trace = self._responses_json(
            prompt=prompt,
            schema=schema,
            route="/api/ingest/run",
            step="predefined_question",
            reasoning_effort="medium",
            run_id=run_id,
        )
        if not chunks:
            return QuestionAnswer(
                question=question,
                status="not_found",
                answer=None,
                confidence="low",
                sources=[],
                missing_information="No relevant source text was retrieved for this question.",
            ), trace
        return QuestionAnswer.model_validate(data), trace

    def score_risks(
        self, company_name: str, chunks_by_dimension: dict[str, list[dict]], run_id: str | None = None
    ) -> tuple[list[RiskScore], TraceResult]:
        prompt_context = json.dumps(
            {
                dimension: [
                    {
                        "document_name": c["document_name"],
                        "page": c["page"],
                        "quote": quote_from_chunk(c["text"], 320),
                    }
                    for c in chunks[:3]
                ]
                for dimension, chunks in chunks_by_dimension.items()
            },
            indent=2,
        )
        prompt = (
            f"Create ESG risk scores for {company_name}. Score 0 means severe unmanaged risk, "
            "100 means strong controls and evidence. Use only cited context. "
            "For every source quote, use an exact quote from the supplied context snippets.\n\n"
            f"{prompt_context}"
        )
        schema = RiskScoreList.model_json_schema()
        data, trace = self._responses_json(
            prompt=prompt,
            schema=schema,
            route="/api/ingest/run",
            step="risk_scoring",
            reasoning_effort="medium",
            run_id=run_id,
        )
        return RiskScoreList.model_validate(data).scores, trace
