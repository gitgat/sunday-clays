import importlib.util
import time
from datetime import UTC, date, datetime
from pathlib import Path
from types import ModuleType

TOOLS_PATH = Path(__file__).resolve().parents[3] / "backup" / "backup_tools.py"


def load_tools() -> ModuleType:
    spec = importlib.util.spec_from_file_location("backup_tools", TOOLS_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tools = load_tools()


def test_restart_loop_cannot_push_older_days_out() -> None:
    today = date(2026, 9, 27)
    restart_loop = [f"sc-20260927T{h:02d}0000Z.dump" for h in range(20)]
    older_days = [f"sc-202609{d:02d}T093000Z.dump" for d in range(14, 27)]

    keep = tools.dumps_to_keep(restart_loop + older_days, today)

    assert set(older_days) <= keep
    assert "sc-20260927T190000Z.dump" in keep
    assert keep & set(restart_loop) == {"sc-20260927T190000Z.dump"}


def test_keeps_fourteen_daily_and_eight_weekly() -> None:
    today = date(2026, 9, 27)
    daily_for_ten_weeks = [
        f"sc-{(date.fromordinal(today.toordinal() - n)).strftime('%Y%m%d')}T093000Z.dump"
        for n in range(70)
    ]

    keep = tools.dumps_to_keep(daily_for_ten_weeks, today)

    assert {f"sc-202609{d:02d}T093000Z.dump" for d in range(14, 28)} <= keep
    assert "sc-20260913T093000Z.dump" in keep  # Sunday: newest of ISO week 37
    assert "sc-20260912T093000Z.dump" not in keep
    assert "sc-20260809T093000Z.dump" in keep  # Sunday of ISO week 32, the 8th week back
    assert "sc-20260802T093000Z.dump" not in keep  # ISO week 31 is outside the window
    assert len(keep) == 14 + 6


def test_prune_deletes_unkept_dumps_and_temp_files(tmp_path: Path) -> None:
    for name in [
        "sc-20260927T093000Z.dump",
        "sc-20260927T080000Z.dump",
        "sc-20260101T093000Z.dump",
        "sc-20260927T100000Z.dump.tmp",
        "last_success",
    ]:
        (tmp_path / name).write_text("x")

    deleted = tools.prune(tmp_path, datetime(2026, 9, 27, 12, tzinfo=UTC))

    assert deleted == [
        "sc-20260101T093000Z.dump",
        "sc-20260927T080000Z.dump",
        "sc-20260927T100000Z.dump.tmp",
    ]
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "last_success",
        "sc-20260927T093000Z.dump",
    ]


def test_seconds_until_later_today() -> None:
    now = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)  # 01:00 PDT

    assert tools.seconds_until("02:30", now) == 90 * 60


def test_seconds_until_rolls_to_tomorrow() -> None:
    now = datetime(2026, 9, 27, 10, 0, tzinfo=UTC)  # 03:00 PDT

    assert tools.seconds_until("02:30", now) == 23 * 3600 + 30 * 60


def test_seconds_until_across_fall_back() -> None:
    now = datetime(2026, 10, 31, 10, 0, tzinfo=UTC)  # Sat 03:00 PDT; clocks fall back Sun 02:00

    assert tools.seconds_until("02:30", now) == 24 * 3600 + 30 * 60


def test_seconds_until_across_spring_forward() -> None:
    now = datetime(2026, 3, 7, 11, 0, tzinfo=UTC)  # Sat 03:00 PST; clocks spring forward Sun 02:00
    fired = datetime(2026, 3, 8, 10, 30, tzinfo=UTC)  # Sun 03:30 PDT

    # Sunday has no 02:30: the dump runs once, at 03:30 PDT...
    assert tools.seconds_until("02:30", now) == 23 * 3600 + 30 * 60
    # ...and the next one is Monday 02:30 PDT, not a second run on Sunday.
    assert tools.seconds_until("02:30", fired) == 23 * 3600


def test_lock_waits_for_the_holder_then_gives_up(tmp_path: Path) -> None:
    lock_file = tmp_path / "backup.lock"
    with lock_file.open("a") as holder, lock_file.open("a") as waiter:
        assert tools.lock(holder.fileno(), 0.0)
        started = time.monotonic()

        assert not tools.lock(waiter.fileno(), 0.3)
        assert time.monotonic() - started >= 0.3


def test_lock_is_taken_once_the_holder_lets_go(tmp_path: Path) -> None:
    lock_file = tmp_path / "backup.lock"
    with lock_file.open("a") as waiter:
        with lock_file.open("a") as holder:
            assert tools.lock(holder.fileno(), 0.0)

        assert tools.lock(waiter.fileno(), 0.0)


def test_cli_lock_exits_1_while_another_run_holds_it(tmp_path: Path) -> None:
    lock_file = tmp_path / "backup.lock"
    with lock_file.open("a") as holder, lock_file.open("a") as waiter:
        assert tools.main(["lock", str(holder.fileno()), "0"]) == 0

        assert tools.main(["lock", str(waiter.fileno()), "0"]) == 1


def test_cli_rejects_unknown_command() -> None:
    assert tools.main(["explode"]) == 2
