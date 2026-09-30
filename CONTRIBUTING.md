# Contributing to Sunday Clays

The design spec lives in `docs/superpowers/specs/`; the master plan (Architecture Contract,
execution procedure) and the per-area sub-plans live in `docs/superpowers/plans/`. Every change is
test-driven (write the failing test, watch it fail, make it pass) and lands as a pull request that
passes the single required check, `ci-ok`.

## Toolchain

| Tool | Version | Install |
|---|---|---|
| uv | 0.9.9 or newer. CI and the backend image pin 0.9.9; bump `UV_VERSION` in `.github/workflows/ci.yml`, the `ghcr.io/astral-sh/uv` tag in `backend/Dockerfile` and `[tool.uv] required-version` in `backend/pyproject.toml` together. | `brew install uv` |
| Python | 3.13 (uv installs it) | |
| Node | 22 (`.nvmrc`) | `nvm install && nvm use` |
| pnpm | 10.34.5 (`packageManager` in `frontend/package.json`) | `corepack enable` |
| Docker | Desktop, Colima or OrbStack | |
| lefthook | 2.x | `brew install lefthook && lefthook install` |
| gh + gh-stack | gh 2.101.0 or newer | `gh extension install github/gh-stack` |

## Everyday commands

| What | Where | Command |
|---|---|---|
| Backend checks | `backend/` | `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch` |
| Frontend checks | `frontend/` | `pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm test --coverage` |
| Repo-script tests | repo root | `uv run --no-project --with pytest --with pyyaml pytest scripts/tests` |
| Local stack | repo root | `scripts/dev-secrets.sh && docker compose up -d --build --wait`, then open http://localhost:8080 |
| E2E (stack running) | `frontend/` | `pnpm exec playwright install chromium && pnpm exec playwright test` |

- `pnpm typecheck` first regenerates `src/api/schema.d.ts` from the backend's OpenAPI schema
  (`pnpm gen:api`), so frontend code is always typed against the current backend.
- Run coverage as `pnpm test --coverage`. `pnpm test -- --coverage` forwards a literal `--`, and
  Vitest then silently skips coverage.
- Stop the local stack with `docker compose down`; add `-v` to wipe its database and backups.
- The e2e stack (`compose.test.yaml`) publishes host port `E2E_PORT` (default 8080), and Playwright
  targets `E2E_BASE_URL` (default `http://localhost:8080`). To run several worktrees' stacks at
  once, give each its own Compose project and port, for example
  `E2E_PORT=18080 IMAGE_TAG=<tag> docker compose -p <project> -f compose.yaml -f compose.test.yaml up -d --wait`,
  then `E2E_BASE_URL=http://localhost:18080 pnpm exec playwright test` in `frontend/`.

## Tests and databases

- Backend tests start one `postgres:17` testcontainer per pytest run, so Docker must be running. On
  macOS the conftest points Ryuk at `/var/run/docker.sock` automatically.
- `TEST_DATABASE_URL=postgresql+psycopg://…` makes pytest use an existing, empty database instead;
  CI does this. **Never point two concurrent worktrees at the same `TEST_DATABASE_URL`**: the
  `committed_engine` fixture (arriving in Plan 03 T7) truncates every table after each test, and
  `fx_engine` (arriving in Plan 03 T6) drops and recreates `<db>_fx`. Per-run testcontainers are
  the isolation mechanism.
- `tests/unit` never touches a database; `tests/integration` uses the `engine`, `session` and
  `client` fixtures from `backend/tests/conftest.py`.

## Branches, commits, worktrees and hooks

- One plan task = one branch = one worktree = one pull request. Task branches are
  `task/<NN>-<T>-<slug>` (for example `task/03-2-identity`); `chore/ratchet-wave-<N>` and
  `chore/deps-<pkg>` are controller-only.
- Conventional Commits. Every commit ends with the trailer
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Worktrees live under `.wt/` (gitignored): `git worktree add .wt/<branch> <branch>`; remove them
  with `git worktree remove .wt/<branch>` after the branch lands.
- lefthook's pre-commit hook runs ruff, eslint and prettier on staged files, plus `pnpm typecheck`
  when TypeScript changed. Its pre-push hook runs the backend suite when `backend/**` changed and the
  frontend suite when `frontend/**` changed, so a frontend-only push never starts Postgres.

## Stacked pull requests with gh stack

Each dependency chain in a plan is one stack of pull requests, managed with `gh stack` (extension
`github/gh-stack`). Independent chains are separate stacks off `main`. CI runs on every pull request,
including mid-stack ones whose base is another stack branch, because `ci.yml`'s `pull_request`
trigger has no branch filter.

1. **Build the stack.** In the main checkout run `gh stack init -b main task/03-1-models` and give
   the implementer a worktree: `git worktree add .wt/task/03-1-models task/03-1-models`. When a layer
   passes task review, run `gh stack add task/03-2-identity` from the top of the stack and create its
   worktree. The next implementer starts on top of reviewed but unmerged work.
2. **Siblings.** Same-wave siblings on the same parent that touch disjoint files are implemented
   concurrently on branches cut from the parent layer, then linearised in plan order. Run
   `gh stack add` for the first; for the second, run `git rebase --onto <first> <parent> <second>`,
   then adopt it with `gh stack init`/`gh stack add`. Disjoint files guarantee no conflicts.
3. **Publish.** Run `gh stack submit --auto` after each new layer. Pull requests open as drafts, and
   drafts still run CI. Once the whole chain has passed task review, run
   `gh stack submit --auto --open`.
4. **Fix a lower layer.** Commit on that layer's branch, then run `gh stack rebase --upstack` from
   that layer and `gh stack push`. On a conflict (exit code 3), resolve it in the conflicted layer's
   worktree, `git add` the files, run `gh stack rebase --continue`, then `gh stack push`.
5. **Land.** When every layer's `ci-ok` is green (`gh pr checks <N> --required --watch`), run
   `gh stack merge <stack-number> --squash --yes`, then `gh stack sync --prune` and
   `git worktree remove` for each layer. A ready lower prefix can land alone:
   `gh stack merge <pr-number-of-last-ready-layer> --squash --yes`; the remaining layers re-target
   `main`.
6. **One stack lands at a time.** After each merge, run `gh stack sync` on every other open stack.
   That rebases it onto the new `main` and re-runs CI before it can land. If CI on `main` is red,
   stop all merges until it is fixed.

`gh stack` exit codes: **3** means a rebase conflict (resolve as in step 4). **8** means the stack
is locked by another operation (wait and retry). **9** means stacked pull requests are not enabled
for the repository (ask the owner to enable the preview in the repository settings).

## Coverage ratchet and bundle budgets

- Floors are 90% lines **and** 90% branches, measured separately for the backend and the frontend.
  `ratchets/baseline.json` holds the current floors (`backend_lines`, `backend_branches`,
  `frontend_lines`, `frontend_branches`). `ratchets/budgets.json` holds absolute bundle budgets
  (`entry_js_gz_kb` 250, `total_js_gz_kb` 1600). CI's `ratchet` job fails on any value below its
  floor or over its budget.
- Task pull requests never edit `ratchets/`. CI rejects such a change unless the branch starts with
  `chore/ratchet-`. After each wave merges, the controller raises the floors from a fresh download
  of only the three ratchet inputs (a stale `artifacts/` would be read as current, and the run's
  image tars are large):

  ```bash
  rm -rf artifacts
  gh run download <id of the latest main ci run> -D artifacts \
    -n backend-coverage -n frontend-coverage -n bundle-stats
  python3 scripts/ratchet.py update     # floor = max(old, max(90, floor(measured) - 1)); never lowers
  ```

  The controller then opens `chore/ratchet-wave-<N>`, which merges like any other pull request.

## Dependencies and lockfiles

- Plan 01 declares the complete Phase-1 dependency set in `backend/pyproject.toml` and
  `frontend/package.json`. Task pull requests never change the dependency lists, `uv.lock` or
  `pnpm-lock.yaml`; tool-config sections and scripts may change.
- A genuinely new package first lands in a controller pull request `chore(deps): add <pkg>` on
  branch `chore/deps-<pkg>` (manifest and lockfile only). The task then rebases onto it.
- Never hand-merge a lockfile conflict. Regenerate the lockfile, then commit it:
  - backend: `git checkout origin/main -- backend/uv.lock && (cd backend && uv lock)`
  - frontend: `(cd frontend && pnpm install)`
- `tools/trophy_art` has its own `pyproject.toml` and is exempt.

## Continuous integration and deployment

- `.github/workflows/ci.yml` runs on every pull request, on pushes to `main` and on demand. Its jobs
  are `backend`, `frontend`, `ratchet`, `docker`, `stack-config` and `e2e`, plus the aggregate
  `ci-ok` (the only required check), which fails if any job fails, is cancelled or is skipped.
  `scripts/tests/test_ci_config.py` guards this shape. A new job needs no `if:` and must be added
  to `ci-ok.needs`.
- Images are published to GHCR only from CI-green `main` commits (`publish` job). Once the
  repository variable `PUBLISH_ON_PUSH` is `true`, the Swarm's `deployer` service rolls each
  published commit out by itself (`deploy/README.md`, "Automatic deploys"). Migrations must stay
  expand/contract, because a rollback runs the previous release on the newer schema.
- Branch protection on `main` is applied once, with the owner's OK, by
  `scripts/setup-branch-protection.sh`, after `ci-ok` has run on `main` at least once.
