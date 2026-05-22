from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.db import init_db
from app.services.workflow import ensure_report_rows


def create_app() -> FastAPI:
    settings = get_settings()
    init_db()
    ensure_report_rows()
    app = FastAPI(title="ESG Risk Dashboard API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(settings.frontend_origin)],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()

