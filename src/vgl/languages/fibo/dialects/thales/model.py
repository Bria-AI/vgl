from pydantic import Field

from vgl.languages.fibo.model import FiboVGL


class ThalesVGL(FiboVGL):
    """FIBO's VGL in the Thales dialect: no scores, and edits state their change."""

    edit_instruction: str | None = Field(None, description="A concise but clear description of the expected changes in the image.")
