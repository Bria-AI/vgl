"""Edit an image with the VGL it was generated from, so the edit keeps what the prompt doesn't change.

python examples/edit_with_vgl.py "make it night" room.jpg room_vgl.json
"""

import sys
from pathlib import Path

from PIL import Image

import vgl
from vgl.dialects.thales import EditImages, ThalesVGL

prompt, image_path, vgl_path = sys.argv[1:]
input_image_vgl = ThalesVGL.model_validate_json(Path(vgl_path).read_text())
scene = vgl.modify(EditImages(prompt=prompt, images=[Image.open(image_path)], input_image_vgl=input_image_vgl))
print(scene.model_dump_json(indent=2, exclude_none=True))
