# Logging

Log through the injectable module logger, with a constant message and the data in `extra`.

## Why

Consumers either configure the `bria_vgl.*` loggers or inject their own logger or `LoggerAdapter` with
`bria_vgl.set_logger()`, and ship records as structured JSON. A constant message groups and greps;
fields in `extra` become queryable attributes.

## Rules

- **One module-level logger:** `logger = get_logger(__name__)` from `bria_vgl.logging`. Never
  `logging.getLogger(...)` in library code, never `print`. The proxy resolves at each call, so a
  later `set_logger()` still applies and records keep the real call site.
- **Constant message, data in `extra`.** No `%s` args or f-strings in the message.

  ```python
  logger.info("LLM call", extra={"model": model, "duration_seconds": 1.204})   # yes
  logger.info("LLM call to %s took %.3fs", model, seconds)                     # no
  logger.info(f"LLM call to {model}")                                          # no
  ```

- **Field names:** snake_case; units in the name (`duration_seconds`, `delay_seconds`); reuse
  existing keys (`model`, `error`, `attempt`, `fallback`) before inventing one. Values are
  JSON-friendly: str, number, bool, list. An exception goes in as `type(exc).__name__` or `str(exc)`.
- **Never use reserved `LogRecord` names** as keys (`message`, `msg`, `args`, `name`, `filename`,
  `module`, `lineno`, …) — `logging` raises `KeyError`.
- **Levels:** `info` for routine telemetry (call timings), `warning` for a degraded path the call
  survives (retry, fallback, dropped option). Raise instead of logging an error; the caller decides.
- **Tests** assert on `record.<field>` and `record.message`, not on formatted `caplog.text` where a
  field matters.
