"""Every Thales payload renders its bundled prompts with nothing left unfilled."""

import logging

import pytest
from PIL import Image

from bria_vgl.dialects.thales import Caption, EditImages, EditImageWithMask, Generate, Inspire, Refine, ThalesVGL
from bria_vgl.prompting import render_prompts

_IMAGE = Image.new("RGB", (8, 8), "red")
_MASK = Image.new("L", (8, 8), 255)
_VGL = ThalesVGL.model_validate(
    {
        "short_description": "a red bear",
        "background_setting": "a room",
        "lighting": {"conditions": "dim", "direction": "side"},
        "aesthetics": {"composition": "centered", "color_scheme": "warm", "mood_atmosphere": "cosy"},
        "context": "a photo",
    }
)

PAYLOADS = [
    Generate(prompt="a fox"),
    Inspire(prompt="the same fox at night", image=_IMAGE),
    Caption(image=_IMAGE),
    Refine(prompt="make it night", input_vgl=_VGL),
    EditImages(prompt="make it night", images=[_IMAGE]),
    EditImages(prompt="put <image_2> on <image_1>", images=[_IMAGE, _IMAGE]),
    EditImageWithMask(prompt="a cat", image=_IMAGE, mask=_MASK),
    EditImages(prompt="make it night", images=[_IMAGE], input_image_vgl=_VGL),
    EditImages(prompt="put <image_2> on <image_1>", images=[_IMAGE, _IMAGE], input_image_vgl=_VGL),
    EditImageWithMask(prompt="a cat", image=_IMAGE, mask=_MASK, input_image_vgl=_VGL),
]


@pytest.mark.integration
class TestBundledPrompts:
    @pytest.mark.parametrize("payload", PAYLOADS, ids=lambda p: p.to_request().prompts.name)
    def test_should_render_with_every_placeholder_filled(self, payload, caplog):
        request = payload.to_request()
        with caplog.at_level(logging.WARNING, logger="bria_vgl"):
            system_prompt, final_prompt = render_prompts(request.prompts, request.context)
        assert "unfilled" not in caplog.text
        assert system_prompt.strip() and final_prompt.strip()
        assert (payload.prompt or "") in final_prompt

    def test_every_bundled_prompt_should_be_reachable(self):
        from bria_vgl.dialects.thales.payloads import _PROMPTS

        bundled = {entry.name for entry in _PROMPTS.iterdir() if entry.is_dir()}
        assert bundled == {p.to_request().prompts.name for p in PAYLOADS}
