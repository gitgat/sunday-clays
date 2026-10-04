#!/usr/bin/env bash
# Verified pg_dump of the sunday_clays DB (run by the `backup` service; C1, Plan 01 T4).
#   backup.sh          dump once at start, then daily at 02:30 America/Los_Angeles
#   backup.sh --once   one verified dump, then exit (used by verify-restore.sh)
# Env: PGHOST PGUSER PGDATABASE POSTGRES_PASSWORD_FILE [BACKUP_HC_URL_FILE] [BACKUP_DIR=/backups]
#      [BACKUP_LOCK_TIMEOUT=600] [BACKUP_WROTE_FILE: receives the path of the dump a run kept]
# Each run holds an exclusive flock on $BACKUP_DIR/backup.lock, so a second run (verify-restore.sh
# during the nightly dump) waits for the first rather than pruning its *.dump.tmp. A run that
# waits longer than BACKUP_LOCK_TIMEOUT seconds fails like any other failed dump.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
LOCK_TIMEOUT="${BACKUP_LOCK_TIMEOUT:-600}"
TOOLS="$(dirname "$0")/backup_tools.py"
PGPASSWORD="$(cat "$POSTGRES_PASSWORD_FILE")"
export PGPASSWORD

ping_healthcheck() { # suffix: "" on success, "/fail" on failure
  local url=""
  if [[ -n "${BACKUP_HC_URL_FILE:-}" && -f "${BACKUP_HC_URL_FILE}" ]]; then
    url="$(tr -d '[:space:]' <"$BACKUP_HC_URL_FILE")" || url=""
  fi
  # No file, or only whitespace (Swarm rejects an empty secret, so a newline disables pings).
  [[ -n "$url" ]] || return 0
  python3 -c 'import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=10)' \
    "$url$1" || echo "backup: healthcheck ping failed" >&2
}

# Always called as `if dump_once`, where bash ignores `set -e`: every step must propagate its
# own failure, or a failed or unverifiable dump would be reported (and pinged) as a success.
dump_once() {
  local stamp tmp dump
  stamp="$(date -u +%Y%m%dT%H%M%SZ)" || return 1
  tmp="$BACKUP_DIR/sc-$stamp.dump.tmp"
  dump="$BACKUP_DIR/sc-$stamp.dump"
  # response_cache is a disposable UNLOGGED cache (Plan 19 D22): keep its definition, not its rows.
  # club_event_attempts is ephemeral rate-limit rows (IP fingerprints, Plan 20): never dumped either.
  pg_dump --format=custom --exclude-table-data=response_cache \
    --exclude-table-data=club_event_attempts --file="$tmp" || return 1
  pg_restore --list "$tmp" >/dev/null || return 1
  mv "$tmp" "$dump" || return 1
  python3 "$TOOLS" prune "$BACKUP_DIR" || return 1
  touch "$BACKUP_DIR/last_success" || return 1
  if [[ -n "${BACKUP_WROTE_FILE:-}" ]]; then
    printf '%s\n' "$dump" >"$BACKUP_WROTE_FILE" || return 1
  fi
  echo "backup: wrote $dump"
}

run_dump() {
  # fd 9 holds this run's lock; it is closed before pinging and before the next sleep starts.
  if exec 9>>"$BACKUP_DIR/backup.lock" && python3 "$TOOLS" lock 9 "$LOCK_TIMEOUT" && dump_once; then
    exec 9>&-
    ping_healthcheck ""
  else
    exec 9>&-
    echo "backup: dump failed" >&2
    ping_healthcheck "/fail"
    return 1
  fi
}

if [[ "${1:-}" == "--once" ]]; then
  run_dump
  exit $?
fi

trap 'exit 0' TERM INT
for _ in $(seq 60); do
  pg_isready --quiet && break
  sleep 2
done
run_dump || true
while true; do
  sleep "$(python3 "$TOOLS" seconds-until 02:30)" &
  wait $!
  run_dump || true
done
