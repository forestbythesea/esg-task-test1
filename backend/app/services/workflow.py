import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import UploadFile

from app.core.config import DATA_DIR, get_settings
from app.core.db import get_conn
from app.models.schemas import CompanyResult, GeneratedResult
from app.services.evals import evaluate_company, evaluate_result
from app.services.guardrails import detect_prompt_injection
from app.services.llm import LLMService, source_from_chunk
from app.services.openai_status import require_valid_openai_model
from app.services.pdf import PDFValidationError, chunk_pages, extract_pages, validate_pdf_file
from app.services.reports import ALLOWED_REPORT_URLS, PREDEFINED_QUESTIONS, REPORTS, RISK_DIMENSIONS, ReportDefinition
from app.services.retrieval import search_chunks


REPORTS_DIR = DATA_DIR / "reports"
GENERATED_DIR = DATA_DIR / "generated"
UPLOADS_DIR = DATA_DIR / "uploads"


def ensure_report_rows() -> None:
    with get_conn() as conn:
        for report in REPORTS:
            conn.execute(
                """
                INSERT OR IGNORE INTO companies
                  (id, name, report_year, file_name, source_url, source_type, status, updated_at)
                VALUES (?, ?, ?, ?, ?, 'baseline', 'ready', CURRENT_TIMESTAMP)
                """,
                (
                    report.company_id,
                    report.company_name,
                    report.report_year,
                    report.file_name,
                    report.source_url,
                ),
            )


def download_report(report: ReportDefinition) -> Path:
    if report.source_url not in ALLOWED_REPORT_URLS:
        raise ValueError("Report URL is not allowlisted")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    target = REPORTS_DIR / report.file_name
    if target.exists() and target.stat().st_size > 0:
        return target
    with httpx.Client(follow_redirects=True, timeout=45) as client:
        response = client.get(report.source_url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "pdf" not in content_type.lower():
            raise ValueError(f"Unexpected content type for {report.file_name}: {content_type}")
        target.write_bytes(response.content)
    return target


def report_path(report: ReportDefinition) -> Path:
    if report.source_type == "upload":
        if not report.local_path:
            raise ValueError("Uploaded report is missing local_path")
        return Path(report.local_path)
    return download_report(report)


def reset_company_chunks(company_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM chunks WHERE company_id = ?", (company_id,))


def persist_chunks(report: ReportDefinition, chunks: list[dict]) -> None:
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO chunks (company_id, document_name, page, text)
            VALUES (?, ?, ?, ?)
            """,
            [(report.company_id, report.file_name, chunk["page"], chunk["text"]) for chunk in chunks],
        )


def load_chunks(company_id: str) -> list[dict]:
    with get_conn() as conn:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT document_name, page, text FROM chunks WHERE company_id = ?",
                (company_id,),
            ).fetchall()
        ]


def generate_company(report: ReportDefinition, run_id: str, llm: LLMService) -> CompanyResult:
    reset_company_chunks(report.company_id)
    path = report_path(report)
    with get_conn() as conn:
        conn.execute(
            "UPDATE companies SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            ("processing", report.company_id),
        )
    pages = extract_pages(path)
    chunks = chunk_pages(pages)
    injection_findings = detect_prompt_injection(" ".join(page["text"] for page in pages[:3]))
    persist_chunks(report, chunks)

    summary_chunks = search_chunks(
        report.company_id,
        "business activities ESG sustainability strategy climate employees governance",
        limit=6,
    ) or load_chunks(report.company_id)[:6]
    summary, _ = llm.summarize(report.company_name, summary_chunks, run_id)
    summary.sources = [source_from_chunk(chunk) for chunk in summary_chunks[:2]]

    answers = []
    for question in PREDEFINED_QUESTIONS:
        retrieved = search_chunks(report.company_id, question, limit=5)
        answer, _ = llm.answer_question(report.company_name, question, retrieved, run_id)
        if answer.status == "answered":
            answer.sources = [source_from_chunk(chunk) for chunk in retrieved[:2]]
            answer.missing_information = None
        else:
            answer.sources = []
        answers.append(answer)

    chunks_by_dimension = {
        dimension: search_chunks(report.company_id, dimension, limit=5)
        for dimension in RISK_DIMENSIONS
    }
    scores, _ = llm.score_risks(report.company_name, chunks_by_dimension, run_id)
    for score in scores:
        score.sources = [
            source_from_chunk(chunk)
            for chunk in chunks_by_dimension.get(score.dimension, [])[:2]
        ]
    result = CompanyResult(
        company_name=report.company_name,
        document={
            "company_id": report.company_id,
            "file_name": report.file_name,
            "report_year": report.report_year,
            "source_url": report.source_url,
            "source_type": report.source_type,
            "document_label": report.document_label,
            "generation_mode": "openai",
            "prompt_injection_findings": injection_findings,
        },
        summary=summary,
        questions=answers,
        risk_scores=scores,
    )
    validation_checks = evaluate_company(result, chunks)
    failed_checks = [check for check in validation_checks if not check["passed"]]
    if failed_checks:
        raise ValueError(f"Generated output failed citation validation: {failed_checks}")
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE companies
            SET summary_json = ?, questions_json = ?, scores_json = ?,
                status = ?, generation_mode = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                result.summary.model_dump_json(),
                json.dumps([a.model_dump(mode="json") for a in result.questions]),
                json.dumps([s.model_dump(mode="json") for s in result.risk_scores]),
                "completed",
                "openai",
                report.company_id,
            ),
        )
    return result


def _start_run(*, target_report_id: str | None, source_type: str | None) -> str:
    run_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO runs (id, status, target_report_id, source_type, generation_mode)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, "running", target_report_id, source_type, "openai"),
        )
    return run_id


def _complete_run(run_id: str, output_path: Path) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE runs SET status = ?, completed_at = CURRENT_TIMESTAMP, output_path = ? WHERE id = ?",
            ("completed", str(output_path), run_id),
        )


def _fail_run(run_id: str, error: Exception, report_id: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE runs SET status = ?, completed_at = CURRENT_TIMESTAMP, error = ? WHERE id = ?",
            ("failed", str(error), run_id),
        )
        if report_id:
            conn.execute(
                "UPDATE companies SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                ("failed", report_id),
            )


def _write_outputs(run_id: str, companies: list[CompanyResult], reports: list[ReportDefinition]) -> dict:
    settings = get_settings()
    generated = GeneratedResult(
        generated_at=datetime.now(timezone.utc).isoformat(),
        model={"provider": "openai", "name": settings.openai_model},
        generation_mode="openai",
        companies=companies,
    )
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = GENERATED_DIR / f"esg-results-{run_id}.json"
    output_path.write_text(generated.model_dump_json(indent=2), encoding="utf-8")
    chunks_by_company = {report.company_id: load_chunks(report.company_id) for report in reports}
    evals = evaluate_result(generated, chunks_by_company)
    eval_path = GENERATED_DIR / f"evals-{run_id}.json"
    eval_path.write_text(json.dumps(evals, indent=2), encoding="utf-8")
    _complete_run(run_id, output_path)
    return {"run_id": run_id, "status": "completed", "output_path": str(output_path), "evals": evals}


def run_ingestion() -> dict:
    require_valid_openai_model()
    ensure_report_rows()
    run_id = _start_run(target_report_id=None, source_type="baseline")
    llm = LLMService()
    try:
        companies = [generate_company(report, run_id, llm) for report in REPORTS]
        return _write_outputs(run_id, companies, REPORTS)
    except Exception as exc:
        _fail_run(run_id, exc)
        raise


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug[:60] or "uploaded-report"


def _safe_pdf_name(filename: str) -> str:
    name = Path(filename).name
    if not name.lower().endswith(".pdf"):
        raise PDFValidationError("Only .pdf files are supported.")
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", name)[:120] or "uploaded.pdf"


def upload_report(
    *,
    company_name: str,
    report_year: str | None,
    document_label: str | None,
    file: UploadFile,
) -> dict:
    settings = get_settings()
    if not company_name.strip():
        raise PDFValidationError("Company name is required.")
    filename = _safe_pdf_name(file.filename or "uploaded.pdf")
    content_type = (file.content_type or "").lower()
    if content_type and "pdf" not in content_type:
        raise PDFValidationError("Uploaded file must have a PDF content type.")
    report_id = f"upload-{_slugify(company_name)}-{uuid.uuid4().hex[:8]}"
    upload_dir = UPLOADS_DIR / report_id
    upload_dir.mkdir(parents=True, exist_ok=False)
    target = upload_dir / filename
    max_bytes = settings.max_upload_mb * 1024 * 1024
    written = 0
    with target.open("wb") as handle:
        while chunk := file.file.read(1024 * 1024):
            written += len(chunk)
            if written > max_bytes:
                target.unlink(missing_ok=True)
                raise PDFValidationError(f"PDF exceeds the size limit of {settings.max_upload_mb} MB.")
            handle.write(chunk)
    validate_pdf_file(target, max_pages=settings.max_upload_pages)
    year = (report_year or "unknown").strip() or "unknown"
    label = (document_label or filename).strip()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO companies (
              id, name, report_year, file_name, source_url, source_type,
              local_path, document_label, status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (report_id, company_name.strip(), year, filename, "", "upload", str(target), label, "uploaded"),
        )
    return {
        "id": report_id,
        "name": company_name.strip(),
        "report_year": year,
        "file_name": filename,
        "source_type": "upload",
        "status": "uploaded",
    }


def report_from_row(row: dict) -> ReportDefinition:
    return ReportDefinition(
        company_id=row["id"],
        company_name=row["name"],
        file_name=row["file_name"],
        report_year=row["report_year"],
        source_url=row["source_url"] or "",
        source_type=row.get("source_type") or "baseline",
        local_path=row.get("local_path"),
        document_label=row.get("document_label"),
    )


def process_report(report_id: str) -> dict:
    require_valid_openai_model()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM companies WHERE id = ?", (report_id,)).fetchone()
    if not row:
        raise ValueError("Report not found.")
    report = report_from_row(dict(row))
    run_id = _start_run(target_report_id=report_id, source_type=report.source_type)
    llm = LLMService()
    try:
        company = generate_company(report, run_id, llm)
        return _write_outputs(run_id, [company], [report])
    except Exception as exc:
        _fail_run(run_id, exc, report_id=report_id)
        raise


def company_from_row(row: dict) -> dict:
    is_openai_generated = row.get("generation_mode") == "openai"
    return {
        "id": row["id"],
        "name": row["name"],
        "report_year": row["report_year"],
        "file_name": row["file_name"],
        "source_url": row["source_url"],
        "source_type": row.get("source_type") or "baseline",
        "document_label": row.get("document_label"),
        "status": row.get("status") or "ready",
        "generation_mode": row.get("generation_mode"),
        "summary": json.loads(row["summary_json"]) if is_openai_generated and row["summary_json"] else None,
        "questions": json.loads(row["questions_json"]) if is_openai_generated and row["questions_json"] else [],
        "risk_scores": json.loads(row["scores_json"]) if is_openai_generated and row["scores_json"] else [],
        "updated_at": row["updated_at"],
    }


def get_companies() -> list[dict]:
    ensure_report_rows()
    with get_conn() as conn:
        return [
            company_from_row(dict(row))
            for row in conn.execute("SELECT * FROM companies ORDER BY name, report_year DESC").fetchall()
        ]


def get_company(company_id: str) -> dict | None:
    ensure_report_rows()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
        return company_from_row(dict(row)) if row else None
