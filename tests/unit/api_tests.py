import json

import pytest
from litellm.exceptions import AuthenticationError, RateLimitError, ServiceUnavailableError

import vgl
from vgl import exceptions, gateway
from vgl.dialects.thales import EditImages, Generate, ThalesVGL
from vgl.prompting import BLOCK_PREAMBLE


@pytest.fixture(autouse=True)
def gemini_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")


@pytest.fixture
def sent(monkeypatch, a_vgl_dict):
    """Records each gateway call and answers with a valid VGL."""
    calls: list[dict] = []

    def fake_call(**kwargs):
        calls.append(kwargs)
        return json.dumps({**a_vgl_dict, "edit_instruction": "made it night"})

    monkeypatch.setattr(gateway, "call", fake_call)
    return calls


@pytest.mark.unit
class TestCreate:
    def test_should_return_the_dialects_vgl(self, sent):
        assert isinstance(vgl.create(Generate(prompt="a fox")), ThalesVGL)

    def test_should_default_to_gemini_on_ai_studio(self, sent):
        vgl.create(Generate(prompt="a fox"))
        assert sent[0]["model_name"] == vgl.DEFAULT_LLM == "gemini/gemini-3.5-flash-lite"

    def test_should_send_the_user_prompt_and_seed(self, sent):
        vgl.create(Generate(prompt="a red fox"), seed=7)
        assert "a red fox" in sent[0]["user_prompt"] and sent[0]["seed"] == 7

    def test_should_compose_a_style_preset_into_the_system_prompt(self, sent):
        vgl.create(Generate(prompt="a fox"), style_preset_prompt="Muted film colours.")
        assert BLOCK_PREAMBLE in sent[0]["system_prompt"] and "Muted film colours." in sent[0]["system_prompt"]

    def test_should_reject_an_edit_payload(self, an_image):
        with pytest.raises(TypeError, match="vgl.modify"):
            vgl.create(EditImages(prompt="p", images=[an_image]))  # type: ignore[arg-type]

    def test_a_misspelt_option_should_raise(self):
        with pytest.raises(TypeError):
            vgl.create(Generate(prompt="p"), lmm="x")  # type: ignore[call-arg]


@pytest.mark.unit
class TestModify:
    def test_should_send_images_in_order(self, sent, an_image, another_image):
        vgl.modify(EditImages(prompt="p", images=[another_image, an_image]))
        assert sent[0]["images"] == [another_image, an_image]

    def test_should_ignore_a_style_preset(self, sent, an_image):
        vgl.modify(EditImages(prompt="p", images=[an_image]), style_preset_prompt="Muted film colours.")
        assert "Muted film colours." not in sent[0]["system_prompt"]

    def test_should_reject_a_create_payload(self):
        with pytest.raises(TypeError, match="vgl.create"):
            vgl.modify(Generate(prompt="p"))


@pytest.mark.unit
class TestVertex:
    def test_a_vertex_llm_without_its_env_should_fail_before_the_call(self, sent, monkeypatch):
        for name in ("VERTEXAI_PROJECT", "VERTEXAI_LOCATION", "GOOGLE_APPLICATION_CREDENTIALS"):
            monkeypatch.delenv(name, raising=False)
        with pytest.raises(OSError):
            vgl.create(Generate(prompt="p"), llm="vertex_ai/gemini-3.5-flash-lite")
        assert sent == []


def _raise(error):
    def fake_call(**_):
        raise error

    return fake_call


@pytest.mark.unit
class TestProviderErrors:
    def test_a_rejected_key_should_raise_vgls_authentication_error(self, monkeypatch):
        # Arrange
        rejected = AuthenticationError(message="API key not valid", llm_provider="gemini", model="gemini/x")
        monkeypatch.setattr(gateway, "call", _raise(rejected))

        # Act
        with pytest.raises(exceptions.AuthenticationError, match="API key not valid") as raised:
            vgl.create(Generate(prompt="p"))

        # Assert
        assert raised.value.__cause__ is rejected

    def test_a_rate_limit_should_raise_vgls_rate_limit_error(self, monkeypatch):
        # Arrange
        limited = RateLimitError(message="429", llm_provider="gemini", model="gemini/x")
        monkeypatch.setattr(gateway, "call", _raise(limited))

        # Act
        with pytest.raises(exceptions.RateLimitError) as raised:
            vgl.create(Generate(prompt="p"))

        # Assert
        assert raised.value.__cause__ is limited
        assert isinstance(raised.value, exceptions.LLMError)

    def test_any_other_provider_error_should_raise_an_llm_error(self, monkeypatch):
        # Arrange
        overloaded = ServiceUnavailableError(message="503", llm_provider="gemini", model="gemini/x")
        monkeypatch.setattr(gateway, "call", _raise(overloaded))

        # Act
        with pytest.raises(exceptions.LLMError) as raised:
            vgl.create(Generate(prompt="p"))

        # Assert
        assert not isinstance(raised.value, (exceptions.AuthenticationError, exceptions.RateLimitError))
        assert isinstance(raised.value, exceptions.VGLError)

    def test_a_missing_gemini_key_should_fail_before_the_call(self, sent, monkeypatch):
        # Arrange
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        # Act
        with pytest.raises(exceptions.AuthenticationError, match="GEMINI_API_KEY"):
            vgl.create(Generate(prompt="p"))

        # Assert
        assert sent == []

    def test_a_max_tokens_error_should_pass_through_unwrapped(self, monkeypatch):
        # Arrange
        monkeypatch.setattr(gateway, "call", _raise(exceptions.MaxTokensError("7000")))

        # Act / Assert
        with pytest.raises(exceptions.MaxTokensError):
            vgl.create(Generate(prompt="p"))
