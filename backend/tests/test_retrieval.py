from app.services.retrieval import quote_from_chunk, score_text


def test_score_text_rewards_overlap() -> None:
    assert score_text("energy management risk", "energy management controls") > score_text(
        "energy management risk", "unrelated ferry route"
    )


def test_quote_from_chunk_truncates_cleanly() -> None:
    quote = quote_from_chunk(" ".join(["word"] * 100), max_chars=80)
    assert len(quote) <= 80
    assert quote.endswith("…")

