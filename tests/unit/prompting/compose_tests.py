"""Unit tests for composing a style preset's block into a base system prompt."""

import pytest

from bria_vgl.prompting import BLOCK_PREAMBLE, STYLE_PRESET_KEY, compose_system_prompt

A_BASE = "You are an art director. {llm_input_schema}"
A_BLOCK = "COLOR\n- Render colours fully saturated."
A_CONTEXT = {"llm_input_schema": "<<FIELD GUIDE>>", STYLE_PRESET_KEY: ""}


def _compose(base=A_BASE, block=A_BLOCK, context=None):
    return compose_system_prompt(base, block, A_CONTEXT if context is None else context)[0]


@pytest.mark.unit
class TestComposeIntoADeclaredSlot:
    """A prompt that names the slot decides where the block goes."""

    def test_should_put_the_block_where_the_slot_is(self):
        # Arrange
        base = "Intro.\n\n{style_preset_block}The JSON must contain:\n\n{llm_input_schema}"

        # Act
        composed = _compose(base=base)

        # Assert
        assert composed.index(A_BLOCK) < composed.index("The JSON must contain:")

    def test_should_keep_the_schema_after_the_block(self):
        # Arrange
        base = "Intro.\n\n{style_preset_block}The JSON must contain:\n\n{llm_input_schema}"

        # Act
        composed = _compose(base=base)

        # Assert
        assert composed.index(A_BLOCK) < composed.index("<<FIELD GUIDE>>")

    def test_should_render_the_slot_away_when_the_caller_supplies_no_block(self):
        """Left unfilled it would ship the literal placeholder to the model."""
        # Arrange
        from bria_vgl.prompting import render

        base = "Intro.\n\n{style_preset_block}The JSON must contain:"

        # Act
        rendered, _ = render(base, A_CONTEXT)

        # Assert
        assert rendered == "Intro.\n\nThe JSON must contain:"


@pytest.mark.unit
class TestComposeWithoutASlot:
    """A prompt that names no slot gets the block appended, the only safe place to guess."""

    def test_should_append_the_block(self):
        # Act
        composed = _compose()

        # Assert
        assert composed.endswith(A_BLOCK)

    def test_should_keep_the_base_prompt_intact(self):
        # Act
        composed = _compose()

        # Assert
        assert composed.startswith("You are an art director.")

    def test_should_separate_the_two_halves_by_a_blank_line(self):
        # Act
        composed = _compose()

        # Assert
        assert composed == f"You are an art director. <<FIELD GUIDE>>\n\n{BLOCK_PREAMBLE}\n\n{A_BLOCK}"


@pytest.mark.unit
class TestComposeSafety:
    def test_should_fill_the_bases_own_placeholders(self):
        # Act
        composed = _compose()

        # Assert
        assert "<<FIELD GUIDE>>" in composed

    @pytest.mark.parametrize(
        "base",
        [
            pytest.param(A_BASE, id="appended"),
            pytest.param("Intro.\n\n{style_preset_block}Tail. {llm_input_schema}", id="declared-slot"),
        ],
    )
    def test_should_not_substitute_a_placeholder_shaped_phrase_in_the_block(self, base):
        """A rule is authored prose, so a brace in it has to reach the model as itself."""
        # Act
        composed = _compose(base=base, block="TEXT\n- Never render {user_prompt} as lettering.")

        # Assert
        assert "{user_prompt}" in composed

    def test_should_report_a_placeholder_the_base_left_unfilled(self):
        # Act
        _, unfilled = compose_system_prompt("Intro. {aspect_ratio} {llm_input_schema}", A_BLOCK, A_CONTEXT)

        # Assert
        assert unfilled == frozenset({"aspect_ratio"})

    @pytest.mark.parametrize("block", [pytest.param("", id="empty"), pytest.param("   \n ", id="whitespace")])
    def test_should_reject_a_block_with_no_content(self, block):
        """An empty block means the preset resolved to nothing, which must not pass as unstyled."""
        # Act / Assert
        with pytest.raises(ValueError, match="empty"):
            _compose(block=block)

    @pytest.mark.parametrize(
        "base",
        [
            pytest.param(A_BASE, id="appended"),
            pytest.param("Intro.\n\n{style_preset_block}Tail. {llm_input_schema}", id="declared-slot"),
        ],
    )
    def test_should_introduce_the_block(self, base):
        """Unintroduced, the rules read as more of the base prompt rather than as instructions."""
        # Act
        composed = _compose(base=base)

        # Assert
        assert composed.index(BLOCK_PREAMBLE) < composed.index(A_BLOCK)

    def test_the_preamble_should_give_the_user_the_content_and_the_guidelines_the_look(self):
        """Agreed wording: a preset must not override what the user asked to see, only how it looks."""
        # Act / Assert
        assert BLOCK_PREAMBLE == (
            "Apply the following style guidelines to the scene you describe. The user's request decides "
            "what is in the scene; these guidelines decide how it looks, and override any default stated above."
        )

    def test_should_leave_the_preamble_out_when_no_preset_is_in_play(self):
        """It announces rules, so it must not appear on a call that carries none."""
        # Arrange
        from bria_vgl.prompting import render

        # Act
        rendered, _ = render("Intro.\n\n{style_preset_block}Tail.", A_CONTEXT)

        # Assert
        assert BLOCK_PREAMBLE not in rendered

    def test_should_reject_an_empty_base_prompt(self):
        # Act / Assert
        with pytest.raises(ValueError, match="empty base system prompt"):
            _compose(base="")
