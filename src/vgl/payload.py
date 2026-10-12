"""The base every dialect's payloads build on. A payload decides its dialect, prompt, and VGL model."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Generic, TypeVar

from PIL import Image
from pydantic import BaseModel, ConfigDict

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class Request:
    """One LLM call, ready to render and send."""

    prompts: Path
    context: dict[str, object]
    response_schema: dict
    images: Sequence[Image.Image] = field(default_factory=tuple)
    temperature: float = 0.2


class Payload(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    #: True for payloads that go to ``vgl.create``; False for ``vgl.modify``.
    creates: ClassVar[bool] = False

    def to_request(self) -> Request:
        raise NotImplementedError

    def parse(self, text: str) -> T:
        raise NotImplementedError
