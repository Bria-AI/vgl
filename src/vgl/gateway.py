import logging
import os
import random
import time
from collections.abc import Sequence
from functools import cache
from typing import Any, cast

import litellm
from litellm.exceptions import APIConnectionError, InternalServerError, RateLimitError, ServiceUnavailableError, Timeout
from litellm.types.utils import ModelResponse
from PIL import Image

from vgl.exceptions import MaxTokensError
from vgl.utils.images import to_base64_jpeg
from vgl.utils.labels import get_request_labels, label_value

logger = logging.getLogger(__name__)

# Lighter model tried when the primary Gemini/Vertex model keeps failing.
GEMINI_FALLBACK_MODEL = "gemini-3.1-flash-lite"

#: Worth another attempt on the same model. Vertex spells "the model is overloaded" as a 500/503.
RETRYABLE_ERRORS = (InternalServerError, ServiceUnavailableError, APIConnectionError, Timeout)

#: A 429 is deliberately absent above: quota is per model and per minute, so retrying in place
#: lands in the same exhausted window — it moves straight to the fallback model instead.
FALLBACK_ERRORS = (RateLimitError, *RETRYABLE_ERRORS)

#: Attempts per model, applied to the primary and the fallback separately.
MAX_ATTEMPTS = 3

#: Doubled each attempt and fully jittered, so a fleet does not retry in lockstep.
BACKOFF_SECONDS = 0.5


def _vertex_labels(overrides: dict[str, str]) -> dict[str, str]:
    """GCP billing labels: defaults, then request labels, then the caller's. litellm forwards
    `labels`, not `metadata`, to Vertex."""
    labels = {"billing_category": "production"}
    service = os.environ.get("SERVICE_NAME", "").strip()
    if service:
        labels["service"] = label_value(service)
    return {**labels, **get_request_labels(), **overrides}


def _backoff_seconds(attempt: int) -> float:
    """Full jitter, which spreads a fleet's retries better than a fixed exponential delay."""
    return random.uniform(0, BACKOFF_SECONDS * 2 ** (attempt - 1))


#: Gemini's OpenAPI dialect spells types in upper case. Standard JSON Schema does not, and
#: Bedrock validates against the standard enum, rejecting the bundled schema outright.
_JSON_SCHEMA_TYPES = {"OBJECT": "object", "ARRAY": "array", "STRING": "string", "INTEGER": "integer", "NUMBER": "number", "BOOLEAN": "boolean"}


def _to_standard_json_schema(node: Any) -> Any:
    """The bundled schema, in Gemini's dialect, rewritten as standard JSON Schema.

    Translated on the way out rather than stored that way, so the bytes Gemini receives — the
    ones every prompt was tuned against — are untouched.
    """
    if isinstance(node, list):
        return [_to_standard_json_schema(item) for item in node]
    if not isinstance(node, dict):
        return node

    converted = {}
    for key, value in node.items():
        # propertyOrdering is Gemini-only, and strict validators reject unknown keywords.
        if key in ("nullable", "propertyOrdering"):
            continue
        if key == "type" and isinstance(value, str):
            converted[key] = _JSON_SCHEMA_TYPES.get(value.upper(), value.lower())
        elif key == "properties" and isinstance(value, dict):
            # Keys here are field names, not keywords, so only the values are schemas.
            converted[key] = {name: _to_standard_json_schema(sub) for name, sub in value.items()}
        else:
            converted[key] = _to_standard_json_schema(value)

    if node.get("nullable") and isinstance(converted.get("type"), str):
        converted["type"] = [converted["type"], "null"]

    # Bedrock's structured output is strict and requires this on every object. Harmless
    # elsewhere: the VGL model forbids extra fields anyway.
    if "properties" in converted and "additionalProperties" not in converted:
        converted["additionalProperties"] = False
    return converted


def _is_anthropic(model_name: str) -> bool:
    """Claude on any route: direct, Bedrock or Vertex."""
    lowered = model_name.lower()
    return "anthropic" in lowered or "claude" in lowered


@cache
def _supports_seed(model_name: str) -> bool:
    """Whether the provider accepts ``seed``. Unknown models are assumed to, as before.

    Anthropic rejects it on every route, direct and via Bedrock, so sending it unconditionally
    made those providers unreachable with an UnsupportedParamsError.
    """
    try:
        supported = litellm.get_supported_openai_params(model=model_name)
    except Exception:
        return True
    return True if supported is None else "seed" in supported


def call(
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    images: Sequence[Image.Image] = (),
    temperature: float = 0.0,
    seed: int | None = 42,
    response_schema: dict | None = None,
    # A lower ceiling turns a valid long VGL into MaxTokensError.
    max_output_tokens: int = 7000,
    top_p: float = 1.0,
    labels: dict[str, str] | None = None,
    thinking_level: str | None = None,
) -> str:
    """One completion, retried and then moved to the Gemini fallback. Returns the reply text.

    ``thinking_level`` applies to Gemini only; None keeps its thinking off.
    """
    messages = _messages(system_prompt, user_prompt, images)
    params = _params(model_name, temperature, top_p, seed, max_output_tokens, response_schema, labels or {}, thinking_level)
    try:
        response = _complete_with_retries(model_name, messages, params)
    except FALLBACK_ERRORS:
        fallback = _fallback_model(model_name)
        if fallback is None:
            raise
        logger.warning("Gemini model exhausted its attempts; moving to the fallback", extra={"model": model_name, "fallback": fallback})
        response = _complete_with_retries(fallback, messages, params)

    if response.choices[0].finish_reason == "length":
        raise MaxTokensError(f"Max tokens ({max_output_tokens}) reached for model {model_name}")
    # litellm types content as optional; a None reply fails parsing downstream.
    return cast(str, response.choices[0].message.content)


def _messages(system_prompt: str, user_prompt: str, images: Sequence[Image.Image]) -> list[dict]:
    images_content = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{to_base64_jpeg(image)}"}} for image in images]
    return [{"role": "system", "content": system_prompt}, {"role": "user", "content": [{"type": "text", "text": user_prompt}, *images_content]}]


def _params(
    model_name: str,
    temperature: float,
    top_p: float,
    seed: int | None,
    max_output_tokens: int,
    response_schema: dict | None,
    labels: dict[str, str],
    thinking_level: str | None = None,
) -> dict[str, Any]:
    """litellm.completion's arguments besides the model and messages."""
    if seed is not None and not _supports_seed(model_name):
        logger.warning("%s does not accept a seed; dropping it, so this call is not reproducible", model_name)
        seed = None
    params: dict[str, Any] = {"temperature": temperature, "max_tokens": max_output_tokens, "seed": seed}
    # Anthropic rejects top_p with temperature. Others keep it: Gemini's own default is 0.95, not 1.0.
    if not _is_anthropic(model_name):
        params["top_p"] = top_p

    lowered = model_name.lower()
    # Keyed off the model, not the provider: vertex_ai also serves Claude.
    if "gemini" not in lowered:
        if response_schema:
            params["response_format"] = {"type": "json_object", "response_schema": _to_standard_json_schema(response_schema)}
        return params

    params["metadata"] = {"billing_category": "production"}
    if "vertex_ai" not in lowered:
        if thinking_level:
            # litellm maps this to Gemini 3's thinkingLevel.
            params["reasoning_effort"] = thinking_level
        else:
            params["extra_body"] = {"thinking_config": {"include_thoughts": True, "thinking_budget": 0}}
        if response_schema:
            params["response_format"] = {"type": "json_object", "response_schema": response_schema}
        return params

    # Not via response_format on Vertex: litellm turns that into responseJsonSchema, which samples differently.
    thinking_config = {"thinkingLevel": thinking_level} if thinking_level else {"thinkingBudget": 0}
    generation_config: dict[str, Any] = {"thinkingConfig": thinking_config}
    if response_schema:
        generation_config |= {"responseMimeType": "application/json", "responseSchema": response_schema}
    params["extra_body"] = {"generationConfig": generation_config}
    params["labels"] = _vertex_labels(labels)
    return params


def _fallback_model(model_name: str) -> str | None:
    """The lighter Gemini on the same provider prefix, or None for a non-Gemini model or one already on it."""
    if "gemini" not in model_name.lower():
        return None
    prefix, slash, _ = model_name.rpartition("/")
    fallback = f"{prefix}{slash}{GEMINI_FALLBACK_MODEL}"
    return None if fallback == model_name else fallback


def _complete_with_retries(model: str, messages: list[dict], params: dict[str, Any]) -> ModelResponse:
    """MAX_ATTEMPTS against one model, backing off between them. The last attempt raises."""
    for attempt in range(1, MAX_ATTEMPTS):
        try:
            return _complete(model, messages, params)
        except RETRYABLE_ERRORS as transient:
            delay = _backoff_seconds(attempt)
            logger.warning(
                "Transient LLM failure; retrying the same model",
                extra={"model": model, "attempt": attempt, "error": type(transient).__name__, "delay_seconds": round(delay, 3)},
            )
            time.sleep(delay)
    return _complete(model, messages, params)


def _complete(model: str, messages: list[dict], params: dict[str, Any]) -> ModelResponse:
    start = time.perf_counter()
    try:
        # Never streamed, so always a ModelResponse.
        return cast(ModelResponse, litellm.completion(model=model, messages=messages, **params))
    finally:
        # A call that fails fast is the one worth timing.
        logger.info("LLM call", extra={"model": model, "duration_seconds": round(time.perf_counter() - start, 3)})
