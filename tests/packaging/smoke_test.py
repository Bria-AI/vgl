"""Live smoke test: every payload against real LLMs. The release gate; not part of the pytest run.

    uv run --group examples python tests/packaging/smoke_test.py               # AI Studio and Vertex
    uv run --group examples python tests/packaging/smoke_test.py gemini/gemini-3.5-flash

AI Studio needs GEMINI_API_KEY; Vertex needs VERTEXAI_PROJECT, VERTEXAI_LOCATION and GOOGLE_APPLICATION_CREDENTIALS.
Exits non-zero if any call fails or returns an invalid VGL.
"""

import sys
import time

from dotenv import load_dotenv
from PIL import Image, ImageDraw

import vgl
from vgl.dialects.thales import EditImages, EditImageWithMask, Generate, ThalesVGL

LLMS = ["gemini/gemini-3.5-flash", "vertex_ai/gemini-3.5-flash"]


def _scene(background: str, shape: str) -> Image.Image:
    """A drawn image, so the script needs no assets."""
    image = Image.new("RGB", (768, 512), background)
    ImageDraw.Draw(image).ellipse((256, 128, 512, 384), fill=shape)
    return image


def _cases(scene: ThalesVGL) -> list[tuple[str, EditImages | EditImageWithMask]]:
    room, ball = _scene("lightblue", "red"), _scene("white", "green")
    mask = Image.new("L", room.size, 0)
    ImageDraw.Draw(mask).ellipse((256, 128, 512, 384), fill=255)
    return [
        ("edit one image", EditImages(prompt="make it night", images=[room])),
        ("edit one image with its VGL", EditImages(prompt="make it night", images=[room], input_image_vgl=scene)),
        ("edit two images", EditImages(prompt="put the ball from <image_2> into <image_1>", images=[room, ball])),
        ("edit two images with a VGL", EditImages(prompt="put the ball from <image_2> into <image_1>", images=[room, ball], input_image_vgl=scene)),
        ("edit with a mask", EditImageWithMask(prompt="replace it with a cat", image=room, mask=mask)),
        ("edit with a mask and a VGL", EditImageWithMask(prompt="replace it with a cat", image=room, mask=mask, input_image_vgl=scene)),
    ]


def _check(name: str, run, *, edit: bool = False) -> ThalesVGL | None:
    start = time.perf_counter()
    try:
        result = run()
        assert isinstance(result, ThalesVGL), f"got {type(result).__name__}"
        assert not edit or result.edit_instruction, "no edit_instruction"
    except Exception as error:
        print(f"  FAIL  {name}: {type(error).__name__}: {error}")
        return None
    print(f"  ok    {name} ({time.perf_counter() - start:.1f}s)")
    return result


def smoke(llm: str) -> bool:
    print(llm)
    scene = _check("create", lambda: vgl.create(Generate(prompt="a red ball in a light blue room"), llm=llm))
    styled = _check("create with a style preset", lambda: vgl.create(Generate(prompt="a red ball"), llm=llm, style_preset_prompt="Muted film colours."))
    if scene is None:
        print("  skip  edits: create failed, so there's no VGL to pass")
        return False
    edits = [_check(name, lambda payload=payload: vgl.modify(payload, llm=llm), edit=True) for name, payload in _cases(scene)]
    return styled is not None and None not in edits


if __name__ == "__main__":
    load_dotenv()
    results = [smoke(llm) for llm in sys.argv[1:] or LLMS]
    sys.exit(0 if all(results) else 1)
