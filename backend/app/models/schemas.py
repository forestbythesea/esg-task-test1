from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Confidence = Literal["high", "medium", "low"]
ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh"]


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_name: str
    page: int
    quote: str = Field(min_length=1, max_length=900)


class Summary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    sources: list[Source]


class QuestionAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    status: Literal["answered", "not_found"]
    answer: str | None
    confidence: Confidence
    sources: list[Source]
    missing_information: str | None


class RiskScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: str
    score: int = Field(ge=0, le=100)
    confidence: Confidence
    rationale: str
    sources: list[Source]


class RiskScoreList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scores: list[RiskScore]


class CompanyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str
    document: dict
    summary: Summary
    questions: list[QuestionAnswer]
    risk_scores: list[RiskScore]


class GeneratedResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: str
    model: dict
    generation_mode: Literal["openai"]
    companies: list[CompanyResult]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    confidence: Confidence
    citations: list[Source]
    trace_id: str
    model: str
    reasoning_effort: ReasoningEffort
    token_usage: dict
    latency_ms: int


class UploadReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    report_year: str
    file_name: str
    source_type: Literal["upload"]
    status: str
