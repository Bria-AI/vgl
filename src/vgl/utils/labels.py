"""Request-scoped GCP billing labels for Vertex Gemini calls.

A service sets them once per request; every call made in that context carries them.
A bare ``ThreadPoolExecutor.submit`` does not inherit them.
"""

import re
from collections.abc import Mapping
from contextvars import ContextVar, Token

#: Vertex label values allow only these characters, up to 63 of them.
_INVALID_LABEL_CHARS = re.compile(r"[^a-z0-9_-]")
_MAX_LABEL_LENGTH = 63

_request_labels: ContextVar[Mapping[str, str] | None] = ContextVar("vgl_request_labels", default=None)


def label_value(value: str) -> str:
    return _INVALID_LABEL_CHARS.sub("-", value.lower())[:_MAX_LABEL_LENGTH]


def set_request_labels(labels: Mapping[str, str]) -> Token:
    """Label every Vertex Gemini call made from the current context, replacing earlier labels."""
    return _request_labels.set(dict(labels))


def reset_request_labels(token: Token) -> None:
    _request_labels.reset(token)


def get_request_labels() -> dict[str, str]:
    """Sanitized; empty values are dropped."""
    labels = _request_labels.get() or {}
    return {key: label_value(value) for key, value in labels.items() if value}
