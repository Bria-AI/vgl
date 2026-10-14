# Prompt Files Are Data

Prompt templates (`src/bria_vgl/**/prompts/**/*.txt` and the prompt/schema config dirs) are the
exact bytes the model receives. **Never reformat them** — no prettier, no editor auto-format,
no re-indenting, no "cleaning up" whitespace or JSON examples inside them.

## Why

The rendered prompt is the model's input. A reformat that looks harmless (reflowed JSON,
trimmed trailing space, normalized quotes) changes what the model sees and silently shifts
output quality. These paths are excluded from Prettier and Ruff for exactly this reason — keep
them that way.

## Templating

- Templates fill any `{name}` they're given a value for and **leave everything else as
  written**, so a JSON example or a lone brace in prose renders untouched.
- An **unfilled placeholder logs a warning** — don't silence it; it means a value wasn't
  passed, which is usually the bug.

## When editing prompt content deliberately

- Edit the text itself; don't let a tool touch its formatting.
- If you add a new `{placeholder}`, wire its value through `prompting.py` and confirm no
  warning fires.
