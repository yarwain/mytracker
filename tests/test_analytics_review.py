import json
from types import SimpleNamespace

import pytest

from app.analytics.review import (
    SYSTEM_PROMPT,
    AnalyticsReviewer,
    AnalyticsReviewError,
    MissingApiKeyError,
    parse_review,
)
from app.analytics.snapshot import AnalyticsSnapshotBuilder
from app.config import OPENAI_MODEL_DEFAULT

AS_OF_YEAR = 2026


def test_parse_review_reads_structured_response() -> None:
    review = parse_review(
        json.dumps(
            {
                "headline": "  Protein and training both moved up.  ",
                "observations": [
                    " Average calories were 2000 kcal. ",
                    "Sessions rose by 3.",
                ],
                "suggestions": [
                    {"title": " Keep the pattern ", "detail": " Average protein was 100 g. "},
                    {"title": "Add a rest day", "detail": "Four sessions is a full stretch."},
                    {"title": "Log the quiet days", "detail": "Three nutrition days were logged."},
                ],
            }
        )
    )

    assert review.headline == "Protein and training both moved up."
    assert review.observations == (
        "Average calories were 2000 kcal.",
        "Sessions rose by 3.",
    )
    assert review.suggestions[0].title == "Keep the pattern"
    assert review.suggestions[0].detail == "Average protein was 100 g."
    assert len(review.suggestions) == 3


def test_parse_review_rejects_invalid_payloads() -> None:
    with pytest.raises(AnalyticsReviewError, match="not valid JSON"):
        parse_review("not json")
    with pytest.raises(AnalyticsReviewError, match="empty"):
        parse_review("  ")
    with pytest.raises(AnalyticsReviewError, match="expected format"):
        parse_review(
            json.dumps(
                {
                    "headline": "Short",
                    "observations": ["One", "Two"],
                    "suggestions": [
                        {"title": "Only one", "detail": "Not enough."},
                        {"title": "Second", "detail": "Still short."},
                    ],
                }
            )
        )


def test_reviewer_sends_snapshot_and_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    snapshot = _snapshot()
    client = _Client(_valid_content())
    review = AnalyticsReviewer(client=client).review(snapshot)

    kwargs = client.chat.completions.kwargs
    assert kwargs["model"] == OPENAI_MODEL_DEFAULT
    assert kwargs["messages"][0]["content"] == SYSTEM_PROMPT
    assert "Do not invent" in kwargs["messages"][0]["content"]
    assert "medical advice" in kwargs["messages"][0]["content"]
    assert kwargs["messages"][1]["content"] == snapshot.to_json()
    assert kwargs["response_format"]["json_schema"]["name"] == "analytics_review"
    assert kwargs["response_format"]["json_schema"]["strict"] is True
    assert review.headline == "A steady week."


def test_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reviewer = AnalyticsReviewer()
    assert reviewer.api_key_configured is False
    with pytest.raises(MissingApiKeyError, match="OPENAI_API_KEY"):
        reviewer.review(_snapshot())


def test_injected_client_works_without_an_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reviewer = AnalyticsReviewer(client=_Client(_valid_content()), model="gpt-4.1-mini")
    assert reviewer.api_key_configured is True
    assert reviewer.review(_snapshot()).suggestions[2].title == "Log meals"


def test_api_errors_are_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    timeout_client = _Client(error=TimeoutError("slow"))
    with pytest.raises(AnalyticsReviewError, match="timed out"):
        AnalyticsReviewer(client=timeout_client).review(_snapshot())

    failed_client = _Client(error=RuntimeError("connection reset"))
    with pytest.raises(AnalyticsReviewError, match="connection reset"):
        AnalyticsReviewer(client=failed_client).review(_snapshot())


def _snapshot():
    from datetime import date

    return AnalyticsSnapshotBuilder().build(as_of=date(AS_OF_YEAR, 10, 18))


def _valid_content() -> str:
    return json.dumps(
        {
            "headline": "A steady week.",
            "observations": ["Calories averaged 2000 kcal.", "Steps averaged 9000."],
            "suggestions": [
                {"title": "Hold calories", "detail": "Stay near the current average."},
                {"title": "Keep the sessions", "detail": "Repeat the workouts you logged."},
                {"title": "Log meals", "detail": "Fill the days that have no intake."},
            ],
        }
    )


class _Completions:
    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        message = SimpleNamespace(content=self.content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class _Client:
    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self.chat = SimpleNamespace(completions=_Completions(content, error))
