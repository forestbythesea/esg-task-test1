from app.models.schemas import CompanyResult, GeneratedResult, QuestionAnswer


def quote_is_grounded(quote: str, chunks: list[dict]) -> bool:
    normalized_quote = " ".join(quote.split()).lower().replace("…", "")
    if len(normalized_quote) < 20:
        return False
    return any(normalized_quote[:80] in " ".join(chunk["text"].split()).lower() for chunk in chunks)


def evaluate_answer(answer: QuestionAnswer, chunks: list[dict]) -> dict:
    if answer.status == "answered":
        has_sources = bool(answer.sources)
        grounded = all(quote_is_grounded(source.quote, chunks) for source in answer.sources)
        return {
            "question": answer.question,
            "passed": has_sources and grounded and bool(answer.answer),
            "checks": {"has_sources": has_sources, "quotes_grounded": grounded},
        }
    return {
        "question": answer.question,
        "passed": answer.answer is None and bool(answer.missing_information),
        "checks": {"no_answer_claim": answer.answer is None, "has_missing_info": bool(answer.missing_information)},
    }


def evaluate_company(company: CompanyResult, chunks: list[dict]) -> list[dict]:
    checks = [evaluate_answer(answer, chunks) for answer in company.questions]
    checks.append(
        {
            "question": "summary_has_grounded_source",
            "passed": bool(company.summary.sources)
            and all(quote_is_grounded(source.quote, chunks) for source in company.summary.sources),
            "checks": {"has_sources": bool(company.summary.sources)},
        }
    )
    checks.append(
        {
            "question": "risk_scores_have_grounded_sources",
            "passed": all(
                score.sources
                and all(quote_is_grounded(source.quote, chunks) for source in score.sources)
                for score in company.risk_scores
            ),
            "checks": {"score_count": len(company.risk_scores)},
        }
    )
    return checks


def evaluate_result(result: GeneratedResult, chunks_by_company: dict[str, list[dict]]) -> list[dict]:
    checks = []
    for company in result.companies:
        company_id = company.document["company_id"]
        checks.extend(evaluate_company(company, chunks_by_company.get(company_id, [])))
    return checks
