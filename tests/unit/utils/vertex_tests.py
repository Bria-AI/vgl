"""Unit tests for validate_vertex_env.

Engines call this in their constructor so a misconfigured deployment fails at
startup rather than on the first request. Each failure mode raises a different
type, which callers map to different handling.
"""

import builtins
import sys

import pytest

from vgl.utils.vertex import is_vertex_model, validate_vertex_env

_REQUIRED = ("VERTEXAI_PROJECT", "VERTEXAI_LOCATION", "GOOGLE_APPLICATION_CREDENTIALS")


@pytest.fixture
def clean_env(monkeypatch):
    """Start from none of the Vertex variables being set."""
    for name in _REQUIRED:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


@pytest.mark.unit
class TestValidateVertexEnv:
    def test_validate_vertex_env_on_a_complete_environment_should_pass(self, clean_env):
        # Arrange
        for name in _REQUIRED:
            clean_env.setenv(name, "value")

        # Act / Assert - no exception
        validate_vertex_env()

    def test_validate_vertex_env_on_an_empty_environment_should_raise_os_error(self, clean_env):
        # Act / Assert
        with pytest.raises(OSError, match="Missing required environment variables"):
            validate_vertex_env()

    @pytest.mark.parametrize("missing", _REQUIRED)
    def test_validate_vertex_env_on_any_single_missing_variable_should_raise(self, clean_env, missing):
        # Arrange
        for name in _REQUIRED:
            if name != missing:
                clean_env.setenv(name, "value")

        # Act / Assert
        with pytest.raises(OSError, match=missing):
            validate_vertex_env()

    def test_validate_vertex_env_should_name_every_missing_variable(self, clean_env):
        """One restart per missing variable is a slow way to learn what is needed.

        ``clean_env`` matters even though this sets nothing: importing litellm calls
        ``load_dotenv()``, so a populated ``.env`` leaks all three variables in.
        """
        # Act / Assert
        with pytest.raises(OSError) as excinfo:
            validate_vertex_env()
        assert all(name in str(excinfo.value) for name in _REQUIRED)

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param("", id="empty"),
            pytest.param("   ", id="whitespace-only"),
            pytest.param("\n", id="newline"),
        ],
    )
    def test_validate_vertex_env_on_a_blank_value_should_raise_value_error(self, clean_env, value):
        """A blank variable is set but useless — a distinct failure from being absent."""
        # Arrange
        for name in _REQUIRED:
            clean_env.setenv(name, "value")
        clean_env.setenv("VERTEXAI_PROJECT", value)

        # Act / Assert
        with pytest.raises(ValueError, match="defined but empty"):
            validate_vertex_env()

    def test_validate_vertex_env_should_not_check_that_the_credentials_file_exists(self, clean_env):
        """Documents current behaviour: only presence is checked, not resolvability."""
        # Arrange
        for name in _REQUIRED:
            clean_env.setenv(name, "value")
        clean_env.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/definitely/not/here.json")

        # Act / Assert - passes despite the path being bogus
        validate_vertex_env()


@pytest.mark.unit
class TestVertexValidationIsProviderScoped:
    """A caller on another provider must need neither the Vertex env nor the ``vertex`` extra."""

    @pytest.mark.parametrize("model_name", ["gpt-5", "openai/gpt-4o", "anthropic/claude-sonnet-5", "bedrock/llama"])
    def test_a_non_vertex_model_should_pass_with_no_vertex_environment(self, clean_env, model_name):
        # Act / Assert
        validate_vertex_env(model_name)

    @pytest.mark.parametrize("model_name", ["vertex_ai/gemini-2.5-flash", "VERTEX_AI/Gemini", "vertex_ai/anything"])
    def test_a_vertex_model_should_still_raise_on_a_missing_environment(self, clean_env, model_name):
        # Act / Assert
        with pytest.raises(OSError):
            validate_vertex_env(model_name)

    def test_no_model_name_should_validate_unconditionally(self, clean_env):
        # Act / Assert
        with pytest.raises(OSError):
            validate_vertex_env()

    def test_a_missing_google_auth_should_name_the_extra_rather_than_fail_inside_litellm(self, clean_env, monkeypatch):
        """Otherwise it surfaces as a litellm ImportError naming neither vgl nor the fix."""
        # Arrange
        for var in ("VERTEXAI_PROJECT", "VERTEXAI_LOCATION", "GOOGLE_APPLICATION_CREDENTIALS"):
            monkeypatch.setenv(var, "set")
        real_import = builtins.__import__

        def without_google_auth(name, *args, **kwargs):
            if name.startswith("google.auth"):
                raise ImportError("No module named 'google'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", without_google_auth)
        for module in [m for m in list(sys.modules) if m.startswith("google")]:
            monkeypatch.delitem(sys.modules, module, raising=False)

        # Act / Assert
        with pytest.raises(ImportError, match=r"vgl\[vertex\]"):
            validate_vertex_env("vertex_ai/gemini-2.5-flash")


@pytest.mark.unit
class TestIsVertexModel:
    @pytest.mark.parametrize(
        ("model_name", "expected"),
        [
            ("vertex_ai/gemini-2.5-flash", True),
            ("VERTEX_AI/gemini", True),
            ("gpt-5", False),
            ("gemini/gemini-2.5-flash", False),
            (None, False),
            ("", False),
        ],
    )
    def test_only_the_vertex_provider_prefix_should_match(self, model_name, expected):
        """``gemini/`` is the AI Studio path: an API key, no google.auth, no service account."""
        # Act / Assert
        assert is_vertex_model(model_name) is expected
