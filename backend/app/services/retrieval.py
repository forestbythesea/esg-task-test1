import math
import re
from collections import Counter

from app.core.db import get_conn


TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z\-]{2,}")
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "are",
    "was",
    "were",
    "company",
    "report",
    "group",
}


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text) if t.lower() not in STOPWORDS]


def score_text(query: str, text: str) -> float:
    query_counts = Counter(tokenize(query))
    text_counts = Counter(tokenize(text))
    if not query_counts or not text_counts:
        return 0.0
    score = 0.0
    for token, q_count in query_counts.items():
        if token in text_counts:
            score += (1 + math.log(q_count)) * (1 + math.log(text_counts[token]))
    return score / math.sqrt(sum(v * v for v in text_counts.values()))


def search_chunks(company_id: str, query: str, limit: int = 5) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT document_name, page, text FROM chunks WHERE company_id = ?",
            (company_id,),
        ).fetchall()
    ranked = [
        {**dict(row), "score": score_text(query, row["text"])}
        for row in rows
        if len(row["text"].split()) >= 25
    ]
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return [item for item in ranked[:limit] if item["score"] > 0]


def quote_from_chunk(text: str, max_chars: int = 280) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rsplit(" ", 1)[0] + "…"
