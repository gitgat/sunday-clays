import logging
import re

import pytest

from sunday_clays.logging import configure_logging


def test_configure_logging_adds_one_timestamped_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", [])
    monkeypatch.setattr(root, "level", logging.WARNING)

    configure_logging()
    configure_logging()

    assert len(root.handlers) == 1
    record = logging.LogRecord("sunday_clays.probe", logging.INFO, __file__, 1, "hello", None, None)
    line = root.handlers[0].format(record)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} [\d:,]+ INFO sunday_clays\.probe hello", line)
    assert root.level == logging.INFO


def test_configure_logging_keeps_existing_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    root = logging.getLogger()
    existing = logging.NullHandler()
    monkeypatch.setattr(root, "handlers", [existing])
    monkeypatch.setattr(root, "level", logging.WARNING)

    configure_logging(logging.DEBUG)

    assert root.handlers == [existing]
    assert root.level == logging.DEBUG
