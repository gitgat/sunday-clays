#!/usr/bin/env bash
# Plan 19 §3.1.3: validate the Caddyfile, then check crawler routing and /l/ redirects against a
# running stack. Usage: deploy/caddy/test_crawler_ua.sh <base url> [frontend image]
set -euo pipefail

BASE="${1:?usage: test_crawler_ua.sh <base url> [frontend image]}"
IMAGE="${2:-ghcr.io/gitgat/sunday-clays-frontend:ci}"
HERE="$(cd "$(dirname "$0")" && pwd)"
DAY="2026-09-27"
fail=0

docker run --rm "$IMAGE" caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile

check() { # $1 description, $2 expected, $3 actual
  if [[ "$2" == "$3" ]]; then echo "ok   $1"; else echo "FAIL $1: expected [$2], got [$3]"; fail=1; fi
}

while IFS=$'\t' read -r expect ua; do
  [[ -z "$expect" ]] && continue
  body="$(curl -sS -A "$ua" "$BASE/events/$DAY" || true)"
  if grep -q 'property="og:title"' <<<"$body"; then got=crawler; else got=person; fi
  check "$expect: $ua" "$expect" "$got"
  if [[ "$expect" == crawler ]]; then
    share="$(curl -sS -A "$ua" "$BASE/l/events/$DAY" || true)"
    if grep -q 'property="og:title"' <<<"$share"; then got=crawler; else got=person; fi
    check "share link previews for $ua" crawler "$got"
  fi
done <"$HERE/user-agents.tsv"

browser='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0.0.0 Safari/537.36'
location() { curl -s -o /dev/null -A "$browser" -w '%{redirect_url}' "$BASE$1" || true; }
check "share redirect" "$BASE/events/$DAY" "$(location "/l/events/$DAY")"
check "share redirect keeps the query" "$BASE/events/$DAY?w=3m" "$(location "/l/events/$DAY?w=3m")"
check "open redirect //" "$BASE/" "$(location '/l//evil.com')"
check "open redirect upper-case /L//" "$BASE/" "$(location '/L//evil.com')"
check "open redirect %2F%2F" "$BASE/" "$(location '/l/%2F%2Fevil.com')"
check "open redirect backslash" "$BASE/" "$(location '/l/%5Cevil.com')"
exit "$fail"
