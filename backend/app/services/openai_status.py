from functools import lru_cache

from openai import OpenAI

from app.core.config import get_settings


class OpenAIConfigurationError(RuntimeError):
    pass


def reasoning_effort_for(step: str) -> str:
    settings = get_settings()
    model = settings.openai_model.lower()
    if step == "chat" and ("gpt-5.1" in model or "gpt-5.2" in model or "gpt-5.4" in model):
        return "none"
    return "medium"


def get_openai_client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise OpenAIConfigurationError("OpenAI API key is required for LLM generation.")
    return OpenAI(api_key=settings.openai_api_key)


@lru_cache(maxsize=1)
def validate_openai_model() -> dict:
    settings = get_settings()
    if not settings.openai_api_key:
        return {
            "openai_configured": False,
            "model": settings.openai_model,
            "model_validated": False,
            "generation_mode": "not_configured",
            "error": "OPENAI_API_KEY is missing.",
        }
    try:
        client = get_openai_client()
        response = client.responses.create(
            model=settings.openai_model,
            input="Return only the word OK.",
            reasoning={"effort": reasoning_effort_for("preflight")},
            max_output_tokens=16,
        )
        text = getattr(response, "output_text", "")
        return {
            "openai_configured": True,
            "model": settings.openai_model,
            "model_validated": True,
            "generation_mode": "openai",
            "preflight_response": text[:40],
            "error": None,
        }
    except Exception as exc:  # pragma: no cover - depends on live OpenAI account
        return {
            "openai_configured": True,
            "model": settings.openai_model,
            "model_validated": False,
            "generation_mode": "invalid_model",
            "error": str(exc),
        }


def require_valid_openai_model() -> dict:
    status = validate_openai_model()
    if not status["openai_configured"]:
        raise OpenAIConfigurationError(status["error"])
    if not status["model_validated"]:
        raise OpenAIConfigurationError(
            f"OpenAI model '{status['model']}' is not available or failed preflight: {status['error']}"
        )
    return status

