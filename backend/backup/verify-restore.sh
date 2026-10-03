#!/usr/bin/env bash
# Take a fresh verified dump, restore it into a scratch DB and compare row counts of every
# public table with the live DB (run by the CI e2e job after Playwright; C11). response_cache is
# skipped: it is a disposable cache whose rows are not dumped and which the worker rewrites at any
# moment (Plan 19 D22).
set -euo pipefail

SCRATCH_DB=sc_restore_check
HERE="$(dirname "$0")"
PGPASSWORD="$(cat "$POSTGRES_PASSWORD_FILE")"
export PGPASSWORD
export PGOPTIONS='-c client_min_messages=warning' # no NOTICE lines (DROP ... IF EXISTS, CASCADE)
WROTE="$(mktemp)"
trap 'rm -f "$WROTE"' EXIT

drop_scratch() {
  psql --quiet -v ON_ERROR_STOP=1 -d postgres -c "DROP DATABASE IF EXISTS $SCRATCH_DB"
}

cleanup() {
  drop_scratch
  rm -f "$WROTE"
}

row_counts() {
  local db="$1" table
  psql -At -v ON_ERROR_STOP=1 -d "$db" -c \
    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name <> 'response_cache' ORDER BY 1" |
    while read -r table; do
      printf '%s %s\n' "$table" "$(psql -At -v ON_ERROR_STOP=1 -d "$db" -c "SELECT count(*) FROM public.\"$table\"")"
    done
}

# Restore exactly the dump this run wrote (backup.sh records its path), never a newer one that
# the service's own schedule may have written meanwhile.
BACKUP_WROTE_FILE="$WROTE" "$HERE/backup.sh" --once
dump="$(cat "$WROTE")"
[[ -n "$dump" ]] || {
  echo "verify-restore: backup.sh recorded no dump" >&2
  exit 1
}
drop_scratch
trap cleanup EXIT
psql --quiet -v ON_ERROR_STOP=1 -d postgres -c "CREATE DATABASE $SCRATCH_DB"
"$HERE/restore.sh" "$dump" "$SCRATCH_DB"
live="$(row_counts "$PGDATABASE")"
restored="$(row_counts "$SCRATCH_DB")"
if [[ "$live" != "$restored" ]]; then
  echo "verify-restore: row counts differ" >&2
  diff <(echo "$live") <(echo "$restored") >&2 || true
  exit 1
fi
echo "verify-restore: $(echo "$live" | grep -c . || true) tables match ($dump)"
