# Testing Rules

## Running tests

```bash
uv run --dev pytest            # all tests (testpaths = tests)
uv run --dev pytest -m unit    # unit only
uv run --dev pytest -m integration
```

- `log_cli` is on. Test discovery is `*_tests.py` (not `test_*.py`), `testpaths = ["tests"]`.
- Tooling: `pytest` and the pytest ecosystem only — **never `unittest`**.

## Categories & layout

- Tests are **unit** or **integration**, and **both must run offline** — no network, no
  database, no LLM calls.
  - `unit` — isolated, no I/O beyond `tmp_path` and the bundled package data.
  - `integration` — several real components together, still offline (e.g. rendering the
    bundled prompt files).
- **Mark every test class** with `@pytest.mark.unit` or `@pytest.mark.integration` — an
  unmarked test is missed by both `-m` selectors. Don't add unregistered markers (they are
  declared in `pyproject.toml`).
- Organize under `tests/<category>/…`, **mirroring the source layout**.
- Keep tests **out of `src/`** — the wheel ships `src/**/*`, so tests placed there get
  published. Avoid splitting into too many tiny files.

## Conventions

- Group tests in a **`Test`-prefixed class, one class per file**.
- Name tests `test_<what>_on_<condition>_should_<expected>`; drop `_on_<condition>` when
  there is no meaningful condition.
- **One behaviour per test** (multiple `assert`s are fine if they verify one behaviour); no
  redundant tests whose passing is already implied by a stronger one.
- Follow **Arrange-Act-Assert**, marking the three sections with comments:
  ```python
  def test_something():
      # Arrange - set up test data and dependencies

      # Act - perform the action being tested

      # Assert - verify the expected outcome
  ```
- A test pinning a known bug is `@pytest.mark.xfail(strict=True, reason=...)` — it fails loudly
  once the bug is fixed, prompting whoever fixed it to turn it into a real assertion.
- Shared fixtures (`a_vgl`, `an_image`, `a_mask`, `vertex_env`, …) live in `tests/conftest.py`.
- Docstrings only when the *why* isn't obvious from the name (see the `code-style` rule).

## After making changes

After any code change (feature, fix, refactor) you **MUST**:

1. Run the relevant offline tests and fix any failures before considering the work complete:
   ```bash
   uv run --dev pytest
   ```
2. Run pre-commit: `uv run pre-commit run --all-files`.

**Exceptions** — you may skip running tests when the change is documentation-only, is to test
files themselves, or the user explicitly asks you to skip.

> The **live smoke test** (`uv run --group examples python tests/packaging/smoke_test.py`) hits
> real LLMs and is **not** part of the pytest run (it has no `unit`/`integration` marker) — it's
> the release gate. See `AGENTS.md` → Release.
