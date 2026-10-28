"""Ask OpenAI for a written review of an analytics snapshot."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from openai import OpenAI

from app.analytics.snapshot import AnalyticsSnapshot
from app.config import OPENAI_MODEL_DEFAULT

_TIMEOUT_SECONDS = 30.0

SYSTEM_PROMPT = """
You write a personal analytics review for the MyTracker dashboard.
The user message is a JSON snapshot of their own logs for the current window
and the previous window.
Rules:
- Use only numbers that appear in the snapshot. Do not invent measurements,
  workouts, or meals.
- If a value is null, skip that series.
- protein_reference_g_per_kg is a comparison label, not a prescription.
- Do not diagnose, recommend medication or supplements, or give medical advice.
- headline: one sentence on what changed between the windows.
- observations: 2 to 4 short statements that cite snapshot numbers.
- suggestions: 3 to 5 items about nutrition or training. Each has a title and
  one sentence of practical detail.
""".strip()

_REVIEW_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "headline": {"type": "string"},
        "observations": {
            "type": "array",
            "minItems": 2,
            "maxItems": 4,
            "items": {"type": "string"},
        },
        "suggestions": {
            "type": "array",
            "minItems": 3,
            "maxItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "required": ["title", "detail"],
            },
        },
    },
    "required": ["headline", "observations", "suggestions"],
}

REVIEW_RESPONSE_FORMAT: dict = {
    "type": "json_schema",
    "json_schema": {
        "name": "analytics_review",
        "strict": True,
        "schema": _REVIEW_SCHEMA,
    },
}


class AnalyticsReviewError(Exception):
    """The written review could not be produced."""


class MissingApiKeyError(AnalyticsReviewError):
    """OPENAI_API_KEY is not set."""


@dataclass(frozen=True)
class Suggestion:
    """One practical suggestion from the written review."""

    title: str
    detail: str


@dataclass(frozen=True)
class AnalyticsReview:
    """Structured review returned by the model."""

    headline: str
    observations: tuple[str, ...]
    suggestions: tuple[Suggestion, ...]


class AnalyticsReviewer:
    """Call the Chat Completions API with an injectable client."""

    def __init__(
        self,
        *,
        client: object | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._client = client
        self._model = _resolve_model(model)
        self._api_key = _resolve_api_key(api_key)

    @property
    def api_key_configured(self) -> bool:
        """Return whether a review can be requested."""
        return self._client is not None or self._api_key is not None

    def review(self, snapshot: AnalyticsSnapshot) -> AnalyticsReview:
        """Send the snapshot summary and parse the structured response."""
        client = self._resolve_client()
        try:
            completion = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": snapshot.to_json()},
                ],
                response_format=REVIEW_RESPONSE_FORMAT,
            )
        except AnalyticsReviewError:
            raise
        except Exception as exc:
            raise AnalyticsReviewError(_review_error_message(exc)) from exc
        try:
            content = completion.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise AnalyticsReviewError("The review response was empty.") from exc
        return parse_review(content)

    def _resolve_client(self) -> object:
        if self._client is not None:
            return self._client
        if self._api_key is None:
            raise MissingApiKeyError("Set OPENAI_API_KEY to generate a written review.")
        try:
            return OpenAI(api_key=self._api_key, timeout=_TIMEOUT_SECONDS)
        except Exception as exc:
            raise AnalyticsReviewError(_review_error_message(exc)) from exc


def parse_review(content: str | None) -> AnalyticsReview:
    """Parse a model response into a review."""
    if content is None or not content.strip():
        raise AnalyticsReviewError("The review response was empty.")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AnalyticsReviewError("The review response was not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise AnalyticsReviewError("The review response did not match the expected format.")

    headline = payload.get("headline")
    observations = payload.get("observations")
    suggestions = payload.get("suggestions")
    if not isinstance(headline, str) or not headline.strip():
        raise AnalyticsReviewError("The review response did not match the expected format.")
    if (
        not isinstance(observations, list)
        or not 2 <= len(observations) <= 4
        or not all(isinstance(item, str) and item.strip() for item in observations)
    ):
        raise AnalyticsReviewError("The review response did not match the expected format.")
    if not isinstance(suggestions, list) or not 3 <= len(suggestions) <= 5:
        raise AnalyticsReviewError("The review response did not match the expected format.")

    parsed_suggestions: list[Suggestion] = []
    for item in suggestions:
        if not isinstance(item, dict):
            raise AnalyticsReviewError("The review response did not match the expected format.")
        title = item.get("title")
        detail = item.get("detail")
        if (
            not isinstance(title, str)
            or not title.strip()
            or not isinstance(detail, str)
            or not detail.strip()
        ):
            raise AnalyticsReviewError("The review response did not match the expected format.")
        parsed_suggestions.append(Suggestion(title=title.strip(), detail=detail.strip()))

    return AnalyticsReview(
        headline=headline.strip(),
        observations=tuple(item.strip() for item in observations),
        suggestions=tuple(parsed_suggestions),
    )


def _resolve_model(model: str | None) -> str:
    if model is not None and model.strip():
        return model.strip()
    env_model = os.environ.get("OPENAI_MODEL", "").strip()
    return env_model or OPENAI_MODEL_DEFAULT


def _resolve_api_key(api_key: str | None) -> str | None:
    if api_key is not None:
        return api_key.strip() or None
    env_key = os.environ.get("OPENAI_API_KEY", "").strip()
    return env_key or None


def _review_error_message(exc: Exception) -> str:
    if "Timeout" in exc.__class__.__name__:
        return "The review request timed out. Try again."
    text = str(exc).strip() or exc.__class__.__name__
    if len(text) > 300:
        text = f"{text[:297]}..."
    return f"Could not generate a review: {text}"
