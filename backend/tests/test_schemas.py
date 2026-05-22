import pytest
from pydantic import ValidationError

from app.models.schemas import RiskScore, Source


def test_risk_score_bounds() -> None:
    with pytest.raises(ValidationError):
        RiskScore(
            dimension="Energy",
            score=101,
            confidence="high",
            rationale="Too high",
            sources=[Source(document_name="x.pdf", page=1, quote="A sufficiently long quote.")],
        )

