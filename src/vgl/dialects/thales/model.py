from pydantic import Field

from vgl.model import VGL


class ThalesVGL(VGL):
    """The Thales dialect's VGL: no scores, and edits state their change."""

    edit_instruction: str | None = Field(None, description="A concise but clear description of the expected changes in the image.")
