"""Loading a payload's prompt pair and rendering it for one LLM call."""

import re
from collections.abc import Mapping
from pathlib import Path

from bria_vgl.exceptions import PromptNotFoundError
from bria_vgl.log import get_logger

SYSTEM_PROMPT_FILE = "system_prompt.txt"
FINAL_PROMPT_FILE = "final_prompt.txt"

#: The slot a system prompt declares for a style preset. Without it the preset is appended.
STYLE_PRESET_KEY = "style_preset_block"

#: Introduces the preset so it reads as instructions: the user's prompt owns the content, the preset owns the look.
BLOCK_PREAMBLE = (
    "Apply the following style guidelines to the scene you describe. The user's request decides "
    "what is in the scene; these guidelines decide how it looks, and override any default stated above."
)

#: Narrow on purpose: an inline JSON example, a padded ``{ user_prompt }`` or a lone brace stays literal.
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def render(template: str, context: Mapping[str, object]) -> tuple[str, frozenset[str]]:
    """Fill every placeholder ``context`` has a value for and leave the rest. Never raises.

    Returns the text and the unfilled placeholders. ``None`` counts as unsupplied.
    """
    unfilled: set[str] = set()

    def substitute(match: re.Match[str]) -> str:
        value = context.get(match.group(1))
        if value is None:
            unfilled.add(match.group(1))
            return match.group(0)
        return str(value)

    return _PLACEHOLDER.sub(substitute, template), frozenset(unfilled)


def placeholders_in(template: str) -> frozenset[str]:
    return frozenset(match.group(1) for match in _PLACEHOLDER.finditer(template))


def compose_system_prompt(base_template: str, style_preset: str, context: Mapping[str, object]) -> tuple[str, frozenset[str]]:
    """Render ``base_template`` with the preset in its slot, or appended if it has none.

    The preset is a render value, not template text, so a ``{name}`` in it reaches the model as is.
    """
    if not base_template.strip():
        raise ValueError("cannot compose onto an empty base system prompt")
    if not style_preset.strip():
        raise ValueError("style preset is empty, so the composed prompt would be unstyled")

    block = f"{BLOCK_PREAMBLE}\n\n{style_preset.strip()}"
    if f"{{{STYLE_PRESET_KEY}}}" in base_template:
        return render(base_template, {**context, STYLE_PRESET_KEY: f"{block}\n\n"})

    rendered, unfilled = render(base_template, context)
    return f"{rendered.rstrip()}\n\n{block}", unfilled


def _read(directory: Path, name: str) -> str:
    try:
        return directory.joinpath(name).read_text(encoding="utf-8")
    except OSError as missing:
        raise PromptNotFoundError(f"no {name} in {directory}") from missing


def render_prompts(
    directory: Path, context: Mapping[str, object], style_preset: str | None = None, system_template: str | None = None, final_template: str | None = None
) -> tuple[str, str]:
    """The system and final prompts in ``directory``, rendered with ``context``. ``system_template`` and ``final_template`` replace the files."""
    # Supplied even with no preset, so a prompt that declares the slot never ships it.
    full_context = {STYLE_PRESET_KEY: "", **context}
    if system_template is None:
        system_template = _read(directory, SYSTEM_PROMPT_FILE)

    if final_template is None:
        final_template = _read(directory, FINAL_PROMPT_FILE)

    if style_preset is None:
        system_prompt, system_unfilled = render(system_template, full_context)
    else:
        system_prompt, system_unfilled = compose_system_prompt(system_template, style_preset, full_context)
    final_prompt, final_unfilled = render(final_template, full_context)

    if unfilled := system_unfilled | final_unfilled:
        # Not an error: it renders as itself, visible and greppable.
        get_logger(__name__).warning("unfilled prompt placeholders %s in %s", sorted(unfilled), directory.name)
    return system_prompt, final_prompt
