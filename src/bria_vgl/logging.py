import logging

# None: each module logs under its own bria_vgl.* logger. set_logger() routes all of them to one.
_logger: logging.Logger | logging.LoggerAdapter | None = None


def set_logger(logger: logging.Logger | logging.LoggerAdapter | None) -> None:
    """Send all bria_vgl logging to `logger`. None restores the default bria_vgl.* loggers."""
    global _logger
    _logger = logger


class _Logger:
    """Resolves to the injected logger, else the named bria_vgl.* logger, on each use."""

    def __init__(self, name: str):
        self._name = name

    def __getattr__(self, attr):
        return getattr(_logger if _logger is not None else logging.getLogger(self._name), attr)


def get_logger(name: str) -> _Logger:
    return _Logger(name)
