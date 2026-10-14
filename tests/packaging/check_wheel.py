"""Fail if a built wheel is missing any of vgl's data files (prompts, schemas, py.typed).

uv build --wheel && python tests/packaging/check_wheel.py dist/bria_vgl-*.whl
"""

import subprocess
import sys
import zipfile

wheel = sys.argv[1]
tracked = subprocess.run(["git", "ls-files", "src/bria_vgl"], capture_output=True, text=True, check=True).stdout.split()
expected = {path.removeprefix("src/") for path in tracked}
missing = sorted(expected - set(zipfile.ZipFile(wheel).namelist()))
if missing:
    sys.exit("missing from the wheel:\n" + "\n".join(missing))
print(f"ok: all {len(expected)} files are in {wheel}")
