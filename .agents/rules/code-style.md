# Code Style

## Formatting & Linting

- **Ruff** is the formatter *and* linter. Do not use black, isort, or flake8.
- Line length: **160**. Target version: **py311**.
- **Pyright** for type checking (experimental features on; excludes `.venv`, `node_modules`,
  `__pycache__`). Run it as `uv run --all-extras --all-groups pyright` — the extras provide the
  optional-dependency imports (`google.auth`, `boto3`) so Pyright sees them.

Ruff config (`pyproject.toml`):

- **Selected:** `C4` (comprehensions), `E`/`F` (pycodestyle/pyflakes), `I` (isort),
  `PERF` (perflint), `UP` (pyupgrade).
- **Ignored:** `PERF203`.

## Python Style Conventions

- **Type hints on public function signatures.** Use modern PEP 604 syntax: **`X | None`,
  not `Optional[X]`**, and `X | Y` over `Union[X, Y]` — `UP` auto-rewrites the old forms.
- Module-level loggers via `logging.getLogger(__name__)` (logs land under the `bria_vgl` hierarchy), not ad-hoc `print`.
- Imports: standard library, then third-party, then local. Ruff's `I` rule orders them —
  don't order by hand.
- This is a **base library**: keep dependency floors as open lower bounds, floored at the
  oldest version whose API vgl actually uses. A hard pin becomes a resolution conflict for
  every consumer. See the commentary in `pyproject.toml`.

## Comments and docstrings

Keep them short. One line of non-obvious *why* is usually enough.

Do **not**:

- restate what the code says
- elaborate consequences, operational implications, or history
- cite benchmark numbers, measurements, or PR narrative beside the code

A non-obvious decision gets one line so the next person doesn't "correct" it. Everything else
belongs in the PR description or the commit message, not the source.

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/) — enforced by Commitizen
(commit-msg hook) and the `pr-title` workflow on PR titles.

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`,
`chore`, `revert`.

```
feat: Add Vertex AI fallback to the gateway
fix: Handle missing content-type in image downscale
```

> Commit/PR-title type drives release-please: `feat` → minor, `fix`/`perf` → patch. See
> `AGENTS.md` → Release.

## Pre-commit Pipeline

All code must pass pre-commit before committing. `fail_fast: true` — the run stops at the first
failing hook. Hooks:

1. **Gitleaks** — scans for secrets/credentials.
2. **Prettier** — formats YAML and JSON5 (prompt config dirs excluded; see `prompts` rule).
3. **Commitizen** (commit-msg stage) — enforces the message format.
4. **Ruff Format** — auto-formats Python.
5. **Ruff** — `check --fix --exit-non-zero-on-fix` (fails the commit when it fixes something,
   so re-stage and retry).
6. **Pyright** — `uv run --all-extras --all-groups pyright`.
7. **uv lock check** — `uv lock --check`, only when `pyproject.toml` / `uv.lock` change.

Install once: `uv pip install pre-commit && pre-commit install`.
Run manually: `uv run pre-commit run --all-files`.
