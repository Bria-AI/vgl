"""Unit tests for gateway.call — retries, the model fallback and the token-ceiling failure."""

import json
import time

import litellm
import pytest
from litellm.exceptions import BadRequestError, ContentPolicyViolationError, RateLimitError, ServiceUnavailableError, Timeout

from bria_vgl import gateway
from bria_vgl.exceptions import MaxTokensError, VGLError
from bria_vgl.gateway import BACKOFF_SECONDS, GEMINI_FALLBACK_MODEL, MAX_ATTEMPTS, ThinkingLevel, _backoff_seconds, _to_standard_json_schema
from bria_vgl.utils.labels import reset_request_labels, set_request_labels

_GEMINI = "vertex_ai/gemini-2.5-flash"
_FALLBACK = f"vertex_ai/{GEMINI_FALLBACK_MODEL}"


class _StubMessage:
    def __init__(self, content, finish_reason):
        self.content = content
        self.finish_reason = finish_reason

    @property
    def message(self):
        return self


class _StubResponse:
    def __init__(self, content="ok", finish_reason="stop"):
        self.choices = [_StubMessage(content, finish_reason)]


def _rate_limited():
    return RateLimitError(message="429", model="m", llm_provider="vertex_ai")


def _overloaded():
    """How Vertex reports "the model is overloaded" — a 503, not a 429."""
    return ServiceUnavailableError(message="503 model overloaded", llm_provider="vertex_ai", model="m")


@pytest.mark.unit
class TestGatewayCall:
    def setup_method(self):
        self.truncated = _StubResponse("half a caption", finish_reason="length")

    def _patch_completion(self, monkeypatch, side_effects):
        """Swap litellm.completion for a scripted stub; returns the models it was called with."""
        calls = []

        def fake(*, model, **kwargs):
            calls.append(model)
            result = side_effects.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        monkeypatch.setattr(litellm, "completion", fake)
        return calls

    # --- 429 fallback ---

    def test_call_on_gemini_rate_limit_should_retry_once_on_the_fallback_model(self, monkeypatch):
        # Arrange
        calls = self._patch_completion(monkeypatch, [_rate_limited(), _StubResponse("ok")])

        # Act
        result = gateway.call(model_name=_GEMINI, system_prompt="s", user_prompt="u")

        # Assert
        assert result == "ok"
        assert calls == [_GEMINI, _FALLBACK]

    def test_call_on_fallback_should_send_thinking_off_in_the_fallback_models_form(self, monkeypatch):
        """Gemini 2.x takes a zero budget; the Gemini 3+ fallback on AI Studio needs the minimal level."""
        # Arrange
        thinking = []

        def fake(*, model, **kwargs):
            thinking.append(kwargs["extra_body"]["generationConfig"]["thinkingConfig"])
            if len(thinking) == 1:
                raise _rate_limited()
            return _StubResponse("ok")

        monkeypatch.setattr(litellm, "completion", fake)

        # Act
        gateway.call(model_name="gemini/gemini-2.5-flash", system_prompt="s", user_prompt="u")

        # Assert
        assert thinking == [{"thinkingBudget": 0}, {"thinkingLevel": "minimal"}]

    def test_call_on_fallback_should_keep_the_thinking_level(self, monkeypatch):
        # Arrange
        thinking = []

        def fake(*, model, **kwargs):
            thinking.append(kwargs["extra_body"]["generationConfig"]["thinkingConfig"])
            if len(thinking) == 1:
                raise _rate_limited()
            return _StubResponse("ok")

        monkeypatch.setattr(litellm, "completion", fake)

        # Act
        gateway.call(model_name="gemini/gemini-3.5-flash", system_prompt="s", user_prompt="u", thinking_level="high")

        # Assert
        assert thinking == [{"thinkingLevel": "high"}, {"thinkingLevel": "high"}]

    def test_call_on_non_gemini_rate_limit_should_propagate_without_retrying(self, monkeypatch):
        # Arrange
        calls = self._patch_completion(monkeypatch, [_rate_limited()])

        # Act
        with pytest.raises(RateLimitError):
            gateway.call(model_name="gpt-4o", system_prompt="s", user_prompt="u")

        # Assert
        assert calls == ["gpt-4o"]

    def test_call_on_rate_limit_while_already_on_the_fallback_should_not_retry_again(self, monkeypatch):
        # Arrange
        calls = self._patch_completion(monkeypatch, [_rate_limited()])

        # Act
        with pytest.raises(RateLimitError):
            gateway.call(model_name=_FALLBACK, system_prompt="s", user_prompt="u")

        # Assert
        assert calls == [_FALLBACK]

    # --- token ceiling ---

    def test_call_should_default_to_the_ceiling_promptify_ran_with(self, monkeypatch):
        """A VGL can exceed 5000 tokens, and the ceiling is what turns one into MaxTokensError."""
        # Arrange
        sent = {}

        def fake(*, model, **kwargs):
            sent.update(kwargs)
            return _StubResponse("ok")

        monkeypatch.setattr(litellm, "completion", fake)

        # Act
        gateway.call(model_name=_GEMINI, system_prompt="s", user_prompt="u")

        # Assert
        assert sent["max_tokens"] == 7000

    def test_call_on_response_truncated_by_the_token_ceiling_should_raise_max_tokens_error(self, monkeypatch):
        """Callers map this to a client error, so it must not surface as a bare Exception."""
        # Arrange
        self._patch_completion(monkeypatch, [self.truncated])

        # Act / Assert
        with pytest.raises(MaxTokensError):
            gateway.call(model_name=_GEMINI, system_prompt="s", user_prompt="u")

    def test_call_on_response_truncated_by_the_token_ceiling_should_name_the_model_and_ceiling(self, monkeypatch):
        # Arrange
        self._patch_completion(monkeypatch, [self.truncated])

        # Act
        with pytest.raises(MaxTokensError) as excinfo:
            gateway.call(model_name=_GEMINI, system_prompt="s", user_prompt="u", max_output_tokens=123)

        # Assert
        assert "123" in str(excinfo.value) and _GEMINI in str(excinfo.value)

    def test_call_on_fallback_model_hitting_the_token_ceiling_should_still_raise_max_tokens_error(self, monkeypatch):
        """The 429 retry must not swallow a truncation on the second attempt."""
        # Arrange - primary rate-limits, fallback answers but gets cut off
        calls = self._patch_completion(monkeypatch, [_rate_limited(), self.truncated])

        # Act / Assert
        with pytest.raises(MaxTokensError):
            gateway.call(model_name=_GEMINI, system_prompt="s", user_prompt="u")
        assert calls == [_GEMINI, _FALLBACK]

    def test_max_tokens_error_should_be_catchable_as_a_vgl_error(self):
        """Lets callers catch any vgl failure without naming each subclass."""
        # Arrange / Act / Assert
        assert issubclass(MaxTokensError, VGLError)


@pytest.mark.unit
class TestTransientFailureRetries:
    """A single Vertex 5xx used to cost a customer request: the gateway made one call and gave up.

    Only a 429 reached the model fallback, and Vertex reports an overloaded model as a 503.
    """

    @pytest.fixture(autouse=True)
    def _no_real_sleeping(self, monkeypatch):
        """Record the backoffs instead of serving them, so the suite stays instant."""
        self.slept = []
        monkeypatch.setattr(time, "sleep", self.slept.append)

    def _patch_completion(self, monkeypatch, side_effects):
        calls = []

        def fake(*, model, **kwargs):
            calls.append(model)
            result = side_effects.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        monkeypatch.setattr(litellm, "completion", fake)
        return calls

    def test_call_on_a_transient_failure_should_retry_the_same_model(self, monkeypatch):
        """The model is fine; this one call lost. Switching models would be the wrong response."""
        # Arrange
        calls = self._patch_completion(monkeypatch, [_overloaded(), _StubResponse("ok")])

        # Act
        result = gateway.call(model_name=_GEMINI, system_prompt="s", user_prompt="u")

        # Assert
        assert result == "ok"
        assert calls == [_GEMINI, _GEMINI]

    def test_call_should_back_off_between_attempts(self, monkeypatch):
        # Arrange
        self._patch_completion(monkeypatch, [_overloaded(), _StubResponse("ok")])

        # Act
        gateway.call(model_name=_GEMINI, system_prompt="s", user_prompt="u")

        # Assert
        assert len(self.slept) == 1 and 0 <= self.slept[0] <= BACKOFF_SECONDS

    def test_call_on_a_model_that_exhausts_its_attempts_should_move_to_the_fallback(self, monkeypatch):
        # Arrange
        calls = self._patch_completion(monkeypatch, [*[_overloaded()] * MAX_ATTEMPTS, _StubResponse("ok")])

        # Act
        result = gateway.call(model_name=_GEMINI, system_prompt="s", user_prompt="u")

        # Assert
        assert result == "ok"
        assert calls == [_GEMINI] * MAX_ATTEMPTS + [_FALLBACK]

    def test_call_should_propagate_once_both_models_are_exhausted(self, monkeypatch):
        """The budget is bounded: a total provider outage must still fail, not retry forever."""
        # Arrange
        calls = self._patch_completion(monkeypatch, [_overloaded()] * (2 * MAX_ATTEMPTS))

        # Act
        with pytest.raises(ServiceUnavailableError):
            gateway.call(model_name=_GEMINI, system_prompt="s", user_prompt="u")

        # Assert
        assert calls == [_GEMINI] * MAX_ATTEMPTS + [_FALLBACK] * MAX_ATTEMPTS

    def test_call_on_a_rate_limit_should_not_retry_the_same_model(self, monkeypatch):
        """Quota is per model and per minute, so the second attempt belongs on the fallback."""
        # Arrange
        calls = self._patch_completion(monkeypatch, [_rate_limited(), _StubResponse("ok")])

        # Act
        gateway.call(model_name=_GEMINI, system_prompt="s", user_prompt="u")

        # Assert
        assert calls == [_GEMINI, _FALLBACK]

    def test_call_on_a_timeout_should_retry(self, monkeypatch):
        """A timeout is the one transient failure that costs the caller real latency, so it is
        worth naming: dropping it from the set would quietly restore the old behaviour."""
        # Arrange
        calls = self._patch_completion(monkeypatch, [Timeout(message="timed out", model="m", llm_provider="vertex_ai"), _StubResponse("ok")])

        # Act
        gateway.call(model_name=_GEMINI, system_prompt="s", user_prompt="u")

        # Assert
        assert calls == [_GEMINI, _GEMINI]

    @pytest.mark.parametrize(
        "error",
        [
            BadRequestError(message="400", model="m", llm_provider="vertex_ai"),
            ContentPolicyViolationError(message="blocked", model="m", llm_provider="vertex_ai"),
        ],
    )
    def test_call_on_a_failure_the_provider_will_repeat_should_not_retry(self, monkeypatch, error):
        """A malformed request and a blocked response fail identically on every attempt."""
        # Arrange
        calls = self._patch_completion(monkeypatch, [error])

        # Act
        with pytest.raises(type(error)):
            gateway.call(model_name=_GEMINI, system_prompt="s", user_prompt="u")

        # Assert
        assert calls == [_GEMINI]

    def test_call_on_a_transient_failure_from_a_non_gemini_model_should_not_reach_the_fallback(self, monkeypatch):
        """The fallback is a Gemini model; sending another provider's traffic there is a bug."""
        # Arrange
        calls = self._patch_completion(monkeypatch, [_overloaded()] * MAX_ATTEMPTS)

        # Act
        with pytest.raises(ServiceUnavailableError):
            gateway.call(model_name="gpt-4o", system_prompt="s", user_prompt="u")

        # Assert
        assert calls == ["gpt-4o"] * MAX_ATTEMPTS


@pytest.mark.unit
class TestCallDurationLogging:
    """The 2026-09-03 outage was a fast failure, and nothing recorded how long a call took."""

    @pytest.fixture(autouse=True)
    def _no_real_sleeping(self, monkeypatch):
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    def _patch_completion(self, monkeypatch, side_effects):
        def fake(*, model, **kwargs):
            result = side_effects.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        monkeypatch.setattr(litellm, "completion", fake)

    def _timings(self, caplog):
        return [record for record in caplog.records if record.message == "LLM call"]

    def test_a_call_should_log_its_model_and_duration(self, monkeypatch, caplog):
        # Arrange
        self._patch_completion(monkeypatch, [_StubResponse("ok")])

        # Act
        with caplog.at_level("INFO"):
            gateway.call(model_name=_GEMINI, system_prompt="s", user_prompt="u")

        # Assert
        (timing,) = self._timings(caplog)
        assert timing.model == _GEMINI
        assert isinstance(timing.duration_seconds, float)

    def test_every_attempt_should_be_timed_including_the_fallback(self, monkeypatch, caplog):
        """A retried call's cost is the sum of its attempts, so one record for the last is a lie."""
        # Arrange
        self._patch_completion(monkeypatch, [*[_overloaded()] * MAX_ATTEMPTS, _StubResponse("ok")])

        # Act
        with caplog.at_level("INFO"):
            gateway.call(model_name=_GEMINI, system_prompt="s", user_prompt="u")

        # Assert
        assert [timing.model for timing in self._timings(caplog)] == [_GEMINI] * MAX_ATTEMPTS + [_FALLBACK]

    def test_a_failing_call_should_still_be_timed(self, monkeypatch, caplog):
        """The failures are the reason this exists: they die in ~200ms and skew nothing else."""
        # Arrange
        self._patch_completion(monkeypatch, [_overloaded()] * (2 * MAX_ATTEMPTS))

        # Act
        with caplog.at_level("INFO"), pytest.raises(ServiceUnavailableError):
            gateway.call(model_name=_GEMINI, system_prompt="s", user_prompt="u")

        # Assert
        assert len(self._timings(caplog)) == 2 * MAX_ATTEMPTS


@pytest.mark.unit
class TestBackoff:
    @pytest.mark.parametrize("attempt", range(1, MAX_ATTEMPTS))
    def test_backoff_should_stay_within_the_jitter_window_for_the_attempt(self, attempt):
        """Full jitter: uniform below an exponentially growing ceiling."""
        # Arrange / Act
        delays = [_backoff_seconds(attempt) for _ in range(200)]

        # Assert
        assert all(0 <= delay <= BACKOFF_SECONDS * 2 ** (attempt - 1) for delay in delays)

    def test_backoff_should_grow_with_the_attempt(self):
        """A flat delay would retry a slow-recovering provider as hard as a momentary blip."""
        # Arrange / Act
        first = max(_backoff_seconds(1) for _ in range(200))
        second = max(_backoff_seconds(2) for _ in range(200))

        # Assert
        assert second > first


@pytest.mark.unit
class TestProviderSpecificParameters:
    """Every Gemini-specific branch keys off the model, not the provider.

    `vertex_ai` also serves Claude, which understands neither `generationConfig` nor
    `thinkingConfig` — and would have been sent both while getting no usable schema.
    """

    @staticmethod
    def _sent(monkeypatch, model_name, response_schema=None, **call_kwargs):
        captured = {}

        def fake(**kwargs):
            captured.update(kwargs)
            return _StubResponse()

        monkeypatch.setattr(litellm, "completion", fake)
        gateway.call(model_name=model_name, system_prompt="s", user_prompt="u", response_schema=response_schema, **call_kwargs)
        return captured

    _SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}

    @pytest.mark.parametrize("model_name", [_GEMINI, "gemini/gemini-2.5-flash"])
    def test_gemini_should_get_the_schema_in_generation_config(self, monkeypatch, model_name):
        """The decoding path the bundled prompts were tuned against, on Vertex and AI Studio alike."""
        # Act
        sent = self._sent(monkeypatch, model_name, self._SCHEMA)

        # Assert
        assert sent["extra_body"]["generationConfig"]["responseSchema"] == self._SCHEMA
        assert sent.get("response_format") is None

    @pytest.mark.parametrize(
        ("model_name", "thinking"),
        [
            (_GEMINI, {"thinkingBudget": 0}),
            ("gemini/gemini-3.5-flash-lite", {"thinkingLevel": "minimal"}),
            ("gemini/gemini-2.5-flash", {"thinkingBudget": 0}),
        ],
    )
    def test_gemini_should_get_thinking_off_in_a_form_its_provider_accepts(self, monkeypatch, model_name, thinking):
        """AI Studio rejects a zero thinking budget on Gemini 3+; Vertex accepts it."""
        # Act
        sent = self._sent(monkeypatch, model_name, self._SCHEMA)

        # Assert
        assert sent["extra_body"]["generationConfig"]["thinkingConfig"] == thinking

    @pytest.mark.parametrize("model_name", ["vertex_ai/gemini-3.5-flash", "gemini/gemini-3.5-flash"])
    def test_a_thinking_level_should_replace_thinking_off(self, monkeypatch, model_name):
        # Act
        sent = self._sent(monkeypatch, model_name, thinking_level="high")

        # Assert
        assert sent["extra_body"]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "high"}

    def test_a_thinking_level_member_should_be_sent_as_its_value(self, monkeypatch):
        # Act
        sent = self._sent(monkeypatch, "gemini/gemini-3.5-flash", thinking_level=ThinkingLevel.LOW)

        # Assert
        assert sent["extra_body"]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}
        assert type(sent["extra_body"]["generationConfig"]["thinkingConfig"]["thinkingLevel"]) is str

    @pytest.mark.parametrize(
        ("model_name", "level"), [("gemini/gemini-3.5-flash", "hgh"), ("gemini/gemini-2.5-flash", "high"), ("vertex_ai/gemini-2.5-flash", "high")]
    )
    def test_an_unusable_thinking_level_should_raise_before_the_call(self, monkeypatch, model_name, level):
        """An unknown level, or a level on Gemini 2, which only has budgets."""
        # Arrange
        calls = []
        monkeypatch.setattr(litellm, "completion", lambda **kwargs: calls.append(kwargs))

        # Act
        with pytest.raises(ValueError):
            gateway.call(model_name=model_name, system_prompt="s", user_prompt="u", thinking_level=level)

        # Assert
        assert calls == []

    def test_a_thinking_level_should_not_reach_a_non_gemini_model(self, monkeypatch):
        # Act
        sent = self._sent(monkeypatch, "anthropic/claude-sonnet-4-5", thinking_level="high")

        # Assert
        assert "extra_body" not in sent and "reasoning_effort" not in sent

    @pytest.mark.parametrize("model_name", ["vertex_ai/claude-sonnet-4-5", "anthropic/claude-sonnet-4-5"])
    def test_claude_should_get_the_schema_as_a_response_format(self, monkeypatch, model_name):
        """Including on vertex_ai: the provider prefix does not make it a Gemini call.

        Translated to standard JSON Schema on the way out, which is what non-Gemini validates.
        """
        # Act
        sent = self._sent(monkeypatch, model_name, self._SCHEMA)

        # Assert
        assert sent["response_format"]["type"] == "json_object"
        assert sent["response_format"]["response_schema"] == _to_standard_json_schema(self._SCHEMA)

    @pytest.mark.parametrize("model_name", ["vertex_ai/claude-sonnet-4-5", "anthropic/claude-sonnet-4-5", "gpt-5"])
    def test_a_non_gemini_model_should_get_no_gemini_configuration(self, monkeypatch, model_name):
        """thinkingConfig and generationConfig are Gemini API concepts; sending them is a request error."""
        # Act
        sent = self._sent(monkeypatch, model_name, self._SCHEMA)

        # Assert
        assert "extra_body" not in sent
        assert "billing_category" not in sent.get("metadata", {})

    def test_gemini_on_vertex_should_be_labelled_for_billing(self, monkeypatch):
        # Arrange
        monkeypatch.setenv("SERVICE_NAME", "text_to_image")

        # Act
        sent = self._sent(monkeypatch, _GEMINI)

        # Assert
        assert sent["labels"] == {"billing_category": "production", "service": "text_to_image"}

    def test_a_service_name_should_be_sanitized_to_a_valid_label(self, monkeypatch):
        # Arrange
        monkeypatch.setenv("SERVICE_NAME", "Text.To Image" + "x" * 100)

        # Act
        service = self._sent(monkeypatch, _GEMINI)["labels"]["service"]

        # Assert
        assert service.startswith("text-to-image") and len(service) == 63

    def test_no_service_name_should_omit_the_service_label(self, monkeypatch):
        # Arrange
        monkeypatch.delenv("SERVICE_NAME", raising=False)

        # Act
        sent = self._sent(monkeypatch, _GEMINI)

        # Assert
        assert sent["labels"] == {"billing_category": "production"}

    def test_caller_labels_should_override_the_defaults(self, monkeypatch):
        # Arrange
        monkeypatch.setenv("SERVICE_NAME", "text_to_image")
        captured = {}
        monkeypatch.setattr(litellm, "completion", lambda **kwargs: captured.update(kwargs) or _StubResponse())

        # Act
        gateway.call(model_name=_GEMINI, system_prompt="s", user_prompt="u", labels={"service": "goodegg"})

        # Assert
        assert captured["labels"] == {"billing_category": "production", "service": "goodegg"}

    def test_request_labels_should_be_sent_alongside_the_defaults(self, monkeypatch):
        # Arrange
        monkeypatch.setenv("SERVICE_NAME", "text_to_image")
        token = set_request_labels({"endpoint": "v2-structured_prompt-generate", "env": "production"})

        # Act
        try:
            sent = self._sent(monkeypatch, _GEMINI)
        finally:
            reset_request_labels(token)

        # Assert
        assert sent["labels"] == {
            "billing_category": "production",
            "service": "text_to_image",
            "endpoint": "v2-structured_prompt-generate",
            "env": "production",
        }

    def test_request_labels_should_be_sanitized_and_empty_ones_dropped(self, monkeypatch):
        # Arrange
        token = set_request_labels({"endpoint": "/V2/Image/Generate", "env": ""})

        # Act
        try:
            labels = self._sent(monkeypatch, _GEMINI)["labels"]
        finally:
            reset_request_labels(token)

        # Assert
        assert labels["endpoint"] == "-v2-image-generate" and "env" not in labels

    def test_caller_labels_should_override_request_labels(self, monkeypatch):
        # Arrange
        captured = {}
        monkeypatch.setattr(litellm, "completion", lambda **kwargs: captured.update(kwargs) or _StubResponse())
        token = set_request_labels({"endpoint": "from-request"})

        # Act
        try:
            gateway.call(model_name=_GEMINI, system_prompt="s", user_prompt="u", labels={"endpoint": "from-caller"})
        finally:
            reset_request_labels(token)

        # Assert
        assert captured["labels"]["endpoint"] == "from-caller"

    def test_request_labels_should_not_reach_a_non_vertex_call(self, monkeypatch):
        """Claude rejects the unknown field, whatever the request set."""
        # Arrange
        token = set_request_labels({"endpoint": "v2-image-generate"})

        # Act
        try:
            sent = self._sent(monkeypatch, "vertex_ai/claude-sonnet-4-5")
        finally:
            reset_request_labels(token)

        # Assert
        assert "labels" not in sent

    @pytest.mark.parametrize("model_name", ["vertex_ai/claude-sonnet-4-5", "gemini/gemini-2.5-flash", "gpt-5"])
    def test_a_call_outside_vertex_gemini_should_get_no_labels(self, monkeypatch, model_name):
        """litellm drops labels for AI Studio, and Claude rejects the unknown field."""
        # Act
        sent = self._sent(monkeypatch, model_name)

        # Assert
        assert "labels" not in sent


@pytest.mark.unit
class TestSeedSupport:
    """Anthropic rejects `seed` on every route, so sending it unconditionally made those
    providers unreachable with an UnsupportedParamsError before any prompt was even built."""

    @staticmethod
    def _seed_sent(monkeypatch, model_name):
        captured = {}

        def fake(**kwargs):
            captured.update(kwargs)
            return _StubResponse()

        monkeypatch.setattr(litellm, "completion", fake)
        gateway.call(model_name=model_name, system_prompt="s", user_prompt="u", seed=42)
        return captured.get("seed")

    def test_the_production_model_should_still_receive_its_seed(self, monkeypatch):
        """The parity bar: vertex_ai gemini supports seed, so nothing about it may change."""
        # Act / Assert
        assert self._seed_sent(monkeypatch, _GEMINI) == 42

    @pytest.mark.parametrize("model_name", ["gemini/gemini-3.5-flash-lite", "gemini/gemini-2.5-flash"])
    def test_gemini_on_ai_studio_should_receive_its_seed(self, monkeypatch, model_name):
        """AI Studio honours a seed, though litellm before 1.105 doesn't list it there."""
        # Act / Assert
        assert self._seed_sent(monkeypatch, model_name) == 42

    def test_gemini_on_ai_studio_should_have_its_seed_accepted_by_litellm(self, monkeypatch):
        """Through litellm's own parameter check, offline: before 1.105 it rejects a seed for AI Studio unless allowed."""
        # Arrange
        complete = litellm.completion
        monkeypatch.setattr(litellm, "completion", lambda **kwargs: complete(**kwargs, mock_response="ok"))

        # Act
        result = gateway.call(model_name="gemini/gemini-3.5-flash-lite", system_prompt="s", user_prompt="u", seed=42)

        # Assert
        assert result == "ok"

    @pytest.mark.parametrize(
        "model_name",
        ["anthropic/claude-sonnet-4-5", "bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0"],
    )
    def test_a_model_that_rejects_seed_should_have_it_dropped(self, monkeypatch, model_name):
        # Act / Assert
        assert self._seed_sent(monkeypatch, model_name) is None

    def test_dropping_the_seed_should_warn_that_the_call_is_not_reproducible(self, monkeypatch, caplog):
        """Silently losing reproducibility is the failure mode; the log line is the only signal."""
        # Act
        with caplog.at_level("WARNING"):
            self._seed_sent(monkeypatch, "anthropic/claude-sonnet-4-5")

        # Assert
        assert "not reproducible" in caplog.text

    def test_an_unknown_model_should_keep_its_seed(self, monkeypatch):
        """litellm cannot answer for every id, and the old behaviour was to send it."""
        # Act / Assert
        assert self._seed_sent(monkeypatch, "some-private-deployment/model-x") == 42


@pytest.mark.unit
class TestAnthropicCompatibility:
    """Each of these was a hard failure before any prompt reached the model.

    Verified against a live Bedrock call: Claude Sonnet 4.5 answers only once all three hold.
    """

    _CLAUDE = "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0"

    @staticmethod
    def _sent(monkeypatch, model_name):
        captured = {}

        def fake(**kwargs):
            captured.update(kwargs)
            return _StubResponse()

        monkeypatch.setattr(litellm, "completion", fake)
        gateway.call(model_name=model_name, system_prompt="s", user_prompt="u", seed=42)
        return captured

    def test_anthropic_should_not_receive_top_p(self, monkeypatch):
        """It rejects temperature and top_p together, and temperature is the one vgl varies."""
        # Act / Assert
        assert "top_p" not in self._sent(monkeypatch, self._CLAUDE)

    @pytest.mark.parametrize("model_name", [_GEMINI, "gpt-5"])
    def test_every_other_provider_should_still_receive_top_p(self, monkeypatch, model_name):
        """Gemini's own topP default is 0.95, so omitting 1.0 would change generated output."""
        # Act / Assert
        assert self._sent(monkeypatch, model_name)["top_p"] == 1.0

    def test_an_empty_extra_body_should_be_omitted_rather_than_sent(self, monkeypatch):
        """Bedrock forwards it to the model, and Anthropic rejects the unexpected field."""
        # Act
        sent = self._sent(monkeypatch, self._CLAUDE)

        # Assert
        assert "extra_body" not in sent and "metadata" not in sent

    def test_gemini_should_still_receive_both_containers(self, monkeypatch):
        # Act
        sent = self._sent(monkeypatch, _GEMINI)

        # Assert
        assert sent["extra_body"]["generationConfig"] and sent["metadata"]["billing_category"] == "production"


@pytest.mark.unit
class TestOutputSchemaDialect:
    """The bundled schema is authored in Gemini's OpenAPI dialect; Bedrock validates the standard.

    Translated on the way out, so the bytes Gemini receives are the ones every prompt was tuned
    against. Verified end to end: a live Bedrock call returns a valid VGL only once this holds.
    """

    _GEMINI_DIALECT = {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING"},
            "count": {"type": "INTEGER", "nullable": True},
            "tags": {"type": "ARRAY", "items": {"type": "STRING"}},
        },
        "required": ["name"],
    }

    def test_types_should_become_lower_case(self):
        # Act
        standard = _to_standard_json_schema(self._GEMINI_DIALECT)

        # Assert
        assert standard["type"] == "object"
        assert standard["properties"]["tags"]["items"]["type"] == "string"

    def test_nullable_should_become_a_union_with_null(self):
        """`nullable` is not a JSON Schema keyword; the standard spelling is a type union."""
        # Act
        standard = _to_standard_json_schema(self._GEMINI_DIALECT)

        # Assert
        assert standard["properties"]["count"]["type"] == ["integer", "null"]
        assert "nullable" not in standard["properties"]["count"]

    def test_every_object_should_gain_additional_properties_false(self):
        """Bedrock's structured output is strict and rejects an object without it."""
        # Act
        standard = _to_standard_json_schema(self._GEMINI_DIALECT)

        # Assert
        assert standard["additionalProperties"] is False

    def test_a_field_named_like_a_keyword_should_not_be_translated(self):
        """Keys under `properties` are field names, not schema keywords."""
        # Arrange
        schema = {"type": "OBJECT", "properties": {"type": {"type": "STRING"}, "items": {"type": "STRING"}}}

        # Act
        standard = _to_standard_json_schema(schema)

        # Assert
        assert set(standard["properties"]) == {"type", "items"}
        assert standard["properties"]["type"]["type"] == "string"

    def test_translation_should_not_mutate_the_input(self):
        """It is the wheel's own schema, cached and shared across every call."""
        # Arrange
        before = json.dumps(self._GEMINI_DIALECT, sort_keys=True)

        # Act
        _to_standard_json_schema(self._GEMINI_DIALECT)

        # Assert
        assert json.dumps(self._GEMINI_DIALECT, sort_keys=True) == before

    @pytest.mark.parametrize("model_name", [_GEMINI, "gemini/gemini-2.5-flash"])
    def test_gemini_should_receive_the_stored_schema_untranslated(self, monkeypatch, model_name):
        """The parity bar: these bytes are what the bundled prompts were tuned against."""
        # Arrange
        captured = {}

        def fake(**kwargs):
            captured.update(kwargs)
            return _StubResponse()

        monkeypatch.setattr(litellm, "completion", fake)

        # Act
        gateway.call(model_name=model_name, system_prompt="s", user_prompt="u", response_schema=self._GEMINI_DIALECT)

        # Assert
        sent = (captured.get("extra_body") or {}).get("generationConfig", {}).get("responseSchema") or captured["response_format"]["response_schema"]
        assert sent == self._GEMINI_DIALECT
