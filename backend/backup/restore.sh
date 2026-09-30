#!/usr/bin/env bash
# Restore a custom-format dump: restore.sh <dump> [db]   (db defaults to $PGDATABASE)
# Stop `api` and `worker` first when restoring over the live database.
#
# All or nothing, in one transaction: drop the public schema, recreate it as a fresh
# Postgres 15+ database has it, replay the dump. Tables the dump does not know (a newer
# migration's) are gone afterwards. COMMIT is sent only after pg_restore has read the whole
# dump; on any failure psql stops or reaches end of input inside the open transaction, the
# server rolls it back, and the database is exactly as it was.
set -euo pipefail

dump="${1:?usage: restore.sh <dump> [db]}"
db="${2:-$PGDATABASE}"
PGPASSWORD="$(cat "$POSTGRES_PASSWORD_FILE")"
export PGPASSWORD

pg_restore --list "$dump" >/dev/null # an unreadable dump fails here, before anything is touched
{
  cat <<'SQL'
BEGIN;
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
ALTER SCHEMA public OWNER TO pg_database_owner;
GRANT USAGE ON SCHEMA public TO PUBLIC;
COMMENT ON SCHEMA public IS 'standard public schema';
SQL
  pg_restore --no-owner --file=- "$dump" || exit 1
  echo 'COMMIT;'
} | psql --no-psqlrc --quiet -v ON_ERROR_STOP=1 --dbname="$db"
echo "restore: restored $dump into $db"
