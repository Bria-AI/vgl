from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("vgl")
except PackageNotFoundError:  # run from a source checkout without installing
    __version__ = "0.0.0"
