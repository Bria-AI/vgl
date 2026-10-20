"""Locks vgl's public surface so a symbol can't silently leak into (or vanish from) it.

The published package's importable names are its contract; this pins the three surfaces we
curate by hand. A deliberate change updates the expected set here, in the same commit.
"""

import pytest

import bria_vgl
from bria_vgl import exceptions
from bria_vgl.dialects import thales


@pytest.mark.unit
class TestPublicApi:
    def test_top_level_exports_exactly_the_core_verbs(self):
        # Arrange
        expected = {"__version__", "DEFAULT_LLM", "ThinkingLevel", "create", "modify"}

        # Act / Assert
        assert set(bria_vgl.__all__) == expected
        assert all(hasattr(bria_vgl, name) for name in expected)

    def test_exceptions_module_exports_exactly_the_error_hierarchy(self):
        # Arrange
        expected = {
            "VGLError",
            "MaxTokensError",
            "ContentFilterError",
            "PromptNotFoundError",
            "LLMError",
            "AuthenticationError",
            "RateLimitError",
            "InvalidResponseError",
        }

        # Act / Assert
        assert set(exceptions.__all__) == expected
        assert all(issubclass(getattr(exceptions, name), exceptions.VGLError) for name in expected)

    def test_thales_dialect_exports_exactly_its_payloads_and_model(self):
        # Arrange
        expected = {"Generate", "Inspire", "Caption", "Refine", "EditImages", "EditImageWithMask", "ThalesVGL"}

        # Act / Assert
        assert set(thales.__all__) == expected
        assert all(hasattr(thales, name) for name in expected)
