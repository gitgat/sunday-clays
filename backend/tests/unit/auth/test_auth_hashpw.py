import getpass
import runpy
import sys

import pytest

from sunday_clays.auth import hashpw
from sunday_clays.auth.passwords import verify_password


def _prompts(monkeypatch: pytest.MonkeyPatch, *answers: str) -> list[str]:
    asked: list[str] = []
    replies = iter(answers)

    def fake_getpass(prompt: str = "Password: ", stream: object = None) -> str:
        asked.append(prompt)
        return next(replies)

    monkeypatch.setattr(getpass, "getpass", fake_getpass)
    return asked


def test_prints_a_verifiable_hash_after_confirmation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    asked = _prompts(monkeypatch, "s3cret-pass", "s3cret-pass")
    assert hashpw.main([]) == 0
    printed = capsys.readouterr().out.strip()
    assert len(asked) == 2
    assert printed.startswith("$argon2id$")
    assert verify_password(printed, "s3cret-pass") is True


def test_mismatched_confirmation_prints_nothing_and_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _prompts(monkeypatch, "s3cret-pass", "s3cret-pasS")
    assert hashpw.main([]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "do not match" in captured.err


def test_empty_password_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _prompts(monkeypatch, "", "")
    assert hashpw.main([]) == 1
    assert capsys.readouterr().out == ""


def test_password_on_the_command_line_is_rejected_before_prompting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = _prompts(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        hashpw.main(["hunter2"])
    assert exc.value.code == 2
    assert asked == []


def test_module_entry_point_runs_main(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _prompts(monkeypatch, "entry-pass", "entry-pass")
    monkeypatch.setattr(sys, "argv", ["hashpw"])
    monkeypatch.delitem(sys.modules, "sunday_clays.auth.hashpw")
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("sunday_clays.auth.hashpw", run_name="__main__")
    assert exc.value.code == 0
    assert verify_password(capsys.readouterr().out.strip(), "entry-pass") is True
