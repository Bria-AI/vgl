import json
import math
from typing import ClassVar

from boltons.iterutils import remap
from pydantic import Field, ValidationError

from vgl.exceptions import InvalidResponseError
from vgl.languages.fibo.model import FiboVGL
from vgl.payload import Payload, T


def _is_filled(_path, _key, value) -> bool:
    return not (value is None or value in ("", [], {}) or (isinstance(value, float) and math.isnan(value)))


class FiboPayload(Payload[T]):
    """Shared by FIBO dialects: a prompt in, the dialect's VGL model out."""

    #: The dialect's VGL model, which ``parse`` validates against.
    vgl_model: ClassVar[type[FiboVGL]]

    prompt: str = Field(min_length=1)

    def parse(self, text: str) -> T:
        """Drop empty values the model returned, then validate."""
        try:
            return self.vgl_model.model_validate(remap(json.loads(text), visit=_is_filled))  # type: ignore[return-value]
        except (json.JSONDecodeError, TypeError, ValidationError) as invalid:
            raise InvalidResponseError(f"reply isn't a valid {self.vgl_model.__name__}: {invalid}") from invalid


def vgl_json(vgl: FiboVGL) -> str:
    """A VGL as it goes into a prompt: no empty fields, ``json.dumps`` spacing like the prompts were tuned on."""
    return json.dumps(vgl.model_dump(exclude_none=True))
