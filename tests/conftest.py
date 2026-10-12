"""Fixtures shared across the vgl test suite."""

import pytest
from PIL import Image

from vgl.dialects.thales import ThalesVGL

#: A minimal VGL carrying every required field and nothing optional. Kept as a
#: dict so tests can mutate one field without restating the rest.
A_VGL: dict = {
    "short_description": "a red bear on a sofa",
    "background_setting": "a warm living room",
    "lighting": {"conditions": "dim indoor", "direction": "side-lit from left"},
    "aesthetics": {"composition": "rule of thirds", "color_scheme": "warm", "mood_atmosphere": "cosy"},
    "context": "an editorial photograph",
}


@pytest.fixture
def a_vgl_dict() -> dict:
    """The raw dict form, for tests that need to omit or corrupt a field."""
    return dict(A_VGL)


@pytest.fixture
def a_vgl() -> ThalesVGL:
    return ThalesVGL.model_validate(A_VGL)


@pytest.fixture
def another_vgl() -> ThalesVGL:
    """Differs from :func:`a_vgl` in one field, so a diff between them is non-empty."""
    return ThalesVGL.model_validate({**A_VGL, "short_description": "a blue bear on a sofa"})


@pytest.fixture
def an_image() -> Image.Image:
    return Image.new("RGB", (8, 8), "red")


@pytest.fixture
def another_image() -> Image.Image:
    """A second reference, distinguishable from :func:`an_image` by identity alone."""
    return Image.new("RGB", (8, 8), "blue")


@pytest.fixture
def a_mask() -> Image.Image:
    """Fully opaque, so compositing through it replaces the whole image."""
    return Image.new("L", (8, 8), 255)


@pytest.fixture
def vertex_env(monkeypatch):
    """Satisfy ``validate_vertex_env``, which every Vertex call checks."""
    monkeypatch.setenv("VERTEXAI_PROJECT", "test-project")
    monkeypatch.setenv("VERTEXAI_LOCATION", "us-central1")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/dev/null")
