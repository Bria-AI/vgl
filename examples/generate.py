"""Create a VGL from a prompt.

python examples/generate.py "a red fox in snow at dusk"
"""

import sys

import bria_vgl
from bria_vgl.dialects.thales import Generate

scene = bria_vgl.create(Generate(prompt=sys.argv[1]))
print(scene.model_dump_json(indent=2, exclude_none=True))
