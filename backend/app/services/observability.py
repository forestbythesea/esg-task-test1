import time
import uuid
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.db import get_conn


@dataclass
class TraceResult:
    trace_id: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float


class TraceRecorder:
    def __init__(
        self,
        *,
        route: str,
        step: str,
        model: str,
        reasoning_effort: str,
        run_id: str | None = None,
        user_id: int | None = None,
    ) -> None:
        self.trace_id = str(uuid.uuid4())
        self.route = route
        self.step = step
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.run_id = run_id
        self.user_id = user_id
        self.started = time.perf_counter()

    def finish(
        self,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        status: str = "ok",
        error: str | None = None,
    ) -> TraceResult:
        settings = get_settings()
        latency_ms = int((time.perf_counter() - self.started) * 1000)
        total = prompt_tokens + completion_tokens
        cost = (
            prompt_tokens / 1_000_000 * settings.input_token_price_per_million
            + completion_tokens / 1_000_000 * settings.output_token_price_per_million
        )
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO traces (
                  id, run_id, user_id, route, step, model, reasoning_effort,
                  prompt_tokens, completion_tokens, total_tokens,
                  estimated_cost_usd, latency_ms, status, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.trace_id,
                    self.run_id,
                    self.user_id,
                    self.route,
                    self.step,
                    self.model,
                    self.reasoning_effort,
                    prompt_tokens,
                    completion_tokens,
                    total,
                    cost,
                    latency_ms,
                    status,
                    error,
                ),
            )
        return TraceResult(self.trace_id, latency_ms, prompt_tokens, completion_tokens, total, cost)

