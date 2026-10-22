import json

import pytest

import bria_vgl
from bria_vgl import exceptions, gateway
from bria_vgl.dialects.thales import EditImages, Generate, ThalesVGL

SCENE_FIELDS = ("background_setting", "lighting", "aesthetics", "context")


@pytest.fixture(autouse=True)
def gemini_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")


@pytest.fixture
def a_valid_reply(a_vgl_dict) -> str:
    return json.dumps({**a_vgl_dict, "edit_instruction": "made it night"})


@pytest.fixture
def a_reply_without_the_scene(a_vgl_dict) -> str:
    """How a model that won't depict a prompt tends to answer: JSON with the scene left out."""
    return json.dumps({**{key: value for key, value in a_vgl_dict.items() if key not in SCENE_FIELDS}, "edit_instruction": "remove it"})


def _answer(monkeypatch, *replies) -> list[dict]:
    """Answers the gateway's calls in turn, with a reply's text or by raising an error. Returns each call's arguments."""
    calls: list[dict] = []
    remaining = list(replies)

    def fake_call(**kwargs):
        calls.append(kwargs)
        reply = remaining.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(gateway, "call", fake_call)
    return calls


@pytest.mark.unit
class TestInvalidReply:
    def test_create_on_a_valid_reply_should_call_once(self, monkeypatch, a_valid_reply):
        # Arrange
        calls = _answer(monkeypatch, a_valid_reply)

        # Act
        vgl = bria_vgl.create(Generate(prompt="p"), seed=7)

        # Assert
        assert isinstance(vgl, ThalesVGL)
        assert len(calls) == 1

    def test_modify_on_a_reply_without_the_scene_should_ask_again(self, monkeypatch, an_image, a_reply_without_the_scene, a_valid_reply):
        # Arrange
        calls = _answer(monkeypatch, a_reply_without_the_scene, a_valid_reply)

        # Act
        vgl = bria_vgl.modify(EditImages(prompt="p", images=[an_image]), seed=7)

        # Assert
        assert vgl.edit_instruction == "made it night"
        assert len(calls) == 2

    def test_the_retry_should_send_the_next_seed(self, monkeypatch, a_reply_without_the_scene, a_valid_reply):
        # Arrange
        calls = _answer(monkeypatch, a_reply_without_the_scene, a_valid_reply)

        # Act
        bria_vgl.create(Generate(prompt="p"), seed=7)

        # Assert
        assert [call["seed"] for call in calls] == [7, 8]

    def test_the_retry_on_the_largest_seed_should_wrap_to_zero(self, monkeypatch, a_reply_without_the_scene, a_valid_reply):
        # Arrange
        calls = _answer(monkeypatch, a_reply_without_the_scene, a_valid_reply)

        # Act
        bria_vgl.create(Generate(prompt="p"), seed=2**31 - 1)

        # Assert
        assert [call["seed"] for call in calls] == [2**31 - 1, 0]

    def test_the_retry_without_a_seed_should_send_none(self, monkeypatch, a_reply_without_the_scene, a_valid_reply):
        # Arrange
        calls = _answer(monkeypatch, a_reply_without_the_scene, a_valid_reply)

        # Act
        bria_vgl.create(Generate(prompt="p"))

        # Assert
        assert [call["seed"] for call in calls] == [None, None]

    def test_create_on_an_empty_reply_should_ask_again(self, monkeypatch, a_valid_reply):
        # Arrange
        calls = _answer(monkeypatch, exceptions.InvalidResponseError("returned an empty reply (finish_reason=stop)"), a_valid_reply)

        # Act
        vgl = bria_vgl.create(Generate(prompt="p"))

        # Assert
        assert isinstance(vgl, ThalesVGL)
        assert len(calls) == 2

    def test_create_on_two_invalid_replies_should_raise_an_unusable_reply_error(self, monkeypatch, a_reply_without_the_scene):
        # Arrange
        calls = _answer(monkeypatch, "I can't help with that.", a_reply_without_the_scene)

        # Act
        with pytest.raises(exceptions.UnusableReplyError) as raised:
            bria_vgl.create(Generate(prompt="p"))

        # Assert
        assert isinstance(raised.value, exceptions.ContentFilteredError)
        assert isinstance(raised.value, exceptions.InvalidResponseError)
        assert isinstance(raised.value.__cause__, exceptions.InvalidResponseError)
        assert len(calls) == 2

    def test_create_on_a_filtered_reply_should_not_ask_again(self, monkeypatch):
        # Arrange
        calls = _answer(monkeypatch, exceptions.ContentFilteredError("blocked"))

        # Act
        with pytest.raises(exceptions.ContentFilteredError) as raised:
            bria_vgl.create(Generate(prompt="p"))

        # Assert
        assert not isinstance(raised.value, exceptions.UnusableReplyError)
        assert len(calls) == 1
