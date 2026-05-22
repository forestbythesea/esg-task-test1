# ESG Risk Dashboard

Interactive ESG risk dashboard with a FastAPI backend, React frontend, local SQLite persistence, PDF upload, grounded OpenAI report analysis, ESG risk scoring, follow-up chat, local traces, token/cost/latency accounting, and deterministic citation evals.

The baseline task DOCX and every processed PDF are treated as untrusted input. Document text is used only as evidence, never as executable instructions.

## Current Status

- Runtime generation is **real OpenAI only**. There is no silent synthetic/offline fallback.
- Local `.env` contains an OpenAI key and `OPENAI_MODEL=gpt-5.4-mini`.
- `/api/config/status` currently validates that model for this API key and reports `generation_mode: openai`.
- Baseline reports have been processed successfully with OpenAI. The API currently returns `completed / openai` results with six risk scores per report.
- Canonical local database path is `data/app.db` from the repo root. Relative `BACKEND_DATABASE_URL` values are resolved from the repo root, even when the backend is started from `backend/`.

## Stack

- Backend: FastAPI, Pydantic, SQLite, pypdf, OpenAI Responses API.
- Frontend: React, Recharts, lucide-react.
- Local dev frontend: custom esbuild server via `./scripts/frontend-dev.sh`.
- Vite/Vitest config remains in `frontend/`, but this Mac/Codex environment had Rollup native package signing issues, so the esbuild launcher is the reliable local path.
- Storage:
  - SQLite: `data/app.db`
  - downloaded baseline PDFs: `data/reports/`
  - uploaded PDFs: `data/uploads/<report_id>/`
  - generated JSON/evals: `data/generated/`

## Environment

Create `.env` from the example:

```bash
cp .env.example .env
```

Required:

```bash
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.4-mini
```

Optional:

```bash
BACKEND_DATABASE_URL=sqlite:///./data/app.db
FRONTEND_ORIGIN=http://localhost:5173
MAX_UPLOAD_MB=30
MAX_UPLOAD_PAGES=250
```

`.env.example` matches the backend default model. The local `.env` can override it; the app validates the configured model before generation.

## Setup

Backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e "backend[dev]"
```

Frontend dependencies are already represented by `frontend/package-lock.json`. If global `npm` is available:

```bash
cd frontend
npm install
cd ..
```

If `npm` is not available, `./scripts/frontend-dev.sh` bootstraps a repo-local npm CLI under `frontend/.local-tools/` when needed.

## Run

Start the backend:

```bash
cd backend
source ../.venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Start the frontend from the repo root:

```bash
./scripts/frontend-dev.sh
```

Open [http://localhost:5173](http://localhost:5173) and sign in as `analyst`, `reviewer`, or `admin`.

## Main Workflow

1. Confirm the OpenAI status banner says OpenAI is connected.
2. Use **Run baseline** to regenerate the built-in reports.
3. Use **Upload PDF** to add a custom report.
4. Select the uploaded report from the dropdown.
5. Click **Process PDF**.
6. Review risk scores, charts, summary, Q&A, exact source quotes, observability, and chat.

Baseline processing can take a minute or more because it makes real model calls for three reports. Uploaded PDFs are processed one report at a time.

Chat is enabled only when the selected report has `status: completed` and `generation_mode: openai`.

## API Overview

Auth:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"analyst"}'
```

Readiness:

```bash
curl http://localhost:8000/api/config/status
```

Baseline processing:

```bash
curl -X POST http://localhost:8000/api/ingest/run \
  -H "Authorization: Bearer <token>"
```

PDF upload:

```bash
curl -X POST http://localhost:8000/api/reports/upload \
  -H "Authorization: Bearer <token>" \
  -F "company_name=Example Company" \
  -F "report_year=2026" \
  -F "document_label=Annual Report" \
  -F "file=@/path/to/report.pdf"
```

Process an uploaded report:

```bash
curl -X POST http://localhost:8000/api/reports/<report_id>/process \
  -H "Authorization: Bearer <token>"
```

## Reports

Built-in baseline reports:

- Tallink Grupp Sustainability Report 2024.
- Eesti Energia annual report 2025.
- Eesti Energia SPO / use-of-proceeds PDF.

Uploaded reports are stored locally and processed through the same extraction, retrieval, OpenAI generation, citation validation, scoring, eval, and trace pipeline.

## Grounding And Validation

- OpenAI structured outputs use strict Pydantic schemas.
- Source text is wrapped as untrusted evidence in prompts.
- Model-written answers and scores are saved only after citation validation.
- Displayed citation quotes are anchored to exact retrieved PDF chunks so grounding checks pass deterministically.
- If a report cannot provide enough evidence for an answer, the output should use `not_found` rather than inventing content.
- Generated JSON includes `generation_mode: "openai"` and model metadata.

## Observability

Local traces are stored in SQLite and exposed in the UI:

- route and workflow step
- model
- reasoning effort
- prompt/completion/total tokens
- estimated cost
- latency
- status and error

No Langfuse or external telemetry service is required.

## Tests And Verification

Backend tests:

```bash
source .venv/bin/activate
pytest backend/tests
ruff check backend/app backend/tests
```

Frontend type check:

```bash
node frontend/node_modules/typescript/bin/tsc -b frontend
```

The current verified state:

- Backend tests: `8 passed`
- Ruff: passed
- Frontend TypeScript: passed
- Live OpenAI config preflight: passed for the local `.env`
- Baseline OpenAI ingestion: completed with citation evals passing

## Security Notes

- `.env` is ignored and must not be committed.
- Baseline report URLs are allowlisted.
- Uploaded PDFs are validated by extension, content type, PDF header, page count, encryption status, file size, and extractable text.
- Filenames are sanitized and stored under generated report IDs.
- User chat input has a max length.
- Runtime LLM actions require OpenAI readiness.
- Demo auth uses local seeded users and bearer tokens in SQLite; it is not production auth.

## Limitations

- Auth is demo-only.
- Retrieval is local lexical search rather than embeddings/vector DB.
- PDF extraction quality depends on the PDF text layer.
- Long baseline runs are synchronous today; a production version should move processing to a background job with progress updates.
- Cost estimates use configured per-token assumptions and should be reviewed against current OpenAI pricing before production use.
