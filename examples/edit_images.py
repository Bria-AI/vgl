"""Edit from 1 to 4 images. The prompt refers to them as <image_1> to <image_4>.

python examples/edit_images.py "make it night" room.jpg
python examples/edit_images.py "put the lamp from <image_2> in <image_1>" room.jpg lamp.jpg
"""

import sys

from PIL import Image

import vgl
from vgl.dialects.thales import EditImages

prompt, *paths = sys.argv[1:]
scene = vgl.modify(EditImages(prompt=prompt, images=[Image.open(path) for path in paths]))
print(scene.model_dump_json(indent=2, exclude_none=True))
