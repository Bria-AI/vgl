"""The Thales payloads. Each one maps to a prompt in ``prompts/`` and returns a ThalesVGL."""

import json
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import ClassVar

from PIL import Image
from pydantic import Field, model_validator

from bria_vgl.dialects.thales.model import ThalesVGL
from bria_vgl.payload import Payload, Request, vgl_json
from bria_vgl.utils.images import apply_gray_mask

_DIALECT = Path(__file__).parent
_PROMPTS = _DIALECT / "prompts"


@cache
def _input_schema(name: str) -> str:
    """The field guide that fills ``{llm_input_schema}``."""
    return (_DIALECT / "input_schema" / f"{name}.txt").read_text(encoding="utf-8")


@cache
def _output_schema(name: str) -> dict:
    return json.loads((_DIALECT / "output_schema" / f"{name}.json").read_text(encoding="utf-8"))


class ThalesPayload(Payload[ThalesVGL]):
    vgl_model: ClassVar = ThalesVGL


class Generate(ThalesPayload):
    """A new VGL from a prompt."""

    creates: ClassVar[bool] = True

    def to_request(self) -> Request:
        return Request(
            prompts=_PROMPTS / "generate",
            context={"user_prompt": self.prompt, "llm_input_schema": _input_schema("generate")},
            response_schema=_output_schema("generate"),
            temperature=0.2,
        )


class Inspire(ThalesPayload):
    """A new VGL from a prompt, with one image as a visual reference only: the VGL describes the prompt's scene, not the image.

    The image is sent as an RGB JPEG, downscaled to about 0.26 MP if larger, keeping its aspect ratio.
    """

    creates: ClassVar[bool] = True
    image: Image.Image

    def to_request(self) -> Request:
        return Request(
            prompts=_PROMPTS / "inspire",
            context={"user_prompt": self.prompt, "llm_input_schema": _input_schema("inspire")},
            response_schema=_output_schema("generate"),
            temperature=0.2,
            images=(self.image,),
        )


class Caption(ThalesPayload):
    """A new VGL that describes one image itself. Takes no prompt.

    The image is sent as an RGB JPEG, downscaled to about 0.26 MP if larger, keeping its aspect ratio.
    """

    creates: ClassVar[bool] = True
    prompt: None = None  # type: ignore[assignment]  # no prompt
    image: Image.Image

    def to_request(self) -> Request:
        return Request(
            prompts=_PROMPTS / "caption",
            context={"llm_input_schema": _input_schema("inspire")},
            response_schema=_output_schema("generate"),
            temperature=0.2,
            images=(self.image,),
        )


class Refine(ThalesPayload):
    """An existing VGL changed by a prompt, with no images. The prompt asks the model to keep the fields it doesn't affect."""

    input_vgl: ThalesVGL

    def to_request(self) -> Request:
        return Request(
            prompts=_PROMPTS / "refine",
            # inspire's schema: the one refine had before it was dropped, without generate's diversity wording.
            context={"user_prompt": self.prompt, "llm_input_schema": _input_schema("inspire"), "input_vgl": vgl_json(self.input_vgl)},
            response_schema=_output_schema("generate"),
            temperature=0.2,
        )


class _Edit(ThalesPayload):
    #: The VGL of the first image. With it, the ``_input_vgl`` prompts treat it as the baseline; without, the images are the only source.
    input_image_vgl: ThalesVGL | None = None

    def _edit_request(self, prompt: str, input_schema: str, images: Sequence[Image.Image]) -> Request:
        context: dict[str, object] = {"user_prompt": self.prompt, "llm_input_schema": _input_schema(input_schema)}
        # Every edit prompt has an _input_vgl twin that takes the input image's VGL as its baseline.
        if self.input_image_vgl is not None:
            prompt = f"{prompt}_input_vgl"
            context["input_image_vgl"] = vgl_json(self.input_image_vgl)
        return Request(prompts=_PROMPTS / prompt, context=context, response_schema=_output_schema("edit"), images=tuple(images))


class EditImages(_Edit):
    """Edit from 1 to 4 images. The prompt refers to them as ``<image_1>`` to ``<image_N>``, in list order.

    Each image is sent as an RGB JPEG, downscaled to about 0.26 MP if larger, keeping its aspect ratio.
    """

    images: list[Image.Image] = Field(min_length=1, max_length=4)

    def to_request(self) -> Request:
        if len(self.images) == 1:
            return self._edit_request("edit_image", "edit", self.images)
        return self._edit_request("edit_multi_images", "edit_multi_ref", self.images)


class EditImageWithMask(_Edit):
    """Edit the masked area of one image. White in the mask is the area to change; the mask must match the image's size.

    The mask is painted mid-grey into the image, which is then sent like any other: RGB JPEG, downscaled to
    about 0.26 MP if larger. So the mask is always resized exactly with its image.
    """

    image: Image.Image
    mask: Image.Image

    @model_validator(mode="after")
    def _mask_matches_image(self) -> "EditImageWithMask":
        if self.mask.size != self.image.size:
            raise ValueError(f"mask is {self.mask.size} but image is {self.image.size}; they must match")
        return self

    def to_request(self) -> Request:
        return self._edit_request("edit_image_mask", "inpaint", [apply_gray_mask(self.image, self.mask)])
