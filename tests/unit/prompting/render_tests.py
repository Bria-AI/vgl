"""Unit tests for template rendering.

Rendering is where user-authored prompt text meets caller-supplied values, so it is the one place in the style system that absolutely must not raise: a store
record comes from a database row somebody typed into a form, and a malformed one has to degrade to visibly wrong output rather than a failed request.
"""

import pytest

from vgl.prompting import placeholders_in, render


@pytest.mark.unit
class TestRender:
    def test_render_should_substitute_a_supplied_placeholder(self):
        # Act
        text, unfilled = render("Scene: {user_prompt}", {"user_prompt": "a red bear"})

        # Assert
        assert text == "Scene: a red bear"
        assert unfilled == frozenset()

    def test_render_on_an_unsupplied_placeholder_should_leave_it_as_literal_text(self):
        """The alternative, substituting the word "None", reaches the model as an instruction.

        A visible ``{original_vgl}`` is greppable and obviously a bug to anyone reading the prompt; "None" reads as content.
        """
        # Act
        text, unfilled = render("Existing: {original_vgl}", {"user_prompt": "x"})

        # Assert
        assert text == "Existing: {original_vgl}"
        assert unfilled == frozenset({"original_vgl"})

    def test_render_on_a_none_value_should_treat_it_as_unsupplied(self):
        """Engines pass every template argument every time, most of them ``None``."""
        # Act
        text, unfilled = render("Diff: {diff_json}", {"diff_json": None})

        # Assert
        assert text == "Diff: {diff_json}"
        assert "None" not in text
        assert unfilled == frozenset({"diff_json"})

    def test_render_on_a_key_nothing_declared_anywhere_should_still_substitute_it(self):
        """The open-key-set guarantee, and the whole point of the design.

        Adding a new template input must be one line at the call site — no enum to extend, no registry to update, and nothing in this package to change.
        """
        # Act
        text, unfilled = render("Ratio: {aspect_ratio}", {"aspect_ratio": "16:9"})

        # Assert
        assert text == "Ratio: 16:9"
        assert unfilled == frozenset()

    @pytest.mark.parametrize(
        "template",
        [
            pytest.param('Example: {"a": 1}', id="inline-json"),
            pytest.param("Padded: { user_prompt }", id="padded-placeholder"),
            pytest.param("Lone: { open brace", id="lone-open-brace"),
            pytest.param("Lone: close brace }", id="lone-close-brace"),
            pytest.param("Set: {{nested}}", id="doubled-braces"),
            pytest.param("Dash: {user-prompt}", id="non-identifier"),
            pytest.param("Digit: {1st}", id="leading-digit"),
        ],
    )
    def test_render_should_pass_anything_that_is_not_an_identifier_placeholder_through_untouched(self, template):
        """``str.format_map`` raises ``ValueError`` on every one of these.

        That is fine for prompts authored in a reviewed pull request and unacceptable for prompts typed into a form: prose contains braces, and a JSON example
        in a prompt is a completely reasonable thing to write.
        """
        # Act
        text, _ = render(template, {"user_prompt": "a red bear"})

        # Assert
        assert text == template

    def test_render_should_report_only_identifier_placeholders_as_unfilled(self):
        """A padded placeholder is literal text, so it is a lint concern, not an unfilled value."""
        # Act
        _, unfilled = render("{ user_prompt } and {original_vgl}", {})

        # Assert
        assert unfilled == frozenset({"original_vgl"})

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            pytest.param(42, "42", id="int"),
            pytest.param(1.5, "1.5", id="float"),
            pytest.param(True, "True", id="bool"),
            pytest.param(["a"], "['a']", id="list"),
        ],
    )
    def test_render_should_coerce_non_string_values(self, value, expected):
        """So a call site can pass an aspect ratio or a seed without stringifying first."""
        # Act
        text, _ = render("V: {value}", {"value": value})

        # Assert
        assert text == f"V: {expected}"

    def test_render_should_substitute_every_occurrence_of_a_placeholder(self):
        # Act
        text, _ = render("{user_prompt} / {user_prompt}", {"user_prompt": "bear"})

        # Assert
        assert text == "bear / bear"

    @pytest.mark.parametrize(
        "template",
        [
            pytest.param("", id="empty"),
            pytest.param("{", id="single-open"),
            pytest.param("}", id="single-close"),
            pytest.param("{}", id="empty-braces"),
            pytest.param("{{{{", id="many-braces"),
            pytest.param("{a}{b}{c}", id="several-unknown"),
            pytest.param("{" * 500, id="pathological"),
        ],
    )
    def test_render_should_never_raise(self, template):
        """The central invariant. Resolution errors are lookups; content is never fatal."""
        # Act / Assert
        render(template, {})

    def test_render_should_not_re_expand_a_substituted_value(self):
        """A user prompt containing a brace must not be treated as a template itself.

        Otherwise a caller could inject a placeholder through their own prompt text and read back a value the engine never meant to expose.
        """
        # Act
        text, _ = render("{user_prompt}", {"user_prompt": "{llm_input_schema}", "llm_input_schema": "SECRET"})

        # Assert
        assert text == "{llm_input_schema}"
        assert "SECRET" not in text


@pytest.mark.unit
class TestPlaceholdersIn:
    def test_placeholders_in_should_find_identifier_placeholders(self):
        # Act
        found = placeholders_in("{user_prompt} then {original_vgl}")

        # Assert
        assert found == frozenset({"user_prompt", "original_vgl"})

    def test_placeholders_in_should_ignore_non_identifier_braces(self):
        """Used by the authoring lint, which must not flag a JSON example as a typo."""
        # Act
        found = placeholders_in('{"a": 1} and { user_prompt } and {user-prompt}')

        # Assert
        assert found == frozenset()

    def test_placeholders_in_on_a_template_with_none_should_return_empty(self):
        # Act
        found = placeholders_in("no placeholders here")

        # Assert
        assert found == frozenset()
