import os

_VERTEX_ENV_VARS = ("VERTEXAI_PROJECT", "VERTEXAI_LOCATION", "GOOGLE_APPLICATION_CREDENTIALS")

#: Model ids routed through litellm's Vertex path, which is the only one needing the extra.
_VERTEX_PREFIX = "vertex_ai"


def is_vertex_model(model_name: str | None) -> bool:
    """Whether ``model_name`` goes through litellm's Vertex provider."""
    return bool(model_name) and _VERTEX_PREFIX in model_name.lower()


def validate_vertex_env(model_name: str | None = None):
    """Validate that Vertex is usable: the env vars are set, and ``vgl[vertex]`` is installed.

    Called with a resolved ``model_name`` it is a no-op for non-Vertex ids, so a caller on
    another provider needs neither the env nor the extra. Called with none it validates
    unconditionally.

    Raises OSError, ValueError, or ImportError if validation fails.
    """
    if model_name is not None and not is_vertex_model(model_name):
        return

    missing = [v for v in _VERTEX_ENV_VARS if v not in os.environ]
    if missing:
        raise OSError(f"Missing required environment variables: {', '.join(missing)}")

    empty = [v for v in _VERTEX_ENV_VARS if not os.environ.get(v, "").strip()]
    if empty:
        raise ValueError(f"The following environment variables are defined but empty: {', '.join(empty)}")

    # litellm imports google.auth to read GOOGLE_APPLICATION_CREDENTIALS but declares it only
    # under its own extras, so without this the failure is a litellm ImportError several frames
    # deep that names neither vgl nor the fix.
    try:
        import google.auth  # noqa: F401
    except ImportError as exc:
        raise ImportError(f"{model_name or 'Vertex'} needs google-auth, which vgl does not install by default. Run `pip install 'vgl[vertex]'`.") from exc
