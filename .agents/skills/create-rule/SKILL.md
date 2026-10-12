---
name: create-rule
description: "Create or update an always-on agent rule in this repo, following the .agents convention. Use when adding a new coding guideline, convention, or constraint that should apply across Claude Code and Cursor. Triggers: add a rule, new rule, create-rule."
---

# Creating a rule

Rules are **always-on** — loaded into every agent context on startup. Use a rule for a
cross-cutting convention or constraint; use `create-skill` for on-demand, task-specific know-how.

## Where rules live

Rules are **canonical in `.agents/rules/<name>.md`**. Thin stubs in `.claude/rules/` and
`.cursor/rules/` point back here — never duplicate content.

```
.agents/rules/<name>.md      # rule content (source of truth)
.claude/rules/<name>.md      # Claude Code stub (one line)
.cursor/rules/<name>.mdc     # Cursor stub (frontmatter + @ reference)
```

## Writing the rule

Plain markdown, no frontmatter. Lead with the constraint directly.

```markdown
# Rule Title

One-sentence summary of what this rule enforces.

## Why

Brief rationale — helps agents apply the rule correctly in edge cases.

## Details / Examples

...
```

- Be **prescriptive**: "Always use X", not "X is preferred".
- Include a counter-example when the wrong approach is common.
- Keep it short — it's in every context window. Verify claims against the repo (`pyproject.toml`,
  `.pre-commit-config.yaml`, actual usage) before asserting them; a wrong rule is worse than no
  rule.

## Claude Code stub

Create `.claude/rules/<name>.md` with exactly:

```
Read and apply `.agents/rules/<name>.md`.
```

Claude Code auto-loads everything in `.claude/rules/`, so this one line pulls in the rule.

## Cursor stub

Create `.cursor/rules/<name>.mdc`:

```
---
description: <one sentence — what this rule enforces>
alwaysApply: <true for cross-cutting rules; false if glob-scoped>
globs: [<glob if alwaysApply is false, e.g. "src/vgl/**/prompts/**">]
---

@.agents/rules/<name>.md
```

Use `alwaysApply: true` for repo-wide concerns (style, testing). Use `alwaysApply: false` +
`globs` for path-scoped rules (e.g. the `prompts` rule).

## Checklist

1. Write `.agents/rules/<name>.md` — the rule content.
2. Write `.claude/rules/<name>.md` — one-line stub.
3. Write `.cursor/rules/<name>.mdc` — frontmatter + `@.agents/rules/<name>.md`.
4. Add a row to the **Rules** table in `AGENTS.md`.
