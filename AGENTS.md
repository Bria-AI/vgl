# AGENTS.md

**VGL (Visual Generation Language)** — a base Python library that turns a prompt, or images plus
a prompt, into a structured JSON scene description for image models like FIBO. Source in
`src/vgl/`; the public API is `vgl.create` / `vgl.modify`.

Project rules live in `.agents/rules/`. Read and apply each:

- `.agents/rules/**`

## Environment

- Python **>=3.10** (supports 3.10–3.13; Ruff/Pyright target **py310**).
- Package manager: **`uv`**. Virtual env: `.venv` (run commands via `uv run` or `.venv/bin/python`).
- Credentials in `.env`. The default LLM is Gemini via Google AI Studio (`GEMINI_API_KEY`);
  Vertex and Bedrock are optional extras. See `README.md` → Authenticate.
- This is a **base library**: dependency floors stay open lower bounds — never hard-pin. See the
  `code-style` rule and the commentary in `pyproject.toml`.

## Agent Configuration

All agent rules and skills are canonical in `.agents/`. Thin stubs under `.claude/` (and
`.cursor/` for rules) point back here — never duplicate content.

```
.agents/
├── rules/    Always-on rules — loaded by all agents on startup
└── skills/   On-demand skills — loaded when relevant
```

| Tool | Rules | Skills |
|------|-------|--------|
| Claude Code | `.claude/rules/` stubs → `.agents/rules/` | `.claude/skills/` stubs → `.agents/skills/` |
| Cursor | `.cursor/rules/*.mdc` → `.agents/rules/` | auto-loaded from `.agents/skills/` |

### Rules (always-on)

| Rule | Enforces |
|------|----------|
| `code-style` | Ruff + Pyright, line length 160, comments/docstrings, Conventional Commits, pre-commit |
| `testing` | pytest layout/naming (`*_tests.py`), unit/integration markers, Arrange-Act-Assert, run tests after changes |
| `prompts` | Prompt files are data — never reformat them; `{name}` templating |

### Skills (on-demand — read the `SKILL.md` when the task matches)

| Skill | When to use |
|-------|-------------|
| `create-skill` | Add or update an agent skill (canonical in `.agents/`, stub in `.claude/`) |
| `create-rule` | Add or update an always-on rule (canonical in `.agents/`, stubs in `.claude/`/`.cursor/`) |

## Common commands

`uv` is the entry point for everything — it loads the right groups/extras for you.

| Command | What it does |
|---------|--------------|
| `uv sync --all-extras --all-groups` | Install the full dev environment |
| `uv run --dev pytest` | Run the offline test suite (`-m unit` / `-m integration` to select) |
| `uv run --dev ruff format` | Format Python |
| `uv run --dev ruff check --fix` | Lint and auto-fix |
| `uv run --all-extras --all-groups pyright` | Type-check |
| `uv run pre-commit run --all-files` | Run the full pre-commit pipeline |
| `uv run --group examples python tests/packaging/smoke_test.py` | **Live** smoke test — hits real LLMs; the release gate (not part of pytest) |

Adding dependencies: `uv add <pkg>` for a runtime dep; `uv add <pkg> --optional <extra>` for an
optional-provider extra (`vertex`, `bedrock`, `all`); `uv add <pkg> --group <group>` for a dev
group (`test`, `lint`, `examples`, `dev`). Never hand-edit `uv.lock`.

## Release

One artifact ships from this repo: the **`vgl` package → PyPI, via release-please.**

- `release-please.yml` runs on every push to `dev` and keeps a Release PR open. Merging that PR
  tags `vX.Y.Z` and publishes a GitHub release; `publish.yml` (on release published) builds with
  `uv build` and publishes to PyPI. Bump by landing Conventional Commits — **do not** hand-edit
  versions, tags, or the changelog.
- PR titles must follow Conventional Commits (`pr-title.yml` enforces; the type drives the
  version bump).
- Two workflows gate the release. **Release gate** builds the wheel, checks its contents
  (`tests/packaging/check_wheel.py`), and runs the live smoke test
  (`tests/packaging/smoke_test.py`); it is `workflow_dispatch`-only (the smoke test spends real
  tokens) — dispatch it on the `release-please--branches--dev` branch. **PR gate** runs on every
  PR and posts the required `packaging-gate` status: ordinary PRs pass instantly; the Release PR
  passes only once the Release gate has a green run for its head commit, and stays blocked until
  then (it re-evaluates automatically when Release gate finishes). Dispatching needs repo write
  access; add required reviewers to the `release-gate` environment to limit it to specific people.

`ci.yml` runs on every PR and on push to `dev`: `uv lock --check`, ruff, pyright, gitleaks, and pytest on Python 3.10–3.13. It is self-contained, since a public repo can't call the private `Bria-AI/github-workflows`.

See `CONTRIBUTING.md` for the source layout and the human-facing version of the above, and
`README.md` for the library's public API.
