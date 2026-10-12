"""Edit the masked area of an image. White in the mask is the area to change.

python examples/edit_with_mask.py "replace it with a cat" room.jpg mask.png
"""

import sys

from PIL import Image

import vgl
from vgl.dialects.thales import EditImageWithMask

prompt, image_path, mask_path = sys.argv[1:]
scene = vgl.modify(EditImageWithMask(prompt=prompt, image=Image.open(image_path), mask=Image.open(mask_path)))
print(scene.model_dump_json(indent=2, exclude_none=True))
