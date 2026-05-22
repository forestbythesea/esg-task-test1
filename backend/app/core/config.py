from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5.4-mini", alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL"
    )
    max_upload_mb: int = Field(default=30, alias="MAX_UPLOAD_MB")
    max_upload_pages: int = Field(default=250, alias="MAX_UPLOAD_PAGES")
    backend_database_url: str = Field(
        default=f"sqlite:///{DATA_DIR / 'app.db'}", alias="BACKEND_DATABASE_URL"
    )
    frontend_origin: AnyHttpUrl | str = Field(
        default="http://localhost:5173", alias="FRONTEND_ORIGIN"
    )

    input_token_price_per_million: float = 0.75
    output_token_price_per_million: float = 4.50

    @property
    def sqlite_path(self) -> Path:
        prefix = "sqlite:///"
        if self.backend_database_url.startswith(prefix):
            path = Path(self.backend_database_url.removeprefix(prefix))
            if not path.is_absolute():
                path = ROOT_DIR / path
            return path.resolve()
        return DATA_DIR / "app.db"


@lru_cache
def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()
