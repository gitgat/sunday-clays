"""One linear Alembic history (Plan 20 D19): a second head or a branch point fails here."""

from collections import Counter

from alembic.script import ScriptDirectory

from sunday_clays.db import alembic_config
from sunday_clays.domain.rebuild import LIVE_TABLES


def test_migration_chain_is_linear() -> None:
    script = ScriptDirectory.from_config(alembic_config())
    revisions = list(script.walk_revisions())  # newest first
    assert script.get_heads() == [revisions[0].revision]
    assert all(isinstance(r.down_revision, str | None) for r in revisions), "no merge revisions"
    parents = Counter(r.down_revision for r in revisions)
    assert max(parents.values()) == 1, "no two revisions share a parent"
    assert "0010" in {r.revision for r in revisions}


def test_club_event_tables_are_never_rebuilt() -> None:
    # Pin (D19): the four tables are durable, so a rebuild (domain/rebuild.py) never drops them.
    club = {"club_events", "club_event_registrations", "shooter_contacts", "club_event_attempts"}
    assert not club & set(LIVE_TABLES)
