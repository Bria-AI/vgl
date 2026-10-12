---
name: create-skill
description: "Create or update an agent skill in this repo, following the .agents convention. Use when adding a new skill, editing an existing one, or wiring a skill into Claude Code and Cursor. Triggers: add a skill, new skill, create-skill."
---

# Creating a skill

## Where skills live

Skills are **canonical in `.agents/skills/<name>/SKILL.md`**. Thin stubs in `.claude/skills/`
point back here — never duplicate content. Cursor auto-loads from `.agents/skills/` directly, so
no `.cursor/skills/` stub is needed. See `AGENTS.md` → Agent Configuration.

## File structure

```
.agents/skills/<name>/SKILL.md    # canonical content (source of truth)
.claude/skills/<name>/SKILL.md    # Claude Code stub (frontmatter + one line)
```

## Frontmatter

```markdown
---
name: <kebab-case-name>
description: "<one sentence — WHEN to use this skill, starting with a verb. End with 'Triggers: ...' keywords.>"
---
```

The `description` is what an agent reads to decide whether to load the skill — be specific about
the trigger condition, not just the topic. It must be **identical** in the canonical file and the
stub.

## Writing good skill content

- Lead with the most-used action, not background theory.
- Use a code block for every command, file snippet, or config example.
- Include a checklist for multi-step workflows.
- Keep it scannable — agents read it under token pressure. Cut any bullet that adds no
  constraint or example.
- End with a short **Reference** list of the real files the skill points at.

## Claude Code stub

Create `.claude/skills/<name>/SKILL.md`:

```markdown
---
name: <name>
description: "<same description as the canonical skill>"
---

Full skill content: read `.agents/skills/<name>/SKILL.md`.
```

## Checklist

1. Write `.agents/skills/<name>/SKILL.md` — frontmatter + content.
2. Write `.claude/skills/<name>/SKILL.md` — stub with the identical `description`.
3. Add a row to the **Skills** table in `AGENTS.md`.
4. Nothing to do for Cursor — it loads `.agents/skills/` automatically.

To add an always-on rule instead of an on-demand skill, use the `create-rule` skill.
