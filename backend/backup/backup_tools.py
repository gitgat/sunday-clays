"""Date-based backup retention and the nightly schedule for backup.sh (stdlib only).

python3 backup_tools.py prune <dir>          delete dumps outside 14 daily + 8 weekly slots
python3 backup_tools.py seconds-until HH:MM  seconds until the next HH:MM America/Los_Angeles
python3 backup_tools.py lock <fd> <seconds>  exclusive flock on inherited fd <fd>; exit 1 on timeout
"""

import fcntl
import re
import sys
import time
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

DUMP_NAME = re.compile(r"^sc-(\d{8}T\d{6}Z)\.dump$")
KEEP_DAILY = 14
KEEP_WEEKLY = 8
LOCAL_TZ = ZoneInfo("America/Los_Angeles")


def dump_time(name: str) -> datetime | None:
    match = DUMP_NAME.match(name)
    if match is None:
        return None
    return datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)


def dumps_to_keep(names: Iterable[str], today: date) -> set[str]:
    """Newest dump of each of the last 14 UTC days and of each of the last 8 ISO weeks."""
    stamped = sorted(((t, n) for n in names if (t := dump_time(n)) is not None), reverse=True)
    keep: set[str] = set()
    days_seen: set[date] = set()
    weeks_seen: set[tuple[int, int]] = set()
    first_day = today - timedelta(days=KEEP_DAILY - 1)
    this_week = today.isocalendar()
    first_week_monday = date.fromisocalendar(this_week.year, this_week.week, 1) - timedelta(
        weeks=KEEP_WEEKLY - 1
    )
    for taken, name in stamped:
        day = taken.date()
        week = (day.isocalendar().year, day.isocalendar().week)
        if day >= first_day and day not in days_seen:
            days_seen.add(day)
            keep.add(name)
        if day >= first_week_monday and week not in weeks_seen:
            weeks_seen.add(week)
            keep.add(name)
    return keep


def prune(directory: Path, now: datetime) -> list[str]:
    """Deletes dumps that are not kept and leftover *.dump.tmp files; returns deleted names."""
    names = [p.name for p in directory.iterdir()]
    keep = dumps_to_keep(names, now.astimezone(UTC).date())
    deleted = []
    for name in sorted(names):
        if (DUMP_NAME.match(name) and name not in keep) or name.endswith(".dump.tmp"):
            (directory / name).unlink()
            deleted.append(name)
    return deleted


def seconds_until(hhmm: str, now: datetime) -> int:
    """Seconds from ``now`` until the next local HH:MM in America/Los_Angeles (DST-safe)."""
    hour, minute = (int(part) for part in hhmm.split(":"))
    local_now = now.astimezone(LOCAL_TZ)
    target = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= local_now:
        target = (local_now + timedelta(days=1)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
    return max(1, int((target.astimezone(UTC) - now.astimezone(UTC)).total_seconds()))


def lock(fd: int, timeout_s: float, poll_s: float = 0.1) -> bool:
    """Takes an exclusive flock(2) on ``fd``, waiting up to ``timeout_s``; False on timeout.

    flock(1) for hosts without util-linux (macOS runs the backup.sh tests). The lock belongs to
    the open file description, so when backup.sh passes its own descriptor (``exec 9>>lock``
    then ``lock 9``) the lock outlives this process until the shell closes that descriptor.
    """
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(poll_s)
        else:
            return True


def main(argv: Sequence[str]) -> int:
    if len(argv) == 2 and argv[0] == "prune":
        for name in prune(Path(argv[1]), datetime.now(UTC)):
            print(f"pruned {name}")
        return 0
    if len(argv) == 2 and argv[0] == "seconds-until":
        print(seconds_until(argv[1], datetime.now(UTC)))
        return 0
    if len(argv) == 3 and argv[0] == "lock":
        if lock(int(argv[1]), float(argv[2])):
            return 0
        print(f"backup: another backup run still holds the lock after {argv[2]} s", file=sys.stderr)
        return 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
