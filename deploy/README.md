# Deploying Sunday Clays to the Swarm

Stack `sundayclays`, public at https://sundayclays.claysmasher.com through the Cloudflare Tunnel (see
"Public access (Cloudflare Tunnel)"), and on the LAN through the internal Traefik (`traefik_public`
network, `websecure` entrypoint, `cloudflare` certresolver). Caddy serves the SPA and proxies `/api`
on plain `:80` inside the stack. `api`, `worker`, `db` and `backup` publish no
ports and never join `traefik_public`.

## Preconditions (not built by this repo)

- Two paths reach Caddy, and both peers are in a private range: the Cloudflare Tunnel
  (`cloudflared` → `traefik-public` → Caddy over `edge_public`, where Cloudflare sets
  `CF-Connecting-IP`) and the LAN (`traefik-v3` → Caddy over `traefik_public`, where Traefik has no
  `forwardedHeaders.trustedIPs` on `websecure` and sets `X-Forwarded-For` to the LAN client; verified
  in `swarm-config/traefik-v3`). Caddy trusts forwarding headers only from private ranges
  (`TRUSTED_PROXIES=private_ranges` in `compose.swarm.yaml`; it publishes no ports, so only those two
  overlays reach it), reads `CF-Connecting-IP` first and `X-Forwarded-For` second
  (`client_ip_headers` in `deploy/caddy/Caddyfile`), and always overwrites `X-Real-IP`, which is the
  only client-IP header the API reads. The LAN router strips any `CF-Connecting-IP` a client sends
  (`sundayclays-strip-cf`), so the LAN path cannot be spoofed. Never publish Caddy ports with
  `mode: host`.
- Images are published to GHCR by the CI `publish` job only from CI-green `main` commits. Set the
  repository variable `PUBLISH_ON_PUSH=true` before the first deploy, or run the `ci` workflow on
  `main` with "Run workflow" (workflow_dispatch). Tags are `sha-<7>` and `latest`; deploy `sha-<7>`.
- Every `sha-<7>` image is multi-arch (`linux/amd64` + `linux/arm64`), so `caddy`, `api` and `worker`
  run on any node, Raspberry Pi or Proxmox VM, and Swarm moves them when a node goes away. Only `db`
  and `backup` are pinned, by hostname, to the database node (`autopirate`). The worker is limited
  to 1 GiB of memory.
- On each Raspberry Pi node, `docker info 2>&1 | grep -i 'memory limit'` must print nothing. A
  `No memory limit support` warning means the kernel's memory cgroup is off and the limits are
  ignored: add `cgroup_enable=memory cgroup_memory=1` to the kernel command line and reboot.
- Every node pulls the app images from the fleet registry, `registry.thehalf.io` (a plain
  `registry:3` behind Traefik, pinned to `autopirate`), never from `ghcr.io`: not every node can
  reach GHCR. The deployer copies each release from GHCR into it ("Automatic deploys" →
  "Mirroring"), so only the manager running the deployer needs a `docker login ghcr.io`. The
  stack's images are `registry.thehalf.io/sunday-clays-<image>:sha-<7>`; `SC_REGISTRY` overrides the
  host, and `scripts/check_stack.py` rejects any `ghcr.io` reference in the stack. The registry has
  no auth, so anything on the LAN can push to it; that matches the rest of the fleet.
- Tags published before Plan 13 are amd64-only and are not supported on the mixed fleet. Swarm keeps
  a task off nodes its image does not support only when `docker stack deploy` (or
  `docker service update`) can read the image's index from the registry. If a deploy prints
  `could not be accessed on a registry to record its digest`, stop: it deployed with no platform
  restriction, and an amd64-only image on a Pi crash-loops with `exec format error`. Check that
  `registry.thehalf.io` answers from the node and that the tag was mirrored, then deploy again
  before anything else.

## Public access (Cloudflare Tunnel)

The public edge is the fleet's Cloudflare Tunnel: visitor → Cloudflare (TLS, WAF) → tunnel →
`cloudflared` → `traefik-public` (file provider, plain `:80`, network `edge_public`, no host ports)
→ `sundayclays_caddy`. There is no Cloudflare Access (owner decision): the app's two passwords are the
only gate, and the app limits logins to 10 failures / 15 min per real client IP. The stack side is
in `compose.swarm.yaml` (Caddy joins the external `edge_public` network), but the deployer only
swaps images, so a stack that is already running needs a hand deploy first. Trust limit:
`TRUSTED_PROXIES=private_ranges` trusts every container on `edge_public` and `traefik_public`, so a
compromised neighbour that reaches Caddy directly could set `CF-Connecting-IP` and dodge the per-IP
login limit (the same was already true of `X-Forwarded-For` on `traefik_public`). The owner steps
below are in the `swarm-config` repo, in this order (ingress last, as `cloudflared/config.yml`
itself warns):

0. If the stack is already running, hand-deploy it per "Deploy or upgrade" so Caddy joins
   `edge_public` and picks up the strip labels. Confirm with
   `docker service inspect sundayclays_caddy --format '{{json .Spec.TaskTemplate.Networks}}'`,
   which must include `edge_public`. Do this before touching `routes.yml`.

1. `traefik-public/dynamic/routes.yml`:
   - Add router `sundayclays-public`: rule ``Host(`sundayclays.claysmasher.com`)``, entryPoints
     `web`, service `sundayclays-public`, middlewares `sundayclays-throttle` then `edge-headers`.
   - Add service `sundayclays-public`: `loadBalancer` server `http://sundayclays_caddy:80`,
     `passHostHeader: true`.
   - Add middleware `sundayclays-throttle`:
     `rateLimit: {average: 300, burst: 100, period: 1m, sourceCriterion: {requestHeaderName: CF-Connecting-IP}}`.
     The shared `edge-ratelimit` keys on the `cloudflared` container, so it would be one bucket for
     every visitor.
   - Check that `edge-headers` sets no `Content-Security-Policy` or `Cache-Control`, which would
     replace Caddy's. It does not today (HSTS, nosniff, referrer policy and frame options only). If
     it ever does, use a sundayclays-specific headers middleware without those.
2. Deploy `traefik-public`: `docker stack deploy -c /var/data/config/traefik-public/docker-compose.yml traefik-public`.
3. `cloudflared/config.yml`:
   - Add `- hostname: sundayclays.claysmasher.com` / `service: http://traefik-public:80` above the
     `http_status:404` fallback.
   - Delete any existing A or CNAME record for `sundayclays.claysmasher.com` first (or edit it into
     the proxied tunnel CNAME); `route dns` fails if the name already has a record.
   - Run `cloudflared tunnel route dns thehalf-edge sundayclays.claysmasher.com`. The tunnel login
     must have authorized the `claysmasher.com` zone; otherwise create the proxied CNAME to
     `<UUID>.cfargotunnel.com` by hand.
   - `docker service update --force cloudflared_cloudflared`.
4. Cloudflare dashboard for `claysmasher.com`:
   - SSL/TLS → Edge Certificates → **Always Use HTTPS** on.
   - Leave the default cache behaviour: the API sends `private, no-cache` and `/api/*` has no
     cacheable extension; `/assets/*` is immutable and may be cached.
   - Do **not** add Cloudflare Access.
5. Check the result:
   - `curl -sI https://sundayclays.claysmasher.com/` returns 200 with Caddy's
     `Content-Security-Policy` header.
   - Log in with a wrong password from two different networks (e.g. home Wi-Fi and phone data). On
     the DB node, `docker exec $(docker ps -qf name=sundayclays_db) psql -U sunday -d sunday_clays -c "select ip, at from login_attempts order by at desc limit 5"`
     must show two distinct public IPs, not a Cloudflare or overlay address.
   - LAN spoof check (internal Traefik must strip the header): from the LAN, send a wrong password
     with `curl -H 'CF-Connecting-IP: 203.0.113.9' -d '<wrong password>' https://sundayclays.claysmasher.com/api/<login path>`.
     The newest `login_attempts.ip` must be the LAN client's address, not `203.0.113.9`.

On the LAN the site answers at `https://sundayclays.thehalf.io` (router `sundayclays-lan`, the
fleet's `*.thehalf.io` wildcard DNS and certificate) and at `sundayclays.claysmasher.com` through
the internal Traefik once that name resolves to the ingress VIP. Both LAN routers strip
`CF-Connecting-IP`.

## One-time setup (on a manager node)

1. Only for the first deploy ("Turn it on"), log in to GHCR on this manager with the packages-only
   token (1Password "Github PAT - Packages Only", field `token`, the same token as
   `deployer_ghcr_token`). Once the deployer runs, it logs in by itself, and no other node ever
   needs a GHCR login:

   ```bash
   echo "$GHCR_PAT" | docker login ghcr.io -u <github-user> --password-stdin
   ```

2. Check out this repository at `/var/data/config/sunday-clays` (the fleet keeps every stack's
   config under `/var/data/config`; the app's data lives in `/var/data/sunday-clays`) and create
   `./secrets/` next to `compose.yaml` and `compose.swarm.yaml` (gitignored). Every hand
   `docker stack deploy` below runs from that directory. `scripts/dev-secrets.sh` needs `uv` and `openssl`. Type the real passwords and the
   ping URL at a silent prompt, so they never land in shell history or `ps` output. (Once Plan 04 has
   landed you can instead write the two hashes with
   `docker run --rm -it registry.thehalf.io/sunday-clays-backend:sha-<7> python -m sunday_clays.auth.hashpw`
   once that tag is mirrored, see "Turn it on".)

   ```bash
   read -rsp 'Viewer password: ' VIEWER_PASSWORD && echo && export VIEWER_PASSWORD
   read -rsp 'Admin password: ' ADMIN_PASSWORD && echo && export ADMIN_PASSWORD
   scripts/dev-secrets.sh && unset VIEWER_PASSWORD ADMIN_PASSWORD
   read -rsp 'Healthchecks ping URL: ' hc_url && echo && printf '%s\n' "$hc_url" > secrets/backup_hc_url
   unset hc_url && chmod 600 secrets/*
   ```

   `secrets/backup_hc_url` holds the Healthchecks.io ping URL of the nightly-backup check (create
   the check first: period 1 day, grace 2 hours). To turn the ping off, leave only a newline in it
   (`printf '\n' > secrets/backup_hc_url`): Swarm rejects an empty secret, and the backup service
   treats a URL that is blank after trimming whitespace as "no ping".

3. On the database node (`autopirate`; override with `SC_DB_NODE=<hostname>` at deploy time) create
   the data directories with the owners the containers run as:

   ```bash
   sudo install -d -o 999 -g 999 /var/data/sunday-clays/db        # postgres:17 (Debian) uid
   sudo install -d -o 10001 -g 10001 /var/data/sunday-clays/backups   # backend image uid
   ```

4. Off-site copies: add `/var/data/sunday-clays/*` to the fleet restic set (nightly at 03:30 to
   lakitu, then Backblaze). The app's own dump runs at 02:30 America/Los_Angeles, before restic.

## Deploy or upgrade

Once the stack runs, the `deployer` service puts every CI-green `main` commit live by itself
("Automatic deploys" below). Run `docker stack deploy` by hand only for the first deploy ("Turn it
on"), after a change to `compose*.yaml` or a secret, or to refresh the deployer itself. Always
pause the deployer first (otherwise the hand deploy races a rollout in progress), deploy the tag
the deployer recorded as live (so the command changes configuration, not code), and resume it
afterwards (the pause survives the deployer's restart, so without `resume` automatic deploys stay
off for good). On the manager the deployer runs on (`docker service ps sundayclays_deployer`), in
the directory holding `compose*.yaml` and `secrets/`, run these lines one at a time:

```bash
export GHCR_USER=<github-login>    # owner of the read:packages token ("Automatic deploys" → "Tokens")
D=$(docker ps -q -f name=sundayclays_deployer)
docker exec "$D" python3 /app/deployer.py pause "stack deploy"   # waits for a rollout in progress
export IMAGE_TAG=$(docker exec "$D" python3 /app/deployer.py tag)
[[ $IMAGE_TAG =~ ^sha-[0-9a-f]{7}$ ]] && echo "deploy $IMAGE_TAG" || echo "STOP: bad tag '$IMAGE_TAG'"
docker stack deploy -c compose.yaml -c compose.swarm.yaml sundayclays
D=$(docker ps -q -f name=sundayclays_deployer)   # the deployer may have been recreated
docker exec "$D" python3 /app/deployer.py resume
curl -fsS https://sundayclays.claysmasher.com/api/health   # {"status":"ok","version":"sha-<7>"}
```

- Do not run `docker stack deploy` if the check printed `STOP`. `deployer.py tag` fails with
  `no deploy recorded` only when the deployer's state is empty (a fresh volume, or the task moved
  to another manager); then use the `version` that `/api/health` reports, which is the live
  release because a failed rollout is always rolled back as a whole.
- Never take `IMAGE_TAG` from an old command line or from a single service's image: an older tag
  makes the deployer see drift and put the recorded release straight back after `resume`.
- `api` runs `alembic upgrade head` before uvicorn. Every service updates stop-first (Swarm's
  default; `worker`, `db` and `backup` also set it), so an old and a new `api` never run together
  and the site is briefly down while the new `api` migrates and starts.
- Services update independently, so the previous release's `worker` can still run against the
  migrated schema until its own update; expand/contract migrations keep that safe.
- `api`, `worker`, `caddy` and `backup` roll back by themselves (`failure_action: rollback`): a new
  task that never turns healthy, or fails within 60 s of starting, puts that service back on its
  previous image. `db` never rolls back automatically.
- `worker`, `db` and `backup` run one replica each; the worker gets 5 minutes to finish its current
  job.
- `IMAGE_TAG` and `GHCR_USER` are required (`${…:?}`); `latest` is never deployed. The tag must
  also have a `sunday-clays-deployer` image, which every tag published after Plan 13 has; to go
  back to an older release, use `deployer.py rollback` ("Rollback"), which never touches the
  deployer.
- `docker stack deploy` needs no `--with-registry-auth`: the fleet registry takes no credentials.
- If `docker stack deploy` prints `could not be accessed on a registry to record its digest`, stop
  and make `registry.thehalf.io` reachable: without the index, Swarm gets no platform list and may
  put an image on a node of the wrong architecture. Tags published before Plan 13 are amd64-only and are
  not supported on this fleet ("Preconditions").

## Automatic deploys

The `deployer` service (`deploy/deployer/deployer.py`, one task on a Swarm manager) asks GitHub for
`main`'s SHA every 2 minutes (`git ls-remote`). When `main` has moved and CI has published
`sunday-clays-backend`, `-frontend` and `-deployer` at `sha-<7>` to GHCR (the `publish` job runs only
after `ci-ok` passes on `main`), it mirrors the three into `registry.thehalf.io`, then runs
`docker service update --image registry.thehalf.io/…:sha-<7>` on `api`, waits until `/api/health`
reports `sha-<7>`, then updates `worker`, `caddy` and `backup`, and records the SHA in its
`deployer-state` volume. A service already on that image is skipped.

- **Mirroring.** For each image the deployer runs
  `docker buildx imagetools create --tag registry.thehalf.io/sunday-clays-<image>:sha-<7> ghcr.io/gitgat/sunday-clays-<image>:sha-<7>`,
  which copies the whole multi-arch index from registry to registry (nothing is pulled onto the
  node), then reads the copy back and refuses the release unless it lists exactly `linux/amd64` and
  `linux/arm64` (one platform only, or an `unknown/unknown` attestation entry, fails). Never push
  per-arch tags by hand: a tag without an index strands the nodes of the other architecture. An
  image already mirrored with an identical index is skipped, so a restart copies nothing. The
  mirror runs before any service is touched: if it fails, nothing is updated, the failure is
  recorded like any failed deploy, and that SHA waits for the next commit. Rollback mirrors its tag
  again first, so it works even if a registry GC removed it.
- **Registry GC** (`registry-gc`, `--delete-untagged`) deletes only untagged blobs, so every
  mirrored release stays and rollbacks keep working. Do not delete old `sha-<7>` tags from the
  registry you may still roll back to.

- It never touches `db`, and it never updates itself: a process cannot supervise its own
  replacement. A hand `docker stack deploy` (above) refreshes it.
- A failed step stops the rollout. Swarm has already rolled the failed service back; the deployer
  then rolls back the services it had already updated (`worker`, then `api`), so the whole stack is
  on the previous release again, and leaves the later services alone. Nothing is recorded as
  deployed (`status` shows it under `last_failure`), and that SHA is not tried again until `main`
  moves or the deployer restarts.
- While `main` is unchanged it checks, every poll, that the four services still run the recorded
  tag. If one does not (a hand deploy with an old tag, a later Swarm rollback), it logs `drift: …`
  and redeploys the recorded tag. A paused deployer does not check.
- Every image is published for `linux/amd64` and `linux/arm64`, and a `sha-<7>` tag appears only
  once both architectures are pushed. The `publish` run tags the deployer image first and the
  backend/frontend pair last, so a publish run whose deployer build breaks, on either
  architecture, deploys nothing. CI's `docker` and `docker-arm64` jobs build the deployer image on
  every PR, so that should not reach `main`.
- If the deployer's loop hangs, its container `HEALTHCHECK` notices only after about 4 hours (the
  heartbeat limit, longer than the slowest rollout) plus 3 failed checks 60 s apart, and Swarm
  then restarts it. Do not expect a faster restart; `docker service update --force
  sundayclays_deployer` restarts it at once.
- The deployer holds the Docker socket, which means root on that manager. It is the only service
  allowed to (`scripts/check_stack.py`).

### Tokens

1. **GitHub token** (for `git ls-remote`): a fine-grained personal access token with resource owner
   `gitgat` (a user account, so the token is created while signed in as `gitgat`), access to the
   repository `gitgat/sunday-clays` only, and permission Contents: Read-only (GitHub adds
   Metadata: Read-only). Nothing else. Note its expiry date.
2. **GHCR token** (for the mirror's reads and `docker login`): a classic personal access token with
   only `read:packages` (GHCR does not take fine-grained tokens): 1Password "Github PAT - Packages
   Only", field `token`. The one from "One-time setup" step 1 is the same token. A classic
   token can read every package its owner can see, so prefer one owned by a dedicated machine
   account that is a collaborator on `gitgat/sunday-clays` with read access only (the packages
   inherit the repository's access).
3. On the manager, next to the other secret files:

   ```bash
   read -rsp 'GitHub contents:read token: ' t && echo && printf '%s\n' "$t" > secrets/deployer_github_token
   read -rsp 'GHCR read:packages token: ' t && echo && printf '%s\n' "$t" > secrets/deployer_ghcr_token
   unset t && chmod 600 secrets/deployer_*
   ```

To rotate a token, write the new value into its file, then run the "Deploy or upgrade" sequence
with `export DEPLOYER_SECRETS_REV=2` (then 3, and so on) before `docker stack deploy`. This counter
is separate from `SECRETS_REV`, so the app's six secrets stay put. Afterwards remove the old
versions with
`docker secret ls --format '{{.Name}}' | grep -E '^sundayclays_deployer_.+_v1$' | xargs -r docker secret rm`.
An expired or wrong token shows in the logs as `poll failed: git ls-remote failed (exit 128)` or
`poll failed: docker login ghcr.io failed`.

### Turn it on (first deploy)

The deployer runs on any Swarm manager, Raspberry Pi (`birdo`) or VM: its image, like the app
images, is published for both `linux/arm64` and `linux/amd64`.

1. With the owner's OK, publish from every CI-green `main` commit:
   `gh variable set PUBLISH_ON_PUSH --body true --repo gitgat/sunday-clays`. Each merge to `main`
   then also runs the `publish` jobs (one cached build per image and architecture, then a merge;
   a few Actions minutes).
2. Wait for the `publish` run of the newest `main` commit. The stack pulls the deployer's own
   image from the fleet registry too, so bootstrap by hand: on a manager with the GHCR login
   ("One-time setup" step 1), mirror all three images, check them, then deploy the tag once
   (there is no deployer to pause yet):

   ```bash
   docker buildx version   # precheck: the buildx plugin must be installed on this manager
   TAG=sha-<7>
   for i in backend frontend deployer; do
     docker buildx imagetools create --tag "registry.thehalf.io/sunday-clays-$i:$TAG" \
       "ghcr.io/gitgat/sunday-clays-$i:$TAG"
   done
   for i in backend frontend deployer; do   # each must list linux/amd64 and linux/arm64
     docker buildx imagetools inspect "registry.thehalf.io/sunday-clays-$i:$TAG"
   done
   export GHCR_USER=<github-login>
   IMAGE_TAG=$TAG docker stack deploy -c compose.yaml -c compose.swarm.yaml sundayclays
   ```

   Later hand deploys of a tag the deployer has not mirrored: `docker exec "$D" python3
   /app/deployer.py mirror sha-<7>` (logs in, mirrors, updates no service), then
   `IMAGE_TAG=sha-<7> docker stack deploy …`.
3. `docker service logs -f sundayclays_deployer` shows `deployer: watching … main every 120s`.
   From then on, a merge to `main` is live a few minutes after its `publish` run finishes.

Every automatic deploy restarts `worker` (it gets 5 minutes to finish its job), `caddy` (a few
seconds of errors) and `backup` (which takes a fresh dump on start). Pause around club shoots:
`deployer.py pause "club shoot"`, then `resume` afterwards.

### Talking to it

`docker service ps sundayclays_deployer` shows the manager it runs on. Run these on that node:

```bash
D=$(docker ps -q -f name=sundayclays_deployer)
docker exec "$D" python3 /app/deployer.py status          # live SHA and tag, pause, last failure, last 20 deploys
docker exec "$D" python3 /app/deployer.py tag             # just the live tag
docker exec "$D" python3 /app/deployer.py pause "club shoot"
docker exec "$D" python3 /app/deployer.py resume
docker exec "$D" python3 /app/deployer.py mirror sha-<7>  # copy a release into registry.thehalf.io, deploy nothing
```

`pause` waits for a rollout in progress to finish. The state lives in the node-local
`deployer-state` volume: if the task moves to another manager, it starts empty, records `main`
(without updating anything when that is already live) and forgets a pause, so pause again after a
failover.

### Rollback

- **Automatic:** see above. Check `docker service ps sundayclays_<service>` for the failed task,
  `deployer.py status` for `last_failure`, and `docker service logs sundayclays_deployer` for
  `deploy sha-<7> FAILED: …`.
- **Manual, to an earlier release:**

  ```bash
  docker exec "$D" python3 /app/deployer.py status               # history lists earlier tags
  docker exec "$D" python3 /app/deployer.py rollback sha-<7>
  ```

  `rollback` mirrors the tag again first, so the tag must still be published in GHCR. If GHCR no
  longer has it, use the manual loop below from what `registry.thehalf.io` still holds.

  This updates `api`, `worker`, `caddy` and `backup` in the usual order (skipping any already on
  that tag) and **pauses** automatic deploys, because otherwise the next poll would put `main`
  straight back. Once `main` has the fix, run `resume`. Roll back only to a tag in the `history`,
  for two reasons: those were all built after the rollback-safe start-up (Plan 13 Task 3), and an
  older image crashes on a migrated database with `Can't locate revision`; and they are all
  multi-arch, while older tags are amd64-only and can land on a Pi if Swarm cannot read their
  platforms ("Preconditions").

  Rolling back past migration 0005 (lettered stations such as 7A) is limited once a lettered
  Sunday has been imported. The older release still starts, but its rebuild fails on the
  `station_layouts` key, its joins count 7A twice, and a station reset rule for "7A" crashes its
  reset loader. So roll back that far only for a short fix, and do not import or rebuild until
  `main` is back. The migration's docstring has the details.
- **Retry a failed SHA** without a new commit: `docker service update --force sundayclays_deployer`.
- **Without the deployer** (if it is itself broken): stop it with
  `docker service scale sundayclays_deployer=0` (a later `docker stack deploy` sets it back to 1),
  then on a manager run the loop below. It goes in the same order as the deployer and stops at
  the first failure; if it stops, run it again with the previous tag so the stack is not left
  split between two releases.

  ```bash
  TAG=sha-<7>   # a tag from the deployer's history; stop if an update prints "could not be accessed"
  for i in backend frontend; do   # only if a registry GC removed the tag; needs the GHCR login
    docker buildx imagetools create --tag "registry.thehalf.io/sunday-clays-$i:$TAG" \
      "ghcr.io/gitgat/sunday-clays-$i:$TAG"
  done
  for s in api worker caddy backup; do
    kind=backend; [ "$s" = caddy ] && kind=frontend
    docker service update --image "registry.thehalf.io/sunday-clays-$kind:$TAG" \
      "sundayclays_$s" || { echo "stopped at $s"; break; }
  done
  ```

  When the deployer comes back, it compares the services with its recorded tag and puts that
  release back ("drift"). Before scaling it up, either `pause` it first or make sure `main` has
  the release you want.
- **The schema:** the previous release runs on the newer schema, because migrations are
  expand/contract. Its `api` logs `database schema is newer than this image's migrations (a
  rollback); starting without migrating (database at …, image head …)` and starts, and its
  `worker` accepts the schema too. Rolling back further than one release is safe only if no
  migration in between removed or renamed something the older code uses. Otherwise restore a
  backup ("Backups and restore").

### Logs

`docker service logs -f --since 1h sundayclays_deployer`:

- `deploy sha-<7>: updating sundayclays_<service>` … `deploy sha-<7>: done`: a rollout
  (`… already on sha-<7>` for a service that needed nothing).
- `mirror sha-<7>: ghcr.io/… -> registry.thehalf.io/…` (or `… already there`): the release copied
  into the fleet registry before the rollout. `deploy sha-<7> FAILED: mirror: …` means the copy
  failed or the index was not exactly amd64 + arm64; nothing was updated.
- `sha-<7>: waiting for …`: CI has not finished publishing that commit (or it failed CI). Logged
  once per commit.
- `deploy sha-<7> FAILED: …; rolled back …`: stopped, and the services it had updated are back on
  the previous release. Nothing recorded as deployed; see "Rollback".
- `drift: sundayclays_<service> runs …; recorded sha-<7>, redeploying it`: something other than the
  deployer changed a service's image.
- `poll failed: …`: GitHub or GHCR unreachable, or a token is wrong or expired. (A registry.thehalf.io
  outage shows as `deploy sha-<7> FAILED: mirror: cannot …`.)
- `WARNING … database schema is newer than this image's migrations`, logged by `api` at start-up:
  expected right after a deliberate rollback ("Rollback") or a failed deploy (`deploy sha-<7> FAILED: …`
  in the deployer's log), because the previous `api` is put back after the new one migrated.
  Otherwise it needs investigating: an image older than the database is running with no rollback
  behind it, for example a hand deploy with an old tag.
- No lines at all between deploys is normal: an unchanged `main` is silent.

## Rotating a secret

Swarm secrets are immutable, so a rotation creates a new version. `SECRETS_REV` versions all six
secrets together: bumping it re-creates every one of them from `./secrets/` (keep all six files in
place) and leaves all six `_v<old>` secrets orphaned.

```bash
# 1. put the new value in ./secrets/<name>
# 2. run the "Deploy or upgrade" sequence (pause, IMAGE_TAG from `deployer.py tag`, GHCR_USER,
#    resume) with `export SECRETS_REV=2` before its `docker stack deploy`
# 3. once the services are healthy, remove all six previous versions (not the deployer's tokens,
#    which have their own DEPLOYER_SECRETS_REV)
docker secret ls --format '{{.Name}}' | grep -E '^sundayclays_.+_v1$' | grep -v '^sundayclays_deployer_' \
  | xargs -r docker secret rm
```

- A `db_password` change also needs `ALTER ROLE sunday PASSWORD '<new>';` (Postgres reads
  `POSTGRES_PASSWORD_FILE` only when it initialises an empty data directory) and a matching
  `database_url` in the same revision.
- Rotating `viewer_password_hash` or `admin_password_hash` signs out that role only; rotating
  `session_secret` signs out everyone.

## Backups and restore

- The `backup` service writes a verified custom-format dump at container start and daily at 02:30
  America/Los_Angeles to `/var/data/sunday-clays/backups` (`sc-<UTC>.dump`), keeps the newest dump per
  day for 14 days and per ISO week for 8 weeks (pruned by date), touches `last_success` and pings
  Healthchecks (`/fail` on error).
- Every run, the service's own and `verify-restore.sh`'s, holds an exclusive lock on
  `backups/backup.lock`. A second run waits for the first for up to 10 minutes
  (`BACKUP_LOCK_TIMEOUT`, seconds), then fails like any failed dump (exit 1, `/fail` ping).
- The `backup` task runs on the database node (`autopirate`), so run the `docker exec` commands
  below on that node (`docker service ps sundayclays_backup` shows where it runs); run
  `docker service scale` on a manager.
- Take a fresh dump and check that it restores cleanly into a scratch database (live data is not
  touched):

  ```bash
  docker exec "$(docker ps -q -f name=sundayclays_backup)" /app/backup/verify-restore.sh
  ```

- Restore a dump over the live database (stop the writers first):

  ```bash
  docker service scale sundayclays_api=0 sundayclays_worker=0                    # on a manager
  docker exec -it "$(docker ps -q -f name=sundayclays_backup)" \
    /app/backup/restore.sh /backups/sc-<stamp>.dump                              # on the db node
  docker service scale sundayclays_api=1 sundayclays_worker=1                    # on a manager
  ```

  `restore.sh <dump> [db]` is all or nothing. In one transaction it drops and recreates the `public`
  schema and replays the dump, so tables a newer migration added are gone afterwards. A dump that
  fails part-way leaves the database exactly as it was.
