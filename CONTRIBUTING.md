# Contributing

## Layout

```
src/vgl/
├── api.py            # create, modify
├── payload.py        # the base every dialect's payloads build on
├── prompting.py      # loads and renders a prompt pair, composes a style preset
├── gateway.py        # litellm call, retries, Gemini fallback
├── images.py         # mask burn-in, downscale, base64
├── vertex.py         # Vertex env check
├── exceptions.py, labels.py, log.py
└── languages/fibo/
    ├── model.py, payloads.py            # shared by FIBO dialects
    └── dialects/thales/
        ├── model.py, payloads.py
        ├── output_schema/, input_schema/
        └── prompts/<prompt>/system_prompt.txt, final_prompt.txt
```

## Prompts

Prompt templates fill any `{name}` they're given a value for and leave everything else as written, so a JSON example or a lone brace in prose never breaks rendering. An unfilled placeholder logs a warning. Prompt files are data: don't reformat them, because the bytes are what the model receives.

## Live smoke test

`uv run --group examples python tests/packaging/smoke_test.py` runs every payload against AI Studio and Vertex. Run it before a release — or dispatch the **Release gate** workflow, which runs it (plus the wheel check) and, via the PR gate, is required before the release PR can merge (see Releasing).

> ### Run:
> * uv pip install pre-commit
> * pre-commit install

> ### Tests:
> * run them with: uv run --dev pytest
> * place tests under `tests/`, in a category subdir (`tests/unit/`), mirroring the source layout
> * keep them out of `src/` — the wheel ships `src/**/*`, so tests placed there are published
> * test file name should follow: *_tests.py
> * group tests in a `Test`-prefixed class, one class per file
> * name tests: test_\<what\>_on_\<condition\>_should_\<expected\>, dropping _on_\<condition\> when there is no meaningful condition
> * follow Arrange-Act-Assert, marking the three sections with comments
> * unit tests must run offline — no network, no databases, no LLM calls
> * mark every test class with `@pytest.mark.unit` or `@pytest.mark.integration`:
>   * `unit` — isolated, no I/O beyond `tmp_path` and the bundled package data
>   * `integration` — several real components together, still offline (e.g. rendering the bundled prompt files)
>   * select with `uv run --dev pytest -m unit`; an unmarked test is missed by both
> * shared fixtures (`a_vgl`, `an_image`, `a_mask`, `vertex_env`, …) live in `tests/conftest.py`
> * a test pinning a known bug should be `@pytest.mark.xfail(strict=True, reason=...)` — it then fails
>   loudly once the bug is fixed, prompting whoever fixed it to turn it into a real assertion

> ### adding packages
> common packages that need to be installed every time:
> 
>   > uv add [my-package]
>
> grouped dependencies:
> 
>   > uv add [my-package] --optional all  
>   > uv add [my-package] --optional [my-group]
>

## Releasing

PR titles follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, …), since release-please builds the version bump and the changelog from them. It keeps a release PR open on `dev`; merging it cuts the release.

Two workflows gate the release:

- **Release gate** — builds the wheel, checks its contents, and runs the live smoke test. It's `workflow_dispatch`-only (the smoke test spends real tokens, so it never runs on a commit). Dispatch it on the `release-please--branches--dev` branch. Who can run it: dispatching needs repo write access; add required reviewers to the `release-gate` environment to narrow it to specific people.
- **PR gate** — the cheap `packaging-gate` check that runs on every PR and is required by `dev`'s branch protection. Ordinary PRs pass instantly; the release PR passes only once the Release gate has a green run for its head commit, and stays blocked until then. It re-evaluates automatically when the Release gate finishes.

So: when the release PR is ready, dispatch the Release gate on its branch; once it's green the PR gate flips to passing and the PR can merge.
