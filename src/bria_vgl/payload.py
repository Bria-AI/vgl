"""The base every dialect's payloads build on. A payload decides its dialect, prompt, and VGL model."""

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Generic, TypeVar

from boltons.iterutils import remap
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from bria_vgl.exceptions import InvalidResponseError
from bria_vgl.gateway import ThinkingLevel
from bria_vgl.model import VGL

T = TypeVar("T", bound=VGL)


@dataclass(frozen=True)
class Request:
    """One LLM call, ready to render and send."""

    prompts: Path
    context: dict[str, object]
    response_schema: dict
    images: Sequence[Image.Image] = field(default_factory=tuple)
    temperature: float = 0.2
    #: Replaces the system prompt template in ``prompts``; its placeholders are still filled.
    system_prompt: str | None = None
    #: Replaces the final prompt template in ``prompts``; its placeholders are still filled.
    final_prompt: str | None = None
    #: Gemini 3+ only. None keeps thinking off.
    thinking_level: ThinkingLevel | str | None = None
    #: Thinking tokens count against this on Gemini.
    max_output_tokens: int = 7000


def _is_filled(_path, _key, value) -> bool:
    return not (value is None or value in ("", [], {}) or (isinstance(value, float) and math.isnan(value)))


def _drop_textless_renders(reply: object) -> object:
    """The model sometimes lists an element "without text" as a text render with empty text; that's no text render."""
    if isinstance(reply, dict) and isinstance(reply.get("text_render"), list):
        renders = [render for render in reply["text_render"] if not isinstance(render, dict) or "text" in render]
        reply = {**reply, "text_render": renders or None}
    return reply


class Payload(BaseModel, Generic[T]):
    """A prompt in, the dialect's VGL model out."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    #: True for payloads that go to ``bria_vgl.create``; False for ``bria_vgl.modify`` only.
    creates: ClassVar[bool] = False
    #: True for a creating payload that ``bria_vgl.modify`` also accepts.
    modifies: ClassVar[bool] = False
    #: The dialect's VGL model, which ``parse`` validates against.
    vgl_model: ClassVar[type[VGL]]

    prompt: str = Field(min_length=1)

    def to_request(self) -> Request:
        raise NotImplementedError

    def parse(self, text: str) -> T:
        """Drop empty values the model returned, then validate. Fields outside ``vgl_model`` are dropped."""
        try:
            return self.vgl_model.model_validate(_drop_textless_renders(remap(json.loads(text), visit=_is_filled)))  # type: ignore[return-value]
        except (json.JSONDecodeError, TypeError, ValidationError) as invalid:
            raise InvalidResponseError(f"reply isn't a valid {self.vgl_model.__name__}: {invalid}") from invalid


def vgl_json(vgl: VGL) -> str:
    """A VGL as it goes into a prompt: no empty fields, ``json.dumps`` spacing like the prompts were tuned on."""
    return json.dumps(vgl.model_dump(exclude_none=True))
