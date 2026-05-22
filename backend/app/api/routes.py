from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.db import create_session, get_conn
from app.core.security import current_user
from app.models.schemas import ChatRequest, LoginRequest
from app.services.chat import answer_chat
from app.services.openai_status import OpenAIConfigurationError, validate_openai_model
from app.services.pdf import PDFValidationError
from app.services.workflow import (
    get_companies,
    get_company,
    process_report,
    run_ingestion,
    upload_report,
)


router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/config/status")
def config_status() -> dict:
    return validate_openai_model()


@router.post("/auth/login")
def login(payload: LoginRequest) -> dict:
    session = create_session(payload.username)
    if not session:
        raise HTTPException(status_code=401, detail="Unknown demo user")
    return session


@router.get("/me")
def me(user: dict = Depends(current_user)) -> dict:
    return {"user": user}


@router.get("/companies")
def companies(user: dict = Depends(current_user)) -> list[dict]:
    return get_companies()


@router.get("/companies/{company_id}")
def company(company_id: str, user: dict = Depends(current_user)) -> dict:
    found = get_company(company_id)
    if not found:
        raise HTTPException(status_code=404, detail="Company not found")
    return found


@router.post("/ingest/run")
def ingest(user: dict = Depends(current_user)) -> dict:
    if user["role"] not in {"analyst", "admin"}:
        raise HTTPException(status_code=403, detail="Only analysts and admins can run ingestion")
    try:
        return run_ingestion()
    except OpenAIConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reports/upload")
def upload_pdf_report(
    company_name: str = Form(...),
    report_year: str | None = Form(default=None),
    document_label: str | None = Form(default=None),
    file: UploadFile = File(...),
    user: dict = Depends(current_user),
) -> dict:
    if user["role"] not in {"analyst", "admin"}:
        raise HTTPException(status_code=403, detail="Only analysts and admins can upload reports")
    try:
        return upload_report(
            company_name=company_name,
            report_year=report_year,
            document_label=document_label,
            file=file,
        )
    except PDFValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reports/{report_id}/process")
def process_uploaded_report(report_id: str, user: dict = Depends(current_user)) -> dict:
    if user["role"] not in {"analyst", "admin"}:
        raise HTTPException(status_code=403, detail="Only analysts and admins can process reports")
    try:
        return process_report(report_id)
    except OpenAIConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/chat")
def chat(payload: ChatRequest, user: dict = Depends(current_user)) -> dict:
    if not get_company(payload.company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    try:
        return answer_chat(payload.company_id, payload.message, user["id"]).model_dump(mode="json")
    except OpenAIConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs")
def runs(user: dict = Depends(current_user)) -> list[dict]:
    with get_conn() as conn:
        return [
            dict(row)
            for row in conn.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT 25").fetchall()
        ]


@router.get("/runs/{run_id}")
def run_detail(run_id: str, user: dict = Depends(current_user)) -> dict:
    with get_conn() as conn:
        run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        traces = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM traces WHERE run_id = ? ORDER BY created_at ASC",
                (run_id,),
            ).fetchall()
        ]
    return {"run": dict(run), "traces": traces}


@router.get("/observability/runs/{run_id}")
def run_observability(run_id: str, user: dict = Depends(current_user)) -> dict:
    detail = run_detail(run_id, user)
    traces = detail["traces"]
    totals = {
        "prompt_tokens": sum(t["prompt_tokens"] for t in traces),
        "completion_tokens": sum(t["completion_tokens"] for t in traces),
        "total_tokens": sum(t["total_tokens"] for t in traces),
        "estimated_cost_usd": sum(t["estimated_cost_usd"] for t in traces),
        "latency_ms": sum(t["latency_ms"] for t in traces),
    }
    return {"run": detail["run"], "totals": totals, "traces": traces}
