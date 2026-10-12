## Description

<!-- What does this change do, and why? -->

## Type of Change

<!--
The PR *title* must be a Conventional Commit — it drives the release-please version bump and
changelog. Tick the type that matches your title.
-->

- [ ] `feat`: New feature (minor bump)
- [ ] `fix`: Bug fix (patch bump)
- [ ] `docs`: Documentation only
- [ ] `refactor`: Code change that neither fixes a bug nor adds a feature
- [ ] `test`: Adding or updating tests
- [ ] `chore` / `ci`: Maintenance or CI/CD changes

## Checklist

- [ ] My PR title follows [Conventional Commits](https://www.conventionalcommits.org/) (enforced by the **Validate PR Title** check)
- [ ] `uv run --dev ruff format` and `uv run --dev ruff check --fix` are clean
- [ ] `uv run --all-extras --all-groups pyright` passes
- [ ] `uv run --dev pytest` passes, and I added/updated tests for my change
- [ ] Any new dependency uses an open lower bound (`>=`) — this is a base library, never hard-pin (see `pyproject.toml`)
- [ ] I did not hand-edit versions, tags, or the changelog — release-please owns those

## Related Issues

<!-- Link related issues: "Fixes #123" or "Relates to #123" -->
