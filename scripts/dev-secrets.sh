#!/usr/bin/env bash
# Writes ./secrets/* for local compose and CI e2e (C1). Never overwrites an existing file:
# delete ./secrets/ to regenerate. VIEWER_PASSWORD / ADMIN_PASSWORD are used when set, else a
# random password is generated and printed once.
#
# Every generated value is assigned to a variable before it is written: `set -e` never sees a
# failure inside a command substitution that is passed as an argument, so `write_secret x
# "$(cmd)"` would write an empty secret and carry on. A failed or empty value stops the script.
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p secrets
chmod 700 secrets

die() {
  echo "dev-secrets: $*" >&2
  exit 1
}

write_secret() { # name value
  [[ -n "$2" ]] || die "refusing to write an empty secrets/$1"
  printf '%s' "$2" >"secrets/$1"
  # 644 inside a 700 directory: containers (uid 10001) can read the bind-mounted file,
  # other local users cannot reach it.
  chmod 644 "secrets/$1"
  echo "dev-secrets: wrote secrets/$1"
}

argon2_hash() { # password on stdin -> argon2id hash (m=19456 KiB, t=2, p=1, as hashpw.py)
  uv run --quiet --no-project --with argon2-cffi python -c '
import sys
from argon2 import PasswordHasher
print(PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1).hash(sys.stdin.read()), end="")'
}

random_hex_secret() { # name: 32 random bytes as 64 hex characters
  local value
  if [[ -e "secrets/$1" ]]; then
    echo "dev-secrets: kept secrets/$1"
    return
  fi
  value="$(openssl rand -hex 32)" || die "openssl rand failed for secrets/$1"
  [[ ${#value} -eq 64 ]] || die "openssl rand gave no usable value for secrets/$1"
  write_secret "$1" "$value"
}

password_hash_secret() { # secret-name role password-or-empty
  local name="$1" role="$2" password="$3" generated="" hash
  if [[ -e "secrets/$name" ]]; then
    echo "dev-secrets: kept secrets/$name"
    return
  fi
  if [[ -z "$password" ]]; then
    password="$(openssl rand -base64 18)" || die "openssl rand failed for the $role password"
    [[ -n "$password" ]] || die "openssl rand gave no $role password"
    generated="$password"
  fi
  hash="$(printf '%s' "$password" | argon2_hash)" || die "hashing the $role password failed"
  # shellcheck disable=SC2016 # the literal prefix of every argon2id hash, not an expansion
  [[ "$hash" == '$argon2id$'* ]] || die "hashing the $role password gave no argon2id hash"
  write_secret "$name" "$hash"
  if [[ -n "$generated" ]]; then
    echo "dev-secrets: generated $role password (shown once): $generated"
  fi
}

password_hash_secret viewer_password_hash viewer "${VIEWER_PASSWORD:-}"
password_hash_secret admin_password_hash admin "${ADMIN_PASSWORD:-}"
random_hex_secret session_secret
random_hex_secret db_password

if [[ -e secrets/database_url ]]; then
  echo "dev-secrets: kept secrets/database_url"
else
  db_password="$(cat secrets/db_password)"
  [[ -n "$db_password" ]] || die "secrets/db_password is empty: delete ./secrets/ and run again"
  write_secret database_url "postgresql+psycopg://sunday:$db_password@db:5432/sunday_clays"
fi
