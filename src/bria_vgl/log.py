import logging

# None: each module logs under its own bria_vgl.* logger. set_logger() routes all of them to one.
_logger: logging.Logger | logging.LoggerAdapter | None = None


def set_logger(logger: logging.Logger | logging.LoggerAdapter | None) -> None:
    """Send all bria_vgl logging to `logger`. None restores the default bria_vgl.* loggers."""
    global _logger
    _logger = logger


def get_logger(name: str) -> logging.Logger | logging.LoggerAdapter:
    return _logger if _logger is not None else logging.getLogger(name)
