#!/usr/bin/env bash
# Idempotent repo settings + `main` protection (master plan §0 step 6). Run once, with the
# user's explicit OK, after `ci-ok` has completed at least once on main.
set -euo pipefail

repo="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"

github_api() { # method path json-body
  local output
  if ! output="$(gh api --method "$1" "repos/$repo$2" --input - <<<"$3" 2>&1)"; then
    echo "setup-branch-protection: $1 repos/$repo$2 failed: $output" >&2
    exit 1
  fi
}

github_api PATCH "" '{
  "allow_auto_merge": true,
  "delete_branch_on_merge": true,
  "allow_merge_commit": false,
  "allow_squash_merge": true
}'

github_api PUT "/branches/main/protection" '{
  "required_status_checks": {"strict": true, "contexts": ["ci-ok"]},
  "enforce_admins": true,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}'

echo "setup-branch-protection: $repo main now requires ci-ok (strict, linear, admins included)"
