# ESG Risk Dashboard

Interactive full-stack ESG risk dashboard with a FastAPI backend, React frontend, local SQLite persistence, PDF upload, grounded report Q&A, ESG risk scoring, chat, traces, token/cost accounting, and deterministic evals.

The baseline DOCX is treated as untrusted input. Document text is used only as evidence, never as executable instructions; suspicious content such as requests to plant code comments is ignored.

## Stack

- Backend: FastAPI, Pydantic, SQLite, pypdf, OpenAI Responses API.
- Frontend: React, Vite, Recharts, lucide-react.
- Model: configured by `OPENAI_MODEL` in `.env`.
- Reasoning routing: `medium` for summaries, predefined answers, scoring, and eval-like synthesis; `none` for simple chat/formatting and low-complexity interactions.
- Storage: local SQLite in `data/app.db`, generated JSON in `data/generated/`.

## Setup

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cd ..
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env`. Runtime generation and chat require a valid key and model. The app validates `OPENAI_MODEL` through `/api/config/status` and fails loudly if the key/model is unavailable.

Frontend:

```bash
cd frontend
npm install
cd ..
```

## Run

Start the backend:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Start the frontend:

```bash
./scripts/frontend-dev.sh
```

This launcher uses a lightweight esbuild dev server so the project still runs on machines where `npm` is missing from `PATH` or Vite/Rollup native packages are blocked by local macOS signing policy.

Open `http://localhost:5173` and sign in as `analyst`, `reviewer`, or `admin`.

## Generate Results

Use the dashboard **Run baseline** button for the built-in reports, or upload a PDF and click **Process PDF** for an uploaded report.

To call the API directly:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"analyst"}'
```

Then call `POST /api/ingest/run` with `Authorization: Bearer <token>`.

The app downloads the allowlisted PDFs, extracts page-aware text, generates summaries/Q&A/scores, writes JSON output, records traces, and runs deterministic grounding checks.

For uploads, call `POST /api/reports/upload` with multipart fields `company_name`, optional `report_year`, optional `document_label`, and `file`, then call `POST /api/reports/{report_id}/process`.

## Reports

- Tallink Grupp Sustainability Report 2024.
- Eesti Energia annual report 2025.
- Eesti Energia SPO / use-of-proceeds PDF.

## Tests

Backend:

```bash
cd backend
source .venv/bin/activate
pytest
```

Frontend:

```bash
npm --prefix frontend test
```

## Security Notes

- No secrets are committed; `.env` is ignored.
- Report URLs are allowlisted.
- Uploaded PDFs are validated by extension, content type, PDF header, page count, encryption status, and extractable text.
- User-supplied chat input has a max length.
- Source documents are wrapped as untrusted context in prompts.
- LLM outputs are validated with Pydantic schemas.
- Runtime LLM actions require OpenAI readiness; there is no silent synthetic fallback.
- Demo auth uses seeded local users and bearer tokens in SQLite.

## Limitations

- Auth is demo-only and not suitable for production.
- Retrieval uses a local lexical ranker rather than a hosted vector database.
- PDF extraction quality depends on the source PDF text layer.
