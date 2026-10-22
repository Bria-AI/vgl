import logging
from pathlib import Path

import pytest

from bria_vgl.log import get_logger, set_logger
from bria_vgl.prompting import render_prompts


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    set_logger(None)


@pytest.mark.unit
class TestInjectableLogger:
    def test_defaults_to_the_module_logger(self):
        # Act
        result = get_logger("bria_vgl.gateway")

        # Assert
        assert result is logging.getLogger("bria_vgl.gateway")

    def test_injected_logger_is_returned_for_any_name(self):
        # Arrange
        custom = logging.getLogger("custom")
        set_logger(custom)

        # Act / Assert
        assert get_logger("bria_vgl.gateway") is custom
        assert get_logger("bria_vgl.api") is custom

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

    def test_set_logger_none_restores_the_default(self):
        # Arrange
        set_logger(logging.getLogger("custom"))

        # Act
        set_logger(None)

        # Assert
        assert get_logger("bria_vgl.gateway") is logging.getLogger("bria_vgl.gateway")
