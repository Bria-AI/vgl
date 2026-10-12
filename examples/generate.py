"""Create a VGL from a prompt.

python examples/generate.py "a red fox in snow at dusk"
"""

import sys

import vgl
from vgl.dialects.thales import Generate

scene = vgl.create(Generate(prompt=sys.argv[1]))
print(scene.model_dump_json(indent=2, exclude_none=True))
