import logging
from pathlib import Path

import pytest

from bria_vgl.logging import get_logger, set_logger
from bria_vgl.prompting import render_prompts


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    set_logger(None)


@pytest.mark.unit
class TestInjectableLogger:
    def test_defaults_to_the_named_logger(self, caplog):
        # Arrange
        logger = get_logger("bria_vgl.gateway")

        # Act
        with caplog.at_level(logging.WARNING):
            logger.warning("hello")

        # Assert
        assert [r.name for r in caplog.records] == ["bria_vgl.gateway"]

    def test_injected_logger_receives_records_for_any_name(self, caplog):
        # Arrange
        set_logger(logging.getLogger("custom"))

        # Act
        with caplog.at_level(logging.WARNING):
            get_logger("bria_vgl.gateway").warning("one")
            get_logger("bria_vgl.api").warning("two")

        # Assert
        assert [r.name for r in caplog.records] == ["custom", "custom"]

    def test_logger_bound_before_injection_picks_it_up(self, caplog):
        # Arrange
        bound = get_logger("bria_vgl.gateway")
        set_logger(logging.getLogger("custom"))

        # Act
        with caplog.at_level(logging.WARNING):
            bound.warning("late")

        # Assert
        assert [r.name for r in caplog.records] == ["custom"]

    def test_injected_adapter_receives_a_real_call_sites_record(self, caplog):
        # Arrange
        adapter = logging.LoggerAdapter(logging.getLogger("custom"), {"request_id": "r1"})
        set_logger(adapter)

        # Act
        with caplog.at_level(logging.WARNING):
            render_prompts(Path("unused"), {}, system_template="{missing}", final_template="x")

        # Assert
        assert [r.name for r in caplog.records] == ["custom"]
        assert "unfilled prompt placeholders" in caplog.text
        # The proxy returns the real bound method, so the record points at the call site, not logging.py.
        assert (caplog.records[0].filename, caplog.records[0].funcName) == ("prompting.py", "render_prompts")
        assert caplog.records[0].request_id == "r1"

    def test_set_logger_none_restores_the_default(self, caplog):
        # Arrange
        set_logger(logging.getLogger("custom"))
        set_logger(None)

        # Act
        with caplog.at_level(logging.WARNING):
            get_logger("bria_vgl.gateway").warning("back")

        # Assert
        assert [r.name for r in caplog.records] == ["bria_vgl.gateway"]
