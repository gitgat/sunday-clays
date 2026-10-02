# Sunday Clays: Polish & Reach (Plan 19) — Design Spec

> Date: 2026-10-02 · Status: draft for owner review · Parent spec: `2026-09-27-sunday-clays-design.md` · Contract: master plan C1–C12 (amendments in §2: D6, D21 and D24) · Base: `main` with Plans 15, 16 and 17 merged (`fc2a101`)
> Shared decision with Plan 20: Plan 19 builds the **launch switch** mechanism (§3.0); Plan 20 only adds keys to it.

Plan 19 makes the app easier to find, share and understand, without changing any number it already shows. It has seven parts: launch switches (the mechanism the other six ship behind), link previews, a first-visit tour with a glossary, a weekly recap for the club email, Add to Home Screen, club milestones, and a per-profile summary card.

---

## 1. Context and goals

**Where we are.** The app is password-gated (viewer and admin passwords, signed session cookie) and reached through a Cloudflare Tunnel at `sundayclays.claysmasher.com`. When someone pastes a link in a group chat, the chat app's crawler has no cookie, so the preview shows the login page or nothing. New visitors land on a dense Home with no guide to the words we use ("field-adjusted", "percentile", "special shoot"). The club email is put together by hand. Nothing marks the club's own round numbers (the 300th Sunday, the 350,000th clay). A shooter can share a lifetime profile image, but not "my last 3 months".

**Goals.**

1. Shared links show a clean, name-free preview: the club, and for a Sunday its date, turnout and round type.
2. A first visit gets a 5-step tour, and every explainer can link to a plain glossary.
3. An admin gets the week's recap as paste-ready text, Markdown and an image in one click.
4. Phones can install the app. It opens on Home, or on the viewer's own page when "Which one are you?" is set.
5. The club's own milestones are dated and celebrated on Home and on the Club page.
6. Any profile can produce a shareable summary for the header time window.
7. Each of goals 1–6 can be turned on for everyone, or off again, by an admin without a redeploy.

**Binding owner rules (restated; every section below follows them)**

| # | Rule | Where it is enforced in this plan |
|---|---|---|
| R1 | App copy never uses he/she/his/her (or him/hers/himself/herself). | All copy in §3. There is no central lint; each new copy file gets its own language test, named in §5.1, using the same banned-word list as the existing per-feature `explainers.test.ts` files (plus "class"). |
| R2 | Named-shooter copy is positive or neutral only. | Recap (§3.3), summary card zero-hiding (§3.6, D19). |
| R3 | No rating ranking, rivals or head-to-head. | Recap shows the podium only (D15); milestones are club-level (§3.5); summary card has no rank. |
| R4 | Every data chart has Table, CSV, fullscreen and an ELI5 explainer. | The one new chart (§3.5 "Club totals over time") uses `ChartFrame`. |
| R5 | Time windows use the header window: 8W/3M/6M/12M/YTD/All and custom. | Summary card (§3.6) and the milestones chart (§3.5). |
| R6 | The password gate stays. | Only `/api/og/*` is public, and it serves no names or scores (§3.1, D6). |
| R7 | Nothing is removed from Home. | Home only gains: `data-tour` attributes, one milestone card, one install tip (§3.2, §3.4, §3.5). |
| R8 | Real names never go in tracked files; tests use invented names. | Fixture pseudonyms only (`Devlin, Sid`, `Kaplan, Noel`, `Hadley, Ike`, `Kim, Pat`, …). |
| R9 | Persistent data binds under `/var/data/sunday-clays/<svc>`, never named volumes. | Plan 19 adds no persistent data (D22). |
| R10 | Images are multi-arch (amd64 + arm64). | The one new dependency, Pillow, ships manylinux wheels for both (D8). |
| R11 | No IPs stored (rate limits use `ip_fingerprint`), no access log. | §4. |

---

## 2. Decisions

1. **Launch switches live in `app_state`, one row per key.** The key is `feature.<key>` (for example `feature.summary_card`) and the value is `{"enabled": bool, "updated_at": "<ISO timestamp>"}`. `updated_at` is taken from the database (`now()` inside the upsert), never the app clock. A missing row means **off** (or the `FEATURES_DEFAULT_ON` default, D4). *Rationale:* `app_state` already exists (key `text` PK, `value jsonb`), so no migration is needed. One row per key means two admins flipping different switches never overwrite each other, and an upsert of one row is atomic. Two flips of the same key are last-writer-wins, with one `audit_log` row each.

2. **Gate semantics.** While a switch is off: an **admin** sees the feature with an "Admin preview" badge and its API answers normally; a **viewer** sees nothing, and the feature's viewer API routes answer **404 with the same body as an unknown `/api` path** (`{"detail":"Not Found"}`). The gate is the dependency `feature_gate("<key>")`, which raises `HTTPException(404)`. It runs after the router's `require_viewer`, so a request with **no session gets 401** (as on every gated route), never 404. *Rationale:* the 404 keeps a switched-off feature tidy: the page shows "Page not found" and the API agrees, with no special error state to design. It is **not** a secrecy claim: the JavaScript bundle ships every gated component and its copy, which is acceptable because nothing in an unreleased feature is private. To avoid listing unreleased keys needlessly, `GET /api/features` returns only the enabled keys to a viewer (D3).

3. **The switch API.** `GET /api/features` (viewer) answers `{"switches": {"<key>": true, …}}`: for a **viewer**, only the keys that are on (a missing key means off); for an **admin**, every registered key with its `bool`. `GET /api/admin/features` lists each switch with its label, description, `enabled` and `updated_at`. `PUT /api/admin/features/{key}` takes `{"enabled": bool}`, upserts the row, writes `audit_log` action `feature_switch` with `{key, enabled}`, and returns the switch. An unknown key is 404 `feature_not_found`. `/api/features` is added to the ETag middleware's no-store list, because switches change without a `data_version` bump. *Rationale:* same shape as the Plan 15 bump counts, which have the same staleness problem.

4. **`FEATURES_DEFAULT_ON` setting (default empty).** A comma-separated list of keys treated as on when their `app_state` row is missing. `compose.test.yaml` sets it to all six keys, so the read-only e2e projects see every feature. Production leaves it empty, so every feature starts off. *Rationale:* the shared e2e stack must exercise the features without a mutating setup step, and production launches must be deliberate.

5. **No migration in Plan 19.** Switches use `app_state` (D1); milestones, the summary and the recap are computed on read (D17, D18, D14); OG images are memoized in process (D8). `0009` stays free for Plan 20. *Rationale:* fewer moving parts, and a rollback to the previous release needs no data step. The previous release ignores the `feature.*` rows.

6. **One new public route module, `og` (C2 amendment).** `api/app.py`'s `PUBLIC_ROUTE_MODULES` becomes `{"health", "auth", "og"}`. This is a one-line contract change owned by the link-preview task. A test pins that every route in `og` is under `/api/og/` and accepts GET and HEAD only. The routes are declared with `@router.api_route(..., methods=["GET", "HEAD"])`, because FastAPI's `@router.get` answers HEAD with 405 and crawlers (and the runbook's `curl -sI`) send HEAD. *Rationale:* crawlers cannot log in. Keeping every public path in one small module under one prefix makes the unauthenticated surface easy to audit.

7. **Crawler routing in Caddy, plus a `/l/` share prefix.** Caddy sends GET/HEAD requests whose `User-Agent` matches the crawler list (§3.1.3), on any SPA path, to `/api/og/page/<path>`. Separately, `/l/<path>` is a share prefix: crawlers get the preview, and people get a 302 to `/<path>` (query string kept). App-generated share links (recap link, summary card) use `/l/…`, and every preview's `og:url` is the `/l/` form so a re-scrape by Facebook, iMessage or WhatsApp stays on the bypassed path. The crawler check and the `/l/` redirect sit inside one Caddy `route { … }` block, because Caddy sorts sibling `handle` blocks (single-path matchers before named matchers) and would otherwise run the redirect before the crawler check. The redirect target is built from a fixed `/` prefix and refuses paths that start with `//` or `/\`, so `/l//evil.com` cannot become an open redirect. *Rationale:* a Cloudflare Access policy cannot match on User-Agent. If Access is ever put in front, the only way crawlers get through is a path-scoped Bypass app, and `/l/*` plus `/api/og/*` is that path (runbook, §3.1.6). Without Access (today), every path previews.

8. **OG images are rendered server-side with Pillow.** Pillow `>=12.0` is added to `[project].dependencies` (manylinux wheels for x86_64 and aarch64, so the image stays multi-arch). Images are 1200×630 PNG, drawn from fixed fonts (Roboto Regular and Medium TTF, Apache-2.0, committed under `backend/src/sunday_clays/og/fonts/` with their LICENSE), fixed colours and fixed coordinates. They are saved with no metadata, so the same facts give the same bytes. They are memoized with `cached_by_data_version` (per process, LRU 256), and nothing is written to disk. The Sunday PNG is sent with `public, max-age=3600` (the generic one with `public, max-age=86400`); Cloudflare edge-caches `.png` by default, so a switch-off takes up to an hour to stop serving an already-cached Sunday image, and it never takes back a preview already posted in a chat. The runbook says so (§3.1.6). *Rationale:* crawlers do not run JavaScript, so the client-side `lib/share` path cannot serve them. A memo keyed by `data_version` is the existing cache pattern, and it needs no volume.

9. **One logo, drawn in code.** `sunday_clays/og/logo.py` draws the mark: a clay target in three-quarter view, an ellipse dome `#C76D3F` with rim `#9E5530` and an `#E8A77A` highlight ring, on a `#1A4D2E` rounded square. The OG renderer uses it directly. `uv run python -m sunday_clays.og.icons ../frontend/public/icons` writes the PWA icons, which are committed: `icon-192.png`, `icon-512.png`, `maskable-512.png` (mark inside the 80% safe zone), `apple-touch-icon.png` (180) and `favicon-32.png`. *Rationale:* the repo has no logo asset today, and one source keeps previews, icons and favicon identical.

10. **Previews are built from a facts object with no name field.** `PreviewFacts(kind: Literal["generic","sunday","special"], event_date: date | None, n_shooters: int | None, round_type: RoundType | None, label: str | None)`. The page HTML and the image are rendered only from it. *Rationale:* the type itself makes "never names or personal scores" structural. A test also scans every rendered preview for every fixture display name (§5).

11. **`PUBLIC_BASE_URL` setting** (default `https://sundayclays.claysmasher.com`) builds every absolute URL (`og:url`, `og:image`, recap link). The `Host` header is never used. *Rationale:* a spoofed Host must not poison a crawler's cached preview.

12. **The tour is hand-rolled, about 3 KB, with no new dependency.** A modal dialog with a spotlight ring, remembered in `localStorage` `sc.tour.v1 = "done"`. *Rationale:* the bundle budgets in `ratchets/budgets.json` are absolute, and tour libraries are 15–40 KB and bring their own focus handling, which would need auditing anyway.

13. **The glossary is static frontend content.** The `Explainer` type gains `terms?: readonly GlossaryTermId[]`, and an explainer renders "Words used here" links to `/glossary#<id>`. A lint test requires the matching term id whenever an explainer's text uses a glossary trigger phrase. *Rationale:* definitions are copy, not data, and the lint keeps deep links from rotting as explainers change.

14. **The recap is backend facts plus frontend formatting.** `GET /api/admin/recap/{date}` returns structured facts. `features/admin-recap/format.ts` turns them into plain text and Markdown (pure functions with golden-string tests), and the PNG is rendered client-side through `lib/share`. Competition-category trophies (First Win, Podium, Station Top Gun, Hardest-Station Clean) are left out of the recap's trophy list, and out of the summary card's trophy count and names (§3.6). *Rationale:* the server owns the rules (PB rule, podium ties, first-timers) and the client owns the wording. Competition trophies would be ranking beyond the podium.

15. **The podium is the best rounds with `event_rank <= 3`.** `event_rank` is already the min-rank of best rounds (ties share), so a tie for 1st at 49 shows as "Tied 1st", and the next place is 3rd. Every shooter tied at a place is listed. Nothing below 3rd is ever named. *Rationale:* this reuses the existing tie rule, so the recap agrees with the Sunday page.

16. **PWA: manifest linked at runtime, service worker built by Vite, never `/api`.** `index.html` keeps no manifest link. `features/pwa` injects `<link rel="manifest" href="/manifest.webmanifest">` and registers `/sw.js` only while the `pwa` feature is visible. Existing registrations are unregistered **only** on a definite off: a successful `/api/features` response for a viewer that does not contain `pwa`. A pending, failed (network error) or 401 query, and the logged-out `/login` page (where `useFeatures` is not enabled), leave the service worker alone. The service worker is emitted by a small inline Vite plugin (`pwaShell()` in `vite.config.ts`) that lists the build's entry files. *Rationale:* the switch must really turn installability off, a hand-written SW cannot know the hashed filenames, and a logged-out load must not wipe an installed app.

17. **Club milestones are computed on read.** `analytics/club_milestones.py` computes them from `load_rounds` (regular only), `load_appearances` and `load_calendar` (special included), behind `@cached_by_data_version`, with `as_of` (default: the latest scored Sunday, `_filters.LAST_SCORE_DATE_SQL`, as elsewhere). The thresholds are a declared table. *Rationale:* this follows the existing club analytics pattern, and about 320 Sundays make the cumulative sums trivial.

18. **The summary card gets one new endpoint, `GET /api/shooters/{id}/summary?from=&to=`** (in `api/routes/shooters.py`; `from` is optional, an open start for the "All" window). `GET /api/shooters/{id}?since=&as_of=` already returns `window_stats`, but not Sundays including specials, PBs set, trophies in the window or the longest streak inside it. Rebuilding those client-side would duplicate the streak and PB rules. The endpoint ignores the round-type filter and the card says "All round types". *Rationale:* one source for each rule. A PB set in a round-type slice is not a PB.

19. **Zero-valued lines are hidden on named-shooter surfaces.** On the summary card and in the recap, a line whose value is 0 ("Personal bests 0", "Trophies 0"), or a streak below 2, is omitted rather than shown. *Rationale:* rule R2. "0 personal bests" next to a name reads as a negative.

20. **`lib/share.ts` gains `renderElementToPng(el)` and `downloadElementAsImage(el, filename)`.** `shareElementAsImage` is refactored onto `renderElementToPng`, with its behaviour and tests unchanged. *Rationale:* the summary card's "Download image" and the recap's PNG need a download that never opens the share sheet.

21. **Nav items and routes can name a feature (C10 amendment).** `NavItem` gains `feature?: FeatureKey`, and nav rendering hides an item whose feature is not visible. The new `<FeatureGate feature="…">` wraps a gated page. For a viewer with the switch off, it renders the same "Page not found" view that `RouteErrorPage` shows for unknown paths (extracted as `NotFoundView` from `app/ErrorBoundary.tsx`). *Rationale:* gating stays declarative in each feature's `routes.tsx`, so `router.tsx` is not edited.

22. **No new persistent data, volumes or services.** Everything new is either computed on read, kept in `app_state`, held in a process memo, or kept in the viewer's own browser storage. *Rationale:* rule R9 is met trivially, and backups need no change.

23. **Six switch keys.** `link_previews`, `tour_glossary`, `weekly_recap`, `pwa`, `club_milestones`, `summary_card`. They are declared once in `backend/src/sunday_clays/domain/features.py` as `FeatureKey = Literal[...]` plus the `FEATURES` tuple (key, label, description). The frontend gets the union from the generated `schema.d.ts`. Plan 20 appends to this tuple. *Rationale:* one registry, typed end to end. A test asserts that the admin page lists exactly `FEATURES`.

24. **e2e runs with service workers blocked, except the PWA spec (C10 amendment).** `frontend/playwright.config.ts` gains `serviceWorkers: 'block'` in the shared `use` block, and `pwa.spec.ts` opts back in with `test.use({ serviceWorkers: 'allow' })`. The C10 comment in that file gains "and Plan 19 T9 (serviceWorkers)". *Rationale:* `FEATURES_DEFAULT_ON` turns `pwa` on for the whole e2e stack. Playwright's `page.route` does not see requests a service worker answers, which would break `insight-bumps.spec.ts` and `weather.spec.ts`, and a cache-first `/assets/*` would carry state between tests.

25. **The production default (all off) is tested end to end.** The `admin-mutations` project gains an "all switches off" test that turns every key off, checks the viewer experience, and restores the previous values in `finally` (§5.3). *Rationale:* the read-only worlds turn everything on (D4), so without this the shipped default would be covered only by unit tests.

26. **Dates shown from timestamps use the club timezone.** "Changed Oct 2, 2026" on the Features page comes from `FeatureSwitchOut.updated_on: date | None`, which the backend computes as `updated_at` converted to `ZoneInfo(settings.timezone)` (America/Los_Angeles). The frontend formats that date with the existing `formatDate` and never converts a timestamp itself. The recap picker's default and the summary card's `to` anchor are the latest scored Sunday, never "today". *Rationale:* a UTC timestamp near midnight would otherwise show the next day, and the rest of the app anchors windows on the latest scored Sunday.

27. **Review points accepted in full.** Every point of the 2026-10-02 spec review was taken; none was rejected. Where the review offered a choice, the choice and its reason are in the decision above that it touches (D2/D3 enabled-keys-only, D7 one `route` block, D8 Sunday PNG one hour, D16 definite-off unregister, §3.3 first-time earners plus holders, §3.4 one `main` widget, §3.5 crossings on every scored or attended Sunday).

---

## 3. Feature design

### 3.0 Launch switches

**Data.** `app_state` rows `feature.<key>` → `{"enabled": true, "updated_at": "2026-10-02T18:04:11Z"}`. No migration.

**Backend.**
- `domain/features.py`: `FEATURES: tuple[Feature, ...]`, `FeatureKey`, `read_switches(session) -> dict[FeatureKey, bool]` (one `SELECT key, value FROM app_state WHERE key LIKE 'feature.%'`, missing rows default from `settings.features_default_on`), and `set_switch(session, key, enabled) -> FeatureOut` (an `INSERT … ON CONFLICT (key) DO UPDATE` upsert whose value is built in SQL with `jsonb_build_object('enabled', :enabled, 'updated_at', now())`, so the timestamp is the database's).
- `api/routes/_features.py` (underscore: not discovered): `feature_gate(key) -> Depends`. It reads the role with `current_role` and the switch with `read_switches`, and raises `HTTPException(status_code=404)` when the switch is off and the role is not `admin`.
- `api/routes/features.py` (viewer): `GET /api/features` → `FeaturesOut{switches: dict[FeatureKey, bool]}`; a viewer gets only the keys that are on, an admin gets every key (D3).
- `api/routes/admin_features.py` (admin): `GET /api/admin/features` → `list[FeatureSwitchOut{key, label, description, enabled, updated_at: datetime | None, updated_on: date | None}]` (`updated_on` in the club timezone, D26); `PUT /api/admin/features/{key}` body `FeatureSwitchIn{enabled: bool}` → `FeatureSwitchOut`, audited.
- `api/etag.py`: `"/api/features"` is added to `NO_ETAG_PREFIXES` and to the no-store set.
- Gated viewer routes in this plan: `GET /api/club/milestones` (`club_milestones`, in `api/routes/club.py`), `GET /api/shooters/{id}/summary` (`summary_card`, in `api/routes/shooters.py`), `GET /api/og/image/sunday/{date}.png` (`link_previews`, for every caller, since crawlers have no role). Admin-only routes (`/api/admin/recap/*`) are already admin-gated, so their switch only drives the badge.

**Frontend.**
- `lib/features.ts`: `useFeatures()` (query key `['/api/features']`, `staleTime: 60_000`, `refetchOnWindowFocus: true`, `enabled` only once a session exists, so it never fires on `/login` or sets off the 401 redirect) and `useFeature(key): { visible: boolean; preview: boolean; on: boolean; settled: boolean }`, where `on = switches[key] === true`, `visible = on || role === 'admin'`, `preview = !on && role === 'admin'`, and `settled` is true only after a successful response. While the query is pending, `visible` is false, so nothing flashes in and then out. Code that must act on "off" (the PWA unregister, D16) checks `settled && !on`.
- `components/ui/AdminPreviewBadge.tsx`: a pill with the text **"Admin preview"** and `title`/`aria-description` "Only admins can see this until it is turned on in Features." It sits next to the feature's card or page title.
- `components/FeatureGate.tsx` (D21).
- Page `features/admin-features/`: route `/admin/features`, `RequireRole role="admin"`, `NO_FILTERS`, nav `{ label: 'Features', path: '/admin/features', icon: ToggleRight, order: 940, adminOnly: true }`.

**UI copy (admin Features page).**
- `h1` "Features". Intro: "Turn a finished feature on for everyone. While a switch is off, only admins see the feature, marked “Admin preview”. Changes reach everyone within a minute. No redeploy needed."
- One row per switch: label, description, the existing `Toggle` (accessible name = label), and "Changed Oct 2, 2026" (from `updated_on`, D26) or "Never changed".
- Labels and descriptions (the `FEATURES` tuple):

| key | label | description |
|---|---|---|
| `link_previews` | Link previews | Links shared in chat apps show the Sunday's date, how many shot and the round type. While off, every link shows the plain club preview. |
| `tour_glossary` | Welcome tour and glossary | A 5-step tour on a first visit to Home, the Glossary page, and "Words used here" links in chart explainers. |
| `weekly_recap` | Weekly recap | Admin tool: paste-ready text and an image of a Sunday for the club email. |
| `pwa` | Add to Home Screen | Lets phones install the app, and shows a small install tip on Home. |
| `club_milestones` | Club milestones | Club totals such as clays thrown and Sundays held, dated at the Sunday each round number was passed. Home card and Club page. |
| `summary_card` | Summary card | A shareable card on every profile for the chosen time window. |

**Edge cases.**
- A `PUT` for an unknown key → 404 `feature_not_found`. A body other than `{enabled: bool}` → 422.
- A corrupt `app_state` value (not an object, or `enabled` not a bool) reads as off and logs one warning per read with the key only.
- Switching off while a viewer is on a gated page: the next `/api/features` refetch (≤ 60 s, or on focus) hides the page and shows `NotFoundView`. Gated queries start answering 404 at once, and the page's existing error state covers the gap.
- Switching off while a viewer is mid-navigation to a gated page: the route renders under `FeatureGate` with the cached switches, so the page mounts; its gated query gets 404 and shows the existing error state until the next refetch swaps in `NotFoundView`. No crash, no partial data.
- Two `PUT`s for the same key at once: last writer wins, two `audit_log` rows.
- An unauthenticated request to a gated route gets 401 from `require_viewer`, not 404 (D2).
- The ETag: a gated route answering 404 is never tagged (the middleware tags 200s only), so a cached 200 can never be revalidated to 304 after a switch-off.
- Page views: `/admin/features` and `/admin/recap` are kind `admin`, and `/glossary` is `other` (no new `PageKind`).

### 3.1 Link previews (`link_previews`)

#### 3.1.1 Data

No tables. Facts come from `frames.load_calendar` (one row per Sunday: `kind`, `label`, `round_type`, `n_shooters`, `head_count`, `results_complete`). The preview count is `n_shooters` when the Sunday has scores, else `head_count`, else omitted.

#### 3.1.2 API (module `api/routes/og.py`, public, D6)

| Method & path | Answer |
|---|---|
| `GET`/`HEAD /api/og/page/` and `GET`/`HEAD /api/og/page/{path:path}` | `text/html; charset=utf-8`, the meta page for `/<path>` (a leading `l/` is stripped for the facts lookup) |
| `GET`/`HEAD /api/og/image/generic.png` | `image/png`, 1200×630, the generic card |
| `GET`/`HEAD /api/og/image/sunday/{date}.png?v=<data_version>` | `image/png`, 1200×630, the Sunday card. 404 when the switch is off or there is no such Sunday. `v` is a cache-buster only and is never read. |

All three are declared with `@router.api_route(..., methods=["GET", "HEAD"])` (D6). A HEAD answer has the same status and headers as the GET, with no body.

Path mapping (`og/facts.py: facts_for_path(session, path, switch_on) -> PreviewFacts`):
- `events/YYYY-MM-DD` for a date in the calendar, with the switch on → `sunday` or `special`.
- Everything else, including `/`, `shooters/<id>`, `yir/...`, unknown paths, an unknown date, or the switch off → `generic`.

Response headers:
- HTML: `Cache-Control: private, no-cache` and `Vary: User-Agent`. Humans and crawlers get different bodies at the same SPA URL, so no shared cache (or a Cloudflare "Cache Everything" rule) may store the meta page. Caddy also adds `Vary: User-Agent` to the SPA `index.html` response for the same reason (§3.1.3).
- PNG: `Cache-Control: public, max-age=86400` for `generic.png`, `public, max-age=3600` for the Sunday image (D8).
- Both: `X-Robots-Tag: noindex, nofollow`. Caddy's `security_headers` apply as for every response. `api/etag.py` adds `/api/og/` to `NO_ETAG_PREFIXES`, and `cache_control_for` returns `None` for it, so the route's own `Cache-Control` stands.

The HTML (no script, no style, no inline handlers, so it is CSP-clean):

```html
<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="robots" content="noindex, nofollow">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Sunday Clays">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{PUBLIC_BASE_URL}/l/{path}">
<meta property="og:image" content="{image_url}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{image_alt}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="{image_url}">
</head><body><p><a href="/{path}">Open Sunday Clays</a></p></body></html>
```

Every interpolated value goes through `html.escape(..., quote=True)`. The special label is admin-entered text of at most 60 characters. `{path}` is the requested path with any leading `l/` removed, so `og:url` is always the `/l/` form (`https://sundayclays.claysmasher.com/l/events/2026-09-27`) whether the crawler came in on `/events/…` or `/l/events/…`. Facebook (and so iMessage and WhatsApp) re-scrapes the canonical `og:url`, and only `/l/*` stays reachable if Access is ever enabled (D7). The page never reads the cookie, so a crawler UA sent with a valid session gets the same bytes as one without.

#### 3.1.3 Caddy

Added to `:80`, **before** `handle /api/*`, as **one `route` block** (D7). Caddy sorts sibling `handle` directives by matcher specificity, so a `handle_path /l/*` written after `handle @crawler` would still run first and send crawlers the 302. Inside `route`, directives run in the order written.

```caddyfile
@crawler {
	method GET HEAD
	header_regexp User-Agent (?i)(facebookexternalhit|Twitterbot|Slackbot|Discordbot|WhatsApp|TelegramBot|LinkedInBot|Applebot|SkypeUriPreview)
	not path /api/* /assets/* /trophies/* /icons/* /sw.js /manifest.webmanifest
}
@share_unsafe path_regexp ^/l/[/\\]
@share path /l/*

route {
	# 1. Crawlers on any SPA path (including /l/…) get the meta page.
	handle @crawler {
		request_body {
			max_size 264KiB
		}
		rewrite * /api/og/page{path}?{query}
		import api
	}
	# 2. "/l//evil.com" or "/l/\evil.com" would become a protocol-relative Location: refuse it.
	handle @share_unsafe {
		redir / 302
	}
	# 3. People on a share link go to the app page, query string kept.
	handle @share {
		uri strip_prefix /l
		redir * {uri} 302
	}
}
```

- After `uri strip_prefix /l`, `{uri}` is the remaining path plus query, so `/l/events/2026-09-27?w=3m` redirects to `/events/2026-09-27?w=3m`. The `@share_unsafe` guard has already sent any path whose remainder starts with `/` or `\` to `/`, so `Location` always starts with exactly one `/` followed by a path segment and can never be protocol-relative. Caddy matches `path_regexp` on the decoded path, so `/l/%2F%2Fevil.com` is caught by the same guard. The tests below pin the exact `Location` for each case.
- The SPA catch-all `handle` gains `header Vary User-Agent`, so a shared cache never serves the SPA to a crawler or the meta page to a person.

iMessage previews fetch as `facebookexternalhit` and `Twitterbot`, and Applebot is listed for Apple's own fetcher. In-app browsers must **not** match, because they are people: `FBAN/FBAV` (Facebook and Messenger in-app), `LinkedInApp`, `Twitter for iPhone`, and Discord's desktop client (`discord/1.0.9…`, lower-case, not `Discordbot`). The regex above matches none of them. The `/api/og/*` image and page paths already pass through `handle /api/*` with its existing 264 KiB body cap.

**Caddy tests (T4).** `deploy/caddy/test_crawler_ua.sh` runs `caddy validate --config Caddyfile` and then, against the e2e stack, a table of real User-Agent strings with the expected outcome: each listed crawler (for example `facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)`, `WhatsApp/2.23.20.0 A`, `Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)`, `Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)`, `TelegramBot (like TwitterBot)`, `LinkedInBot/1.0`, `Twitterbot/1.0`) gets `og:title`; each in-app browser and a desktop Chrome UA gets the SPA. The same table is the source of the `link-previews.spec.ts` UA cases (§5.3).

#### 3.1.4 Copy

| Facts | `title` | `description` | `image_alt` |
|---|---|---|---|
| generic | Sunday Clays · Tri-County Gun Club | Scores, trophies and stats for the Sunday Clays group at Tri-County Gun Club. | Sunday Clays logo |
| sunday | Sunday Clays · Tri-County Gun Club | Sunday, Sep 27, 2026 · 23 shooters · Sporting | Sunday Clays, Sunday Sep 27, 2026 |
| special | Sunday Clays · Tri-County Gun Club | 3-Bird Shoot · 40 shooters | Sunday Clays, 3-Bird Shoot on Sep 20, 2026 |

- Round types read "Sporting" or "Super Sporting".
- "1 shooter" in the singular.
- With no count, the line drops that part: "Sunday, Sep 27, 2026 · Sporting".
- The special line keeps the date in the image, not in the description, exactly as the owner specified ("label · N shooters").

Image layout (1200×630, background `#1A4D2E`):
- logo mark 160 px at (80, 80);
- "Sunday Clays" Roboto Medium 72 px `#FEFBF6` at (80, 290);
- "Tri-County Gun Club" Roboto Regular 40 px `#D4E7DD` at (80, 380);
- for a Sunday, line A "Sunday, Sep 27, 2026" (or the special label) Roboto Medium 52 px `#E8A77A` at (80, 450), and line B "23 shooters · Sporting" (special: "Special shoot · 40 shooters") Roboto Regular 40 px `#FEFBF6` at (80, 520);
- footer "sundayclays.claysmasher.com" 28 px `#D4E7DD`, right-aligned at x = 1120, baseline 590.

Text wider than 1040 px is shrunk in 2 px steps down to 32 px, then truncated with "…".

#### 3.1.5 Edge cases

- **Switch off:** every path gets the generic page, and the Sunday image route 404s. The generic image is always available.
- A **future or attendance-only** Sunday with neither scores nor a head count gets the date and round type only.
- A **HEAD** request gets the same status and headers as GET, with no body (never 405, D6).
- A **human with a spoofed crawler UA** sees the meta page with an "Open Sunday Clays" link, which leads to the normal password gate. With a valid session cookie as well, the page is byte-identical to the cookie-less one: no name, no score, nothing that depends on the session.
- **`/l/` abuse:** `/l//evil.com`, `/l/%2F%2Fevil.com` and `/l/\evil.com` redirect to `/`, never off-site. A query string on a share link is kept on the redirect.
- **Profile links** (`/shooters/3`, `/yir/2026/shooters/3`) are always generic. A preview never confirms that a person exists.
- An **unknown date and an existing date** answer the same status (200), so the endpoint cannot be used to probe dates beyond what the approved Sunday preview already shows.
- **Cost:** a cache miss renders in about 20 ms, and the memo holds the latest 256 renders per process. The edge throttle (`sundayclays-throttle`, 300/min per visitor) bounds abuse, so no rate-limit table is added.
- **Deterministic:** the same `PreviewFacts` always gives the same bytes. A data change bumps `v`, so crawlers that respect cache headers fetch the new image.

#### 3.1.6 Deploy runbook additions (`deploy/README.md`, "Public access" section)

A new operator step, **"Link previews and Cloudflare"**:

1. Today there is no Cloudflare Access. Caddy routes crawlers on every path, so no Cloudflare change is needed. Check it with `curl -s -A 'facebookexternalhit/1.1' https://sundayclays.claysmasher.com/events/<latest Sunday> | grep -E 'og:(description|url)'`, which must print the Sunday line and an `og:url` of `https://sundayclays.claysmasher.com/l/events/<latest Sunday>`. Check `curl -sI https://sundayclays.claysmasher.com/api/og/image/generic.png` for `200`, `content-type: image/png`.
2. **Caching (replaces the old step 4 note).** Step 4's cache bullet is rewritten to: "Leave the default cache behaviour. The API sends `private, no-cache`, except the link-preview images under `/api/og/image/` (`.png`, cached at the edge: generic one day, Sunday images one hour). The preview page sends `private, no-cache` and `Vary: User-Agent`. `/assets/*` is immutable and may be cached. Do **not** add a Cache Everything rule." Add: "Turning `link_previews` off stops new Sunday previews at once, but an image already at the edge can be served for up to an hour, and a preview already posted in a chat stays as it is."
3. **If Cloudflare Access is ever put in front of `sundayclays.claysmasher.com`**, add this bypass **before** enabling the Access app for the host:
   - Zero Trust → Access → Applications → **Add an application** → **Self-hosted**.
   - Name `sundayclays-link-previews`. Session duration: default.
   - Application domain 1: subdomain `sundayclays`, domain `claysmasher.com`, path `l/*`.
   - Application domain 2: subdomain `sundayclays`, domain `claysmasher.com`, path `api/og/*`.
   - Policy: name `bypass-previews`, **Action: Bypass**, **Include: Everyone**. No other rules.
   - Save. Access evaluates the most specific path first, so these two paths stay public while the host-wide app gates everything else.
   - Verify: `curl -s -A 'WhatsApp/2.23' https://sundayclays.claysmasher.com/l/events/<latest Sunday> | grep -E 'og:(title|url)'` prints the title and an `og:url` under `/l/`, `curl -sI -A 'facebookexternalhit/1.1' <that og:url>` returns 200 (not the Access redirect), and `curl -sI https://sundayclays.claysmasher.com/events/<latest Sunday>` returns the Access redirect (302 to `*.cloudflareaccess.com`).
   - Only `/l/…` links preview while Access is on. The app's own share links already use `/l/` (D7).
4. Leave Bot Fight Mode off (it is off today). It challenges unverified preview fetchers such as WhatsApp's.

### 3.2 First-visit tour and glossary (`tour_glossary`)

#### 3.2.1 Tour

**Where:** Home only (`/`), mounted by a `hero` homeWidget `{ id: 'tour', order: -10, slot: 'hero' }` in `features/tour/homeWidget.tsx`. The widget renders no visible card; it only opens the dialog. `WidgetSlot` (`features/home/components/WidgetSlot.tsx`) already renders each widget with no wrapper element, so a Component that returns `null` adds no DOM node and no `gap`/`space-y` spacing. A test pins this: the hero slot's child count and height are unchanged with the tour widget mounted and closed. Home gains `data-tour` attributes and loses nothing:
- `data-tour="sunday"` on `LatestEventCard`'s card;
- `data-tour="you"` on the Personal `aside`;
- `data-tour="insights"` on the insights hero widget's card;
- `data-tour="trophies"` on the side-nav "Trophies" link (desktop) and on the `next-trophy` me widget (both screen sizes). The tour targets the **first visible** element in document order (`querySelectorAll` filtered by a non-zero bounding box), so on desktop with me set it is the side-nav link;
- `data-tour="window"` on `TimeWindowFilter` (content header on desktop, top bar on phone).

**When it opens:**
- the feature is visible;
- `localStorage['sc.tour.v1'] !== 'done'`, or the URL has `?tour=1`;
- the latest-Sunday card has rendered, or 1.5 s have passed.

When it opens from `?tour=1`, the `tour` parameter is removed at once with `history.replaceState` (other parameters kept), so a reload does not reopen it.

It never opens on any other page.

**Steps (copy):**

| # | Target | Title | Body |
|---|---|---|---|
| 1 | `sunday` | The latest Sunday | Every Sunday's results land here once the scores are uploaded. Tap "Full results" for the whole sheet. |
| 2 | `you` | Which one are you? | Pick your name once and Home shows your own numbers, your next trophy and a link to your page. It is saved on this device only. |
| 3 | `insights` | Insights and fist bumps | Short, true things the numbers say about the club and its shooters. Tap the fist to give a bump. Bumps are anonymous. |
| 4 | `trophies` | Trophies | Trophies are earned by showing up and shooting. Your next one, and how close you are, shows on Home once you pick your name. |
| 5 | `window` | Time window | Charts and stats follow this window. 8W is the last 8 weeks. Pick 3M, 6M, 12M, YTD, All, or your own dates. |

**UI.**
- The dialog is `role="dialog"`, `aria-modal="true"`, labelled by the step title, and described by the body.
- It shows "Step 2 of 5", buttons **Back** (hidden on step 1), **Next** (on step 5: **Done**) and **Skip tour**, all ≥ 44 px.
- A spotlight ring (`border-accent`, 3 px, `rounded-card`) is positioned over the target's bounding box, plus a dim overlay. The target is `scrollIntoView({ block: 'center' })`.
- On a phone (≤ 640 px) the dialog docks to the bottom above the tabs; on desktop it sits beside the target.
- An admin preview shows `AdminPreviewBadge` in the dialog header.

**Accessibility.**
- Focus moves to the dialog title on open, and Tab/Shift+Tab cycle within the dialog (focus trap).
- **Esc** closes the dialog and counts as done.
- On close, focus returns to the Home `h1`, which gains `tabIndex={-1}` so it can take focus without entering the Tab order.
- Under `prefers-reduced-motion: reduce`, the scroll is `behavior: 'auto'`, there are no transitions, and the ring does not animate.
- The background is `inert` while the dialog is open.

**Edge cases.**
- A missing or hidden target (for example `trophies` on a phone with no me picked) → that step shows centred with no spotlight.
- Storage unavailable → the tour shows at most once per page load (an in-memory flag).
- A viewport resize or scroll repositions the ring (`ResizeObserver` and `scroll` listener, rAF-throttled).
- The tour and the install tip are never shown together: the tip waits until the tour is done (§3.4).

#### 3.2.2 Glossary

**Route** `/glossary` (`features/glossary/routes.tsx`, `NO_FILTERS`, wrapped in `FeatureGate`), nav `{ label: 'Glossary', path: '/glossary', icon: BookOpen, order: 135, feature: 'tour_glossary' }`.

**Page:**
- `h1` "Glossary", intro "The words Sunday Clays uses, in plain English.";
- a definition list (`dl`) with one `dt id="<term-id>"` per term, alphabetical;
- a **"Take the tour again"** button (→ `/?tour=1`).

A hash link scrolls to the term and gives it a 2 s `bg-elevated` highlight, with no animation under reduced motion.

**Terms** (`features/glossary/terms.ts`; the id is the anchor):

| id | Term | Definition |
|---|---|---|
| `clays-thrown` | Clays thrown and broken | Thrown is 50 for every regular round. Broken is the score. Special shoots are left out of both. |
| `difficulty` | Difficulty | How much harder or easier a Sunday was than usual, in targets. It is worked out from how everyone scored compared with their own normal. |
| `field-adjusted` | Field-adjusted score | Your score minus that Sunday's field median. +4 means 4 targets better than the middle of the field, so easy and hard days compare fairly. |
| `field-median` | Field median | The middle score of all rounds that Sunday: half scored more, half scored less. |
| `first-timer` | First-timer | Someone whose first Sunday on record is that day. Special shoots count. |
| `fist-bump` | Fist bump | A thumbs-up on an insight. It is anonymous: it uses a random ID made by your browser, never your name. |
| `held-sunday` | Sunday with full results | A Sunday that has scores, where either no head count was written down or at least half the people counted have a score. Streaks, Sundays held and milestones count these. |
| `percentile` | Percentile | Where your best round of the day landed in the field, from 0% (lowest) to 100% (highest). Ties share a spot. It is (shooters − your average place) ÷ (shooters − 1). |
| `personal-best` | Personal best (PB) | Your best single round so far. On a Sunday's page, in the recap and on the summary card, a new PB counts once you have at least 5 earlier rounds. |
| `rarity` | Rarity | The share of everyone who has shot a round who holds that trophy. 5% means about 1 in 20 shooters. |
| `round-types` | Sporting and Super Sporting | Every regular round is 50 targets. If any station that day threw an odd number of targets, the round is Super Sporting (some single targets mixed with pairs). Otherwise it is Sporting (all pairs). An admin can correct a Sunday's type. |
| `special-shoot` | Special shoot | A Sunday with its own format, such as the 3-Bird Shoot (60 targets). It counts as a Sunday you came to, for streaks, Sundays shot and attendance trophies, but its scores stay out of averages, personal bests, records and leaderboards. |
| `streak` | Streak | Sundays in a row you came to, counting Sundays with full results. A special shoot adds one if you came, and never breaks a run if you did not. |
| `time-window` | Time window | The 8W / 3M / 6M / 12M / YTD / All / Custom control at the top. Charts and stats on the page follow it. Fullscreen and CSV downloads show everything. |
| `trophy-tiers` | Trophy tiers | Tiered trophies go Bronze, Silver, Gold, Platinum, then Diamond as the number grows. |

**Explainer deep links.**
- `components/charts/types.ts` `Explainer` gains `terms?: readonly GlossaryTermId[]`.
- `ExplainerPanel` renders, after "How it's worked out" and only while `useFeature('tour_glossary').visible`, a line **"Words used here:"** followed by links "Field-adjusted score · Percentile" (to `/glossary#field-adjusted` and so on), each ≥ 44 px tall.
- `GLOSSARY_TRIGGERS: Record<GlossaryTermId, RegExp>` (for example `percentile: /\bpercentile\b/i`, `field-adjusted: /\b(field-)?adjusted\b/i`, `special-shoot: /\bspecial shoot/i`, `streak: /\bstreak/i`, `rarity: /\brarity\b|\brare\b/i`, `round-types: /\bsuper sporting\b|\bround type/i`, `personal-best: /\bpersonal best|\bPB\b/`, `difficulty: /\bdifficult/i`, `held-sunday: /full results/i`).
- The lint test walks every `explainers` export in `src/features/*/explainers.ts` and fails when text matches a trigger whose id is not in `terms`. Plan 19 adds the missing `terms` to the existing explainers in the same task.

### 3.3 Weekly recap (`weekly_recap`, admin only)

#### 3.3.1 API — `api/routes/admin_recap.py`

`admin_recap.py` gets `require_admin` from the `admin_` module prefix (api/routes auto-discovery), like every other `admin_*` module. `GET /api/admin/recap/{date}` → `RecapOut`:

```text
event_date: date
kind: "regular" | "special"
label: str | None                 # special only
target_total: int                 # 50 or the special total
shooters: int                     # n_shooters (people with a score)
head_count: int | None
rounds: int                       # n_rounds
podium: list[PodiumPlaceOut]      # regular only; [] for special
  place: 1 | 2 | 3
  tied: bool
  score: int
  names: list[str]                # display names, alphabetical
pbs: list[RecapPbOut]             # regular only
  display_name: str
  score: int
  previous: int
trophies: list[RecapTrophiesOut]  # awards dated this Sunday, category != "competition"
  display_name: str
  items: list[str]                # "Events Attended — Silver", "Iron Streak — Bronze", "Doubleheader"
club_milestones: list[str]        # "350,000 clays thrown"; [] unless club_milestones is on
first_timers: list[str]           # appearance-based, not left_censored
three_bird_new: int | None        # special whose label is a 3-bird label (THREE_BIRD_LABELS): three_bird_shoot awards dated this Sunday (first-time earners)
three_bird_holders: int | None    # same condition: three_bird_shoot awards dated on or before this Sunday (everyone who holds it now)
top_score: int | None             # special only
link: str                         # f"{PUBLIC_BASE_URL}/l/events/{date}"
```

Rules:
- PBs use `events.event_notables`' rule (`PB_MIN_PRIOR_ROUNDS = 5`, best round of the day above every earlier regular round); the function is reused, not copied.
- First-timers are `shooter_profiles.first_event == date and not left_censored`. `first_event` is already appearance-based (Plan 17 D7).
- The 3-bird fields use `participation.normalize_label(label) in THREE_BIRD_LABELS` (reused, not copied). `three_bird_shoot` is awarded only on a shooter's **first** 3-bird shoot, so `three_bird_new` counts first-time earners and `three_bird_holders` counts all holders to date; at the first 3-bird shoot on record they are equal. A special shoot with any other label (for example "Turkey Shoot") gets `None` for both.
- Unknown date → 404 `event_not_found`. A date without full results (`results_complete` false) → 409 `recap_not_ready`, "This Sunday has no full results yet."

#### 3.3.2 UI — `features/admin-recap/`

- Route `/admin/recap`, `RequireRole role="admin"`, `NO_FILTERS`, nav `{ label: 'Recap', path: '/admin/recap', icon: Mail, order: 935, adminOnly: true, feature: 'weekly_recap' }`. Admins always see the nav item; `AdminPreviewBadge` shows beside the `h1` while the switch is off.
- `h1` "Weekly recap". A Sunday picker (`Select`) lists held Sundays from `GET /api/events`, newest first, labelled "Sep 27, 2026" or "Sep 20, 2026 — 3-Bird Shoot". It defaults to the latest held Sunday in the list (a date from the data, never "today", D26), and the choice is kept in the URL as `?date=`.
- Tabs: **Plain text** | **Markdown**. Each shows a read-only `textarea` (monospace, auto-height) with the formatted recap.
- Buttons: **Copy text** / **Copy Markdown** (whichever tab is open; `navigator.clipboard.writeText`, with a fallback of selecting the textarea and `document.execCommand('copy')`), and **Download image** (D20). A polite live line says "Copied." / "Could not copy. Select the text and copy it by hand." / "Image ready."
- The image card (`RecapImageCard`, 600 px wide, rendered on screen under the text as a preview) shows the same contents in the app's card style. Its filename is `sunday-clays-recap-2026-09-27.png`.

#### 3.3.3 Copy (golden strings; `format.ts`)

Regular, plain text:

```text
Sunday Clays · Sunday, September 27, 2026

Turnout: 24 came out and 27 rounds were shot.

Podium (best round of the day)
Tied 1st: Finnegan, Stanton and Stockton, Ethan — 49
3rd: Devlin, Sid — 47

New personal bests
- Kaplan, Noel: 45 (was 43)

Milestones and trophies
- Abernathy, Preston: Events Attended — Silver
- Club: 350,000 clays thrown

Welcome to our first-timers
- Kim, Pat

See every score: https://sundayclays.claysmasher.com/l/events/2026-09-27
```

- Turnout uses `head_count` when present ("24 came out"), else `shooters` ("23 shooters").
- An empty section is omitted entirely, with its heading.
- Names in a tie are joined with ", " and a final " and ".
- Markdown is the same text with `**Podium**`-style bold headings, `-` lists, and `[See every score](url)` as the last line.

Special, plain text:

```text
Sunday Clays · Sunday, September 20, 2026
3-Bird Shoot (special shoot, 60 targets)

40 shooters came out.
3-Bird Shoot trophy: 12 earned it for the first time today. 58 shooters hold it now.
Top score: 55 of 60.

Welcome to our first-timers
- Kim, Pat

See every score: https://sundayclays.claysmasher.com/l/events/2026-09-20
```

- The trophy line is omitted when `three_bird_holders` is `None` or 0. When `three_bird_new` is 0 (everyone had it already), the line is "3-Bird Shoot trophy: 58 shooters hold it now." When `three_bird_new == three_bird_holders` (the first one on record), it is "3-Bird Shoot trophy: 40 shooters earned it today." "1 shooter" in the singular.
- The goldens use the fixture label `"3-Bird Shoot"` (`conftest.py` `SPECIAL_LABEL`). A second golden uses a special shoot labelled "Turkey Shoot" (not a 3-bird label): the trophy line is absent and the rest is unchanged.
- The top score never carries a name (a special shoot is never ranked, Plan 17 D18).

**Edge cases.**
- A Sunday with one shooter: the podium is "1st: Name — 44" only.
- 5 shooters tied for 3rd: all 5 are listed on the "Tied 3rd" line.
- A Sunday before any PB is possible (fewer than 5 earlier rounds for everyone): the section is omitted.
- Trophies for a deceased shooter are listed as for anyone (positive).
- A label containing Markdown characters is escaped in the Markdown variant (`\*`, `\_`, `\[`, `\]`).

### 3.4 PWA: Add to Home Screen (`pwa`)

**Files.**
- `frontend/public/manifest.webmanifest`:

```json
{
  "id": "/",
  "name": "Sunday Clays",
  "short_name": "Sunday Clays",
  "description": "Scores, trophies and stats for the Sunday Clays group.",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "background_color": "#1A4D2E",
  "theme_color": "#1A4D2E",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" },
    { "src": "/icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}
```

- `index.html` gains static `<link rel="icon" href="/icons/favicon-32.png">` and `<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">`. These are harmless while the switch is off. The manifest link is runtime-only (D16).
- `/sw.js`, emitted by `pwaShell()`:
  - The cache name is `sc-shell-<first 12 hex of sha256(index.html)>`.
  - Precache (small, about the size of the first page load): `/`, `/index.html`, `/manifest.webmanifest`, `icon-192.png`, and from the Vite build manifest only the entry chunk (`isEntry`), its static imports and its CSS. Lazy route chunks (`isDynamicEntry`) are **not** precached; they are cached at run time the first time they are fetched.
  - `fetch`: ignore non-GET and cross-origin requests, and any path starting with `/api/` or `/l/`, by returning without `respondWith`, so the browser handles them.
  - Navigations: network first, falling back to the cached `/index.html` when offline.
  - `/assets/*` and `/icons/*`: cache first, and a network answer is put into the current cache (run-time caching of lazy chunks).
  - `install` calls `skipWaiting()`; `activate` calls `clients.claim()` and deletes `sc-shell-*` caches **except the current one and the newest other one**. Each cache holds a synthetic entry `/__sc-created` whose body is the install time (`Date.now()`), written in `install`; `activate` reads it from every other `sc-shell-*` cache, keeps the newest, and deletes the rest. A tab still running the old shell can therefore keep loading old-hash lazy chunks from the previous cache.
  - **Chunk-load recovery:** the app has none today, so Plan 19 adds `lib/chunkReload.ts`, imported by `main.tsx`. It listens for Vite's `vite:preloadError` event and reloads the page once (guarded by `sessionStorage['sc.chunk.reloaded']`, cleared after a successful load), so an old-hash chunk that is in neither the cache nor the server loads the new shell instead of showing an error. This also covers deploys with the PWA switch off.

**Caddy** (before the catch-all `handle`):

```caddyfile
handle /sw.js {
	root * /srv
	header Cache-Control "no-cache"
	header Service-Worker-Allowed "/"
	file_server
}
handle /manifest.webmanifest {
	root * /srv
	header Content-Type "application/manifest+json"
	header Cache-Control "no-cache"
	file_server
}
handle /icons/* {
	root * /srv
	header Cache-Control "public, max-age=86400"
	file_server
}
```

The CSP gains `manifest-src 'self'; worker-src 'self'` (explicit, though both already fall back to `'self'`).

**Launch behaviour.**
- When `matchMedia('(display-mode: standalone)').matches`, the path is `/`, `sessionStorage['sc.pwa.launched']` is unset and `getMe()` is set, the app replaces the URL with `/shooters/{me}`, then sets the flag.
- Otherwise it stays on Home. This happens in an effect of the one `features/pwa` home widget (below), which always mounts and runs the redirect effect before deciding whether to render the tip; `router.tsx` is not edited, and the home widget registry still takes one `homeWidget` per feature (no registry change).

**Install tip and launch redirect** (`features/pwa/homeWidget.tsx`, `{ id: 'install', order: 90, slot: 'main' }`). The Component runs the launch redirect effect, then renders the tip or `null`. The tip shows only when all of these hold:
- touch device (`useIsTouch`);
- not standalone;
- `localStorage['sc.install.dismissed'] !== '1'`;
- the tour is done or not visible;
- either a `beforeinstallprompt` event was captured (by `lib/installPrompt.ts`, imported by `AppShell` so the listener is attached early), or the browser is iOS Safari (`/iP(hone|ad|od)/` and `Safari`, and not `CriOS|FxiOS`).

Copy:
- Card title "Add Sunday Clays to your home screen".
- Android body "Opens like an app, straight to Home or to your own page." Buttons **Install** (calls `prompt()`) and **Not now**.
- iOS body "Tap the Share button, then “Add to Home Screen”." Button **Got it**.
- Not now, Got it, and a completed install all set the dismissed key.
- Admin preview shows the badge.

**Edge cases.**
- Switch turned off: on the next load where `useFeature('pwa')` is `settled && !on` for a viewer, the app unregisters every SW registration, deletes `sc-shell-*` caches and removes the manifest link. A pending, failed or 401 `/api/features` query, and the `/login` page, never unregister (D16).
- A deploy while a tab is open on the old shell: the new SW activates, the old cache is kept as the previous one, so the old tab's lazy routes still load; if a chunk is missing from both, `lib/chunkReload.ts` reloads once onto the new shell.
- An installed app with the switch off still opens; it is just a bookmark.
- The login page works offline only to the extent that the shell loads; `/api` calls fail into the existing error states.
- A logout or a 401 redirect is unaffected, because the SW never touches `/api`.

### 3.5 Club milestones (`club_milestones`)

#### 3.5.1 Data and rules (`analytics/club_milestones.py`)

| metric | value at Sunday d | thresholds |
|---|---|---|
| `clays_thrown` | 50 × regular rounds with `event_date ≤ d` | 10,000 · 25,000 · 50,000 · 100,000 · 150,000 · 200,000 · 250,000 · 300,000 · 350,000 · 400,000 · 450,000 · 500,000 · 600,000 · 700,000 · 800,000 · 900,000 · 1,000,000 |
| `sundays_held` | held Sundays (`results_complete`), regular **and** special, `≤ d` | 25 · 50 · 100 · 150 · 200 · 250 · 300 · 350 · 400 · 450 · 500 |
| `shooters` | distinct shooters in `load_appearances` (special included) with `event_date ≤ d` | 25 · 50 · 100 · 150 · 200 · 250 · 300 · 400 · 500 |
| `rounds` | regular rounds with `event_date ≤ d` | 100 · 500 · 1,000 · 2,500 · 5,000 · 7,500 · 10,000 · 12,500 · 15,000 · 20,000 |

- **Evaluation Sundays:** every Sunday in the calendar that has at least one regular round **or** at least one appearance (`load_rounds` includes Sundays whose `results_complete` is false, so a partial-results Sunday still adds clays and rounds). All four metrics are evaluated on every evaluation Sunday; `sundays_held` simply does not grow on a Sunday that is not held.
- **Crossing date:** the first evaluation Sunday d with value(d) ≥ threshold. A threshold passed on a partial-results Sunday is dated at that Sunday, not at the next held one, so "dated at the Sunday it was crossed" always holds.
- **`as_of` (no leak):** only Sundays ≤ `as_of` are read, so `milestones(as_of=d)` equals `milestones(all)` filtered to crossings ≤ d. `next` progress is the value at the last evaluation Sunday ≤ `as_of`. `as_of` defaults to the latest scored Sunday (`_filters.LAST_SCORE_DATE_SQL`), as every other endpoint does.
- A threshold already passed on the first Sunday on record is dated at that Sunday and flagged `first_on_record: true`.
- Special shoots count only as appearances: they add to `sundays_held` and `shooters`, never to `clays_thrown` or `rounds`.

#### 3.5.2 API

`GET /api/club/milestones?as_of=YYYY-MM-DD` (module `api/routes/club.py`, viewer, `feature_gate("club_milestones")`; `as_of` defaults to the latest scored Sunday, `LAST_SCORE_DATE_SQL`) → `ClubMilestonesOut`:

```text
as_of: date
milestones: list[{metric, threshold, event_date, label, first_on_record}]   # newest first
latest: {metric, threshold, event_date, label, first_on_record} | None
next: list[{metric, threshold, current, remaining, label}]                 # one per metric, None-free; omitted when past the table
series: list[{event_date, clays_thrown, sundays_held, shooters, rounds}]   # one row per evaluation Sunday ≤ as_of
```

`latest` is the newest crossing. Ties on one Sunday are ordered `sundays_held`, `clays_thrown`, `shooters`, `rounds`.

#### 3.5.3 UI and copy

- **Labels:** "350,000 clays thrown", "300 Sundays held", "250 different shooters", "10,000 rounds shot".
- **Home card** (`features/club/homeWidget.tsx`, `{ id: 'club-milestone', order: 20, slot: 'main' }`): title **"Club milestone"**, big line `latest.label`, then "Passed on Sunday, Sep 13, 2026", then "Next up: 400,000 clays thrown, 41,250 to go" (the `next` entry with the smallest `remaining / threshold`), then a link **"All club milestones"** → `/club#milestones`. Explainer `club-milestone` (scope `all-time`): "What this shows: the club's most recent round number, such as total clays thrown or Sundays held." / "How it's worked out: we add up every Sunday on record since Jan 5, 2020, in date order, and note the Sunday each total first reached a round number. Special shoots count as a Sunday held and add their shooters, but not their clays or rounds." `terms: ['held-sunday', 'special-shoot', 'clays-thrown']`. The card is hidden when `latest` is `None`. The widget returns `null` (and does not query) unless `useFeature('club_milestones').visible`; in admin preview it shows `AdminPreviewBadge` beside the title.
- **Club page:** a new first section **"Milestones"** (`id="milestones"`) with two cards. The whole section, heading included, is wrapped in `FeatureGate`-style gating via `useFeature('club_milestones')`: a viewer with the switch off sees no heading, no cards and no gap; an admin sees it with `AdminPreviewBadge` beside the section heading. Its query runs only while visible, so a viewer never triggers the 404.
  - **"Club milestones"**: a list grouped by metric, each line "300 Sundays held — Sep 13, 2026" linking to `/events/<date>`, newest first, with "On the first Sunday on record" for flagged rows. Explainer scope `all-time`.
  - **"Club totals over time"**: a `ChartFrame`, line chart of the cumulative value of one metric chosen by chips (Clays thrown · Sundays held · Shooters · Rounds; URL key `mm`). Each crossing is a `markPoint` labelled with its threshold. Table columns: Sunday, Clays thrown, Sundays held, Shooters, Rounds. CSV `club-totals.csv`, `urlKey="ctot"`. The inline view follows the header window; fullscreen and CSV show every Sunday. Explainer (scope `windowed`): what = "How the club's running totals have grown, Sunday by Sunday, with each round number marked."; read = ["A dot marks the Sunday a round number was passed.", "A flat stretch means no Sundays were held."]; computed = ["Clays thrown: 50 for every regular round. Rounds: regular rounds only.", "Sundays held and Shooters include special shoots.", "Totals start at the first Sunday on record, Jan 5, 2020."].
- Club page milestones ignore the round-type filter. The chart honours the window, as the other Club charts do.

**Edge cases.**
- No evaluation Sunday ≤ `as_of`: `milestones` is empty, `latest` is `None` and `series` is empty. The Club card says "No milestones yet."
- Past the last threshold of a metric: no `next` entry for it.
- A rollback that removes Sundays can "un-cross" a milestone. It is computed on read, so it simply disappears.

### 3.6 Summary card (`summary_card`)

#### 3.6.1 API

`GET /api/shooters/{id}/summary?from=YYYY-MM-DD&to=YYYY-MM-DD` (module `api/routes/shooters.py`, viewer, `feature_gate("summary_card")`, path parameter typed `ShooterId`). `to` is required; `from` is optional and an absent `from` means an open start (the "All" window, whose `windowRange('all')` gives `from: null`), matching `in_window` and `check_window`. `from > to` → 400 `invalid_range` (`check_window`). An unknown shooter → 404 via the existing `NotFoundError("shooter_not_found")`. Cached by `data_version`. The response is `ShooterSummaryCardOut`:

```text
shooter_id, display_name, from, to
sundays: int              # appearances in [from, to], special included
special_sundays: int
rounds: int               # regular rounds in window
average: float | None     # mean regular score, 1 dp; None when rounds == 0
best: {score, event_date} | None
pbs_set: int              # regular Sundays in window where the day's best round beat every earlier regular round, with ≥ 5 earlier rounds
trophies: int             # achievements_awarded rows with event_date in window, category != "competition" (D14)
trophy_names: list[str]   # up to 3, newest first: "Iron Streak — Bronze"
longest_streak: int       # streaks() over appearances and calendar both cut to [from, to]
```

- The round-type filter does not apply (D18).
- The streak counts only Sundays inside the window. A run that started before `from` counts from the first Sunday in the window.

#### 3.6.2 UI and copy

- A `profileSection` in `features/summary/profileSection.tsx`: `{ id: 'summary', title: 'Summary card', order: 90, bare: true }`, just above Share (95). Because `ProfileSections` wraps non-bare sections in a titled card, the section is declared `bare: true` and the Component renders its own `Card` titled "Summary card", or `null` (no title, no gap) unless `useFeature('summary_card').visible`. It shows `AdminPreviewBadge` beside its title in preview.
- The window is `useTimeWindow().range` (any preset or custom; for "All", `from` is `null` and is left out of the query). `to` is the window's anchor, the latest scored Sunday, never "today" (D26). The query waits for `ready`.
- The card (`SummaryCard`, max 480 px, the element that gets rendered):

```text
Sunday Clays · Tri-County Gun Club
Hadley, Ike
Last 3 months · Jul 6 – Sep 27

Sundays shot        11   (1 special shoot)
Rounds · Average    12 · 41.3
Best round          46 · Sep 13
Personal bests      1
Trophies earned     3   Iron Streak — Bronze, Events Attended — Gold, …
Longest streak      6 Sundays in a row
All round types · sundayclays.claysmasher.com
```

- The window line: for a preset, `windowLabel(w)` plus " · " plus `rangeText(range)` from `lib/windowText.ts` ("Last 3 months · Jul 6 – Sep 27"; for All, "All time · through Sep 27, 2026"). For a custom window, `windowLabel(w)` alone, since it already is the dates ("Jan 4 – Mar 29, 2026").
- Lines hidden per D19: rounds/average/best when `rounds == 0`; personal bests when 0; trophies when 0; streak when < 2; "(1 special shoot)" when `special_sundays == 0`. "special shoots" is plural above 1.
- **Buttons:** **Share image** (the existing `ShareCard`, compact = false) and **Download image** (`downloadElementAsImage`). The filename is `sunday-clays-<slugify(name)>-<from>-to-<to>.png`.
- **Empty window** (`sundays == 0`): the card body reads "No Sundays shot in this window." with the existing `WidenWindowButtons` (12M, All), and both buttons are hidden.
- The explainer (`summary-card`, scope `windowed`): what = "A shareable snapshot of one shooter's Sundays in the chosen time window."; computed = ["Sundays shot counts every Sunday you came to, special shoots included.", "Rounds, average, best round and personal bests use regular rounds only, all round types.", "A personal best counts once there are at least 5 earlier rounds.", "Longest streak counts only Sundays inside the window."]; `terms: ['special-shoot', 'personal-best', 'streak']`.

**Edge cases.**
- A special-only shooter: "Sundays shot 1 (1 special shoot)" and nothing else, with no NaN.
- A window before the shooter's first Sunday: the empty state.
- Competition trophies (First Win, Podium, Station Top Gun, Hardest-Station Clean) are not counted or named on the card, as in the recap (D14): a named card is no place for comparison with others.
- A deceased shooter: the card works unchanged (no marker on the image; the profile already shows the memorial).
- A custom window across years is fine.
- A window of one Sunday: a streak of 1 is hidden.

---

## 4. Privacy

- **No IP addresses are stored** by anything in this plan. No new table has an address column. `audit_log.ip` for `feature_switch` is the existing admin-only exception (`admin_actor`). No new rate-limit table is added; if one is ever needed for `/api/og/*`, it must key on `ip_fingerprint` (as `auth/deps.py` does).
- **No access log.** uvicorn keeps `--no-access-log`, and the Caddyfile still has no `log` directive. The `og` routes log nothing per request: not the User-Agent, not the path. A corrupt switch logs the key only.
- **What is public without a password:** the generic preview, and for `/events/<date>` (switch on) the date, the shooter count, the round type and a special label. That is exactly what the owner approved. There are no names, no scores, no profile facts, and profile links are generic. The test in §5.2 enforces it.
- **The service worker never caches `/api` or `/l/`.** Only the app shell (HTML, JS, CSS, icons) is on the device, and no personal data is cached by Plan 19.
- **Images are client-side.** The summary card and the recap PNG are rendered in the browser through `lib/share` and never uploaded.
- **Browser storage keys** (this device only): `sc.tour.v1`, `sc.install.dismissed` (localStorage), and `sc.pwa.launched` (sessionStorage).
- **About page, "Your privacy" card**, gains one sentence: "Links shared in chat apps show only the club name, and for a Sunday its date, how many shot and the round type. Never names or scores." The pronoun and banned-word lints run on it.

## 5. Testing strategy

Strict TDD with RED-then-GREEN evidence per step (memory: TDD evidence required). The coverage floor stays at 90% lines and branches, backend and frontend separately. Golden counts never change: the shared fixtures gain nothing. Tests use only fixture pseudonyms.

### 5.1 Unit

**Backend (pytest)**
- `domain/features.py`:
  - missing row → off;
  - `FEATURES_DEFAULT_ON` → on;
  - a stored `false` beats the default;
  - a corrupt value (a string, `{"enabled": "yes"}`, `null`) → off, plus exactly one warning per `read_switches` call whose message contains the key and does not contain the stored value (`caplog`);
  - an unknown key → `feature_not_found`;
  - `updated_on` is the club-timezone date: an `updated_at` of `2026-10-03T05:30:00Z` gives `2026-10-02` (America/Los_Angeles).
- `feature_gate`: viewer + off → 404 whose body equals an unknown-route 404's; admin + off → 200; viewer + on → 200; no session → 401.
- `GET /api/features`: a viewer gets only the enabled keys; an admin gets all six.
- Language (backend): `tests/unit/domain/test_features_copy.py` checks every `FEATURES` label and description against the banned words (he/she/his/her/him/hers/himself/herself and "class", whole-word, case-insensitive), reusing the word list from `tests/unit/analytics/insights/test_lints.py`.
- `og` routes: every route answers HEAD with 200 and the same headers as GET and an empty body; the module pin test asserts methods ⊆ {GET, HEAD} and the `/api/og/` prefix.
- `og/facts.py`:
  - every path shape (`events/<date>`, `l/events/<date>`, `shooters/3`, `/`, unknown, malformed date, a future date with no counts, special);
  - switch off → generic for every path.
- `og/html.py`:
  - golden HTML for generic, sunday and special (special label `"3-Bird Shoot"`);
  - `og:url` is the `/l/` form for both `events/<d>` and `l/events/<d>`;
  - headers: HTML `Cache-Control: private, no-cache` and `Vary: User-Agent`; Sunday PNG `public, max-age=3600`; generic PNG `public, max-age=86400`;
  - escaping of a label containing `<"&>`;
  - no `<script` and no `style=`.
- `og/render.py`:
  - the same facts give identical bytes twice; the PNG is 1200×630 with no `tEXt`/`iTXt` chunks;
  - the text-fit shrink and ellipsis on a 60-character label;
  - the colour of a background pixel.
- `club_milestones.py`:
  - crossing dates on a hand-built world;
  - a crossing that happens on a Sunday with scores but `results_complete` false is dated at that Sunday, not the next held one;
  - `as_of` omitted defaults to the latest scored Sunday;
  - special rows add to `sundays_held` and `shooters` only;
  - `first_on_record`;
  - the latest tie order;
  - `next` past the end of the table;
  - **no-leak:** for every held Sunday d in `fx_engine`, `milestones(as_of=d) == [m for m in milestones(None) if m.event_date <= d]`, and `next` never uses data after d.
- Summary:
  - each field on a hand-built world: PB count with fewer than 5 prior rounds, a streak cut at `from`, a special-only shooter, an empty window, `from` omitted (open start);
  - competition trophies are not counted or named;
  - mutation-catching asserts (≥ vs > on the PB rule, the window edges inclusive).
- Recap:
  - podium ties (1,1,3; 1,2,2; five tied for 3rd);
  - competition trophies excluded;
  - first-timers from `first_event`;
  - special variant fields: `three_bird_new` (first-time earners) and `three_bird_holders` (all holders to date) at a first and a second 3-bird shoot; a special labelled "Turkey Shoot" gives `None` for both;
  - 409 when not held;
  - milestones only when the switch is on.
- `etag.py`: `/api/features` and `/api/og/*` are untagged; `cache_control_for('/api/og/…')` is `None`.

**Frontend (Vitest + Testing Library + MSW)**
- `useFeature`: the visible/preview matrix (viewer/admin × on/off), pending → not visible and not settled, a missing key → off, and the query is not enabled without a session (no request on `/login`).
- `FeatureGate`: a viewer with the switch off sees `NotFoundView`.
- `AdminPreviewBadge` renders only in preview.
- Nav: items whose `feature` is not visible are hidden.
- Tour:
  - opens once and is stored as done on Done, Skip and Esc;
  - `?tour=1` reopens it and is removed from the URL (other parameters kept);
  - the `trophies` step targets the first visible `data-tour="trophies"` element;
  - the Home `h1` has `tabIndex=-1` and receives focus on close;
  - the closed tour widget adds no node to the hero slot;
  - focus trap (Tab from the last control goes to the first), Esc, focus returned to the `h1`;
  - a missing target centres the step;
  - reduced motion leaves no `transition` class and uses `scrollIntoView` behaviour `auto`;
  - storage throwing gives at most once per load.
- Glossary:
  - every term id is unique and a valid anchor;
  - the hash scrolls and highlights;
  - the **trigger lint** over every explainer export;
  - "Words used here" hidden when the feature is not visible.
- Recap `format.ts`: golden strings for regular, special (`"3-Bird Shoot"`, first and later 3-bird shoot wording), a non-3-bird special ("Turkey Shoot", no trophy line), empty sections, tie wording, and Markdown escaping.
- PWA:
  - the manifest link is injected only when visible;
  - SW registration, and unregistration only on `settled && !on`: a pending query, a 401, a network error and the `/login` page each leave `navigator.serviceWorker.getRegistrations` untouched (mocked) and call no `caches.delete`;
  - `pwaShell()` (Vitest on the plugin): the emitted precache list holds the entry chunk, its static imports and CSS, and no `isDynamicEntry` chunk; the `activate` handler keeps the current and newest previous `sc-shell-*` cache;
  - `lib/chunkReload.ts`: a `vite:preloadError` reloads once and not twice;
  - the standalone launch redirect when me is set (once per session);
  - install tip conditions (Android event, iOS UA, dismissed, tour open, desktop).
- Summary card: the zero-hiding matrix, the empty window, the window line ("Last 3 months · Jul 6 – Sep 27", "All time · through Sep 27, 2026", custom = dates only, never repeated), the "All" window sends no `from`, the filename, and a viewer with the switch off gets no "Summary card" heading (the section is `bare`).
- `lib/share`: `downloadElementAsImage` never calls `navigator.share`; the existing share tests pass unchanged.
- Language tests. There is no central lint today (the checks live in each feature's `explainers.test.ts`), so Plan 19 adds `frontend/src/test/language.ts` exporting `BANNED_WORDS = /\b(he|she|his|her|him|hers|himself|herself|class(es)?)\b/i` and these new tests, each asserting no match over every string in the file's exports:
  - `features/glossary/terms.test.ts` (`terms.ts`),
  - `features/tour/steps.test.ts` (`steps.ts`),
  - `features/pwa/copy.test.ts` (`copy.ts`),
  - `features/admin-recap/format.test.ts` (the formatted output of every golden),
  - `features/summary/explainers.test.ts` and `features/club/explainers.test.ts` (existing file, new `club-milestone` and `club-totals` entries),
  - `features/admin-features/copy.test.ts` (the rendered labels and descriptions from the MSW `/api/admin/features` fixture),
  - `features/about/privacy.test.ts` (the new About sentence).
  The backend `FEATURES` table is covered by `test_features_copy.py` above. Existing per-feature tests are not changed.

### 5.2 Integration (real Postgres; `fx_engine`/`fx_client`/`fx_viewer_client` and `fx_special_engine`/`fx_special_client`/`fx_special_viewer_client` worlds)

- The `og` routes need no cookie. Every route in the `og` module is GET/HEAD under `/api/og/`, and `HEAD /api/og/image/generic.png` is 200 `image/png` with no body. A request with a valid viewer cookie to `/api/og/page/events/<d>` gets byte-identical HTML to the cookie-less one. Every other module still needs a viewer (the role-dependency test is extended).
- **The name scan:** with the switch on, render `/api/og/page/events/<d>` for every Sunday in `fx_engine` and `fx_special_engine`, plus `/api/og/page/shooters/<id>` for every shooter. Assert that no `display_name`, no last name and no first name of any fixture shooter appears, and that no score appears (a regex for any integer 0–60 next to "score" or "of").
- `GET /api/og/image/sunday/<d>.png` is 404 with the switch off and 200 `image/png` with it on. The bytes are identical across two calls and across a `data_version` bump with unchanged facts. The Sunday image sends `public, max-age=3600`.
- Switches: a `PUT` writes an `audit_log` row (`feature_switch`, `{key, enabled}`); `GET /api/features` has `Cache-Control: no-store` and no ETag; the flip is visible on the very next request (no process cache).
- Switch concurrency: two sessions `PUT` the same key (`true` then `false`) on two threads behind a `threading.Barrier`; the stored value is whichever committed last, there are exactly two `feature_switch` audit rows, and `updated_at` equals the database `now()` of the later transaction (not the app clock).
- `GET /api/club/milestones` in `fx_special_client`: the special Sunday adds to `sundays_held` and `shooters` but not to `clays_thrown`. Against `fx_engine` it answers exactly as it does without the special Sunday.
- `GET /api/shooters/{id}/summary`: `fx_special_client` `Kim, Pat` (special-only) and `Hadley, Ike` (extended streak) cases. 422 when `to` is missing; `from` omitted is an open start; 400 `invalid_range`; 404 `shooter_not_found`.
- `GET /api/admin/recap/{date}`: the fixture's latest Sunday 2026-09-27 matches `GET /api/events/2026-09-27` for podium names and PBs, and the `fx_special_client` 2026-09-20 special variant (label "3-Bird Shoot") has `three_bird_new` equal to the `three_bird_shoot` awards dated that day and `three_bird_holders` equal to those dated on or before it. A viewer gets 403.

### 5.3 End to end (Playwright, `desktop` 1440×900 and `mobile` 390×844 projects)

Every spec uses the shared `test` from `e2e/fixtures.ts` (CSP violations and page errors fail the test).

`fixtures.ts` gains two auto option fixtures, `tourSeen` (default `true`) and `installTipSeen` (default `true`). Through `page.addInitScript` they set `sc.tour.v1 = 'done'` and `sc.install.dismissed = '1'`, so existing specs never meet the tour or the tip. The tour and PWA specs use `test.use({ tourSeen: false })` and `test.use({ installTipSeen: false })`. The test stack runs with `FEATURES_DEFAULT_ON` = all six keys (D4). `playwright.config.ts` sets `serviceWorkers: 'block'` for every project, and only `pwa.spec.ts` uses `test.use({ serviceWorkers: 'allow' })` (D24, C10 amendment), so `page.route` in `insight-bumps.spec.ts` and `weather.spec.ts` keeps working and no SW cache carries state between tests.

- `link-previews.spec.ts` (API-level, through Caddy):
  - with `User-Agent: facebookexternalhit/1.1`, `/events/2026-09-27` has `og:description` "Sunday, Sep 27, 2026 · <n> shooters · Sporting", where n comes from `GET /api/events/2026-09-27` (viewer request);
  - the `og:image` URL answers `image/png`, and its size decodes to 1200×630;
  - `/shooters/3` and `/` are generic;
  - **crawler on the share prefix:** with `User-Agent: facebookexternalhit/1.1`, `/l/events/2026-09-27` answers 200 HTML with the Sunday `og:description` and `og:url` `…/l/events/2026-09-27` (not a 302; this pins the `route` ordering, D7). The same with `WhatsApp/2.23.20.0 A`;
  - `HEAD /l/events/2026-09-27` with the crawler UA → 200 `text/html`; `HEAD /api/og/image/generic.png` → 200 `image/png`;
  - `/l/events/2026-09-27` with a browser UA → 302, `Location: /events/2026-09-27`; `/l/events/2026-09-27?w=3m` → `Location: /events/2026-09-27?w=3m`;
  - open-redirect guard: `/l//evil.com`, `/l/%2F%2Fevil.com` and `/l/%5Cevil.com` each → 302 with `Location: /`;
  - the meta page has `Cache-Control: private, no-cache` and `Vary: User-Agent`;
  - in-app browsers are people: `FBAN/FBIOS;FBAV/400.0`, `LinkedInApp/9.0`, `Twitter for iPhone`, `Mozilla/5.0 … discord/1.0.9 … Electron` each get the SPA `index.html` (no `og:title`) on `/events/2026-09-27`;
  - spoofed crawler UA **with** the viewer storage state: the HTML equals the cookie-less response byte for byte and holds no fixture name or score;
  - the CSP header is present on the meta page;
  - no fixture winner name (`Finnegan`, `Stockton`) appears in the HTML.
- `tour.spec.ts`:
  - the first visit to `/` opens "The latest Sunday", "Step 1 of 5";
  - Next ×4 then Done;
  - a reload does not show it again;
  - `?tour=1` reopens it;
  - Esc closes it;
  - keyboard-only: Tab stays inside the dialog;
  - `page.emulateMedia({ reducedMotion: 'reduce' })` run;
  - at 390 the dialog is docked bottom with no side scroll (`expectNoSideScroll`), and every control is ≥ 44 px.
- `glossary.spec.ts`:
  - `/glossary#percentile` scrolls to the term;
  - an explainer on `/shooters/3` shows "Words used here" with a working link;
  - nav has "Glossary".
- `club-milestones.spec.ts`:
  - the Home card shows "Club milestone", and its link lands on `/club#milestones`;
  - the "Club totals over time" chart has Table, CSV (download event, header row), fullscreen and "About this chart";
  - the window changes the inline zoom only.
- `summary-card.spec.ts`:
  - `/shooters/3?w=3m` shows "Summary card" with "Last 3 months";
  - `/shooters/3?w=all` shows the card with "All time · through …" and no request error (the request has no `from`);
  - switching to a custom window updates the dates;
  - "Download image" triggers a download named `sunday-clays-…png`;
  - an empty window shows "No Sundays shot in this window." with 12M/All buttons.
- `pwa.spec.ts` (`serviceWorkers: 'allow'`):
  - `/manifest.webmanifest` has `content-type: application/manifest+json`;
  - `/sw.js` has `Cache-Control: no-cache` and `Service-Worker-Allowed: /`;
  - after load, `navigator.serviceWorker.ready` resolves;
  - after visiting `/events` and `/shooters/3`, `caches.keys()` → `sc-shell-*` holds no URL containing `/api/`;
  - with `installTipSeen: false` at 390, a dispatched synthetic `beforeinstallprompt` shows "Add Sunday Clays to your home screen", and "Not now" hides it for good;
  - the precache (`caches.open('sc-shell-…').keys()`) holds the entry JS and CSS but no lazy route chunk until that route is visited;
  - **shell upgrade:** with the v1 shell open on `/`, the test serves a v2 `sw.js` and v2 `index.html` (a second build's files routed with `context.route` on `/sw.js` and `/`, the old `/assets/*` names made to 404) and calls `registration.update()`; the open v1 tab then navigates to `/club` (a lazy route) and the page either renders "Club" from the kept previous cache or reloads once onto v2 and renders it, with no error page;
  - logging out and loading `/login` leaves `navigator.serviceWorker.getRegistrations()` length 1.
- `recap.spec.ts` (admin context via `ADMIN_STATE`, read-only):
  - `/admin/recap` defaults to Sep 27, 2026;
  - the Plain text tab starts "Sunday Clays · Sunday, September 27, 2026" and contains "Podium";
  - Copy text puts it on the clipboard (`context.grantPermissions(['clipboard-read','clipboard-write'])`);
  - Download image downloads `sunday-clays-recap-2026-09-27.png`.
- `features.admin-mutations.spec.ts` (the existing `admin-mutations` project, run at both sizes with `page.setViewportSize`):
  - turn `summary_card` off; a viewer context sees no "Summary card" section, and `GET /api/shooters/3/summary?from=…&to=…` returns 404 with `{"detail":"Not Found"}`;
  - the admin context sees the card with "Admin preview";
  - turn `link_previews` off; the crawler request gets the generic description;
  - turn `tour_glossary` off; a viewer's `/glossary` shows "Page not found" and the nav has no Glossary;
  - everything is restored to on in `finally`.
  - **All switches off (the production default, D25):** turn all six keys off, then with a viewer context at both sizes:
    - the nav (side nav at 1440, More sheet at 390) has no "Glossary";
    - Home has no "Club milestone" card, no tour dialog (with `tourSeen: false`), and no install tip (with `installTipSeen: false` and a synthetic `beforeinstallprompt`), while every existing Home card is still present;
    - `/shooters/3` has no "Summary card" heading anywhere (no title leak), and the Club page has no "Milestones" heading;
    - `/glossary` shows "Page not found";
    - `GET /api/features` (viewer) answers `{"switches": {}}`;
    - a crawler request (`facebookexternalhit/1.1`) to `/events/2026-09-27` gets the generic description, and `/api/og/image/sunday/2026-09-27.png` is 404.
    The previous values are restored in `finally`.

## 6. Out of scope

- **Results-upload changes of any kind** (parked by the owner): no change to imports, previews, staging, the special-shoot workbook or the rebuild.
- Push notifications, offline data, background sync, or caching any `/api` response in the service worker.
- Emailing the recap from the app (no SMTP, no mailing list). The admin pastes it.
- Personal or named facts in link previews, and per-shooter OG images.
- Server-rendered pages for people, SEO or indexing (`noindex` everywhere).
- Individual milestones or any milestone ranking. Shooter Sunday milestones remain the existing `pf.sunday-milestone` insight and the Events Attended trophies.
- Turning Cloudflare Access on. The runbook only documents the bypass if it ever is.
- A per-viewer or percentage rollout of switches. Switches are on or off for everyone, with admin preview.
- New insight kinds, trophy kinds, or changes to any existing number, chart, page or Home card (Home only gains elements).
- A database migration (`0009` is left for Plan 20).

## 7. Delivery outline (for the plan author)

| Wave | Tasks (parallel lanes, disjoint files) |
|---|---|
| 1 | T1 launch switches backend (`domain/features.py`, `_features.py`, `features.py`, `admin_features.py`, `etag.py`, `config.py`) |
| 2 | T2 switches frontend (`lib/features.ts`, `FeatureGate`, `AdminPreviewBadge`, `NotFoundView`, `registry.ts` `feature`, nav filtering, `admin-features` page) ∥ T3 link previews backend (`og/` package, Pillow, `app.py` public module, logo, icon generator) |
| 3 | T4 Caddy (`route` block, `/l/` guard, `Vary`), `deploy/caddy/test_crawler_ua.sh` (`caddy validate` + UA table), runbook (incl. step 4 cache note), the CSP and PWA headers, `link-previews.spec.ts` ∥ T5 tour + glossary ∥ T6 club milestones (API + Home + Club) ∥ T7 summary card (API + profile, `lib/share` download) |
| 4 | T8 weekly recap (API + admin page) ∥ T9 PWA (manifest, `pwaShell()`, install tip with launch redirect, `lib/chunkReload.ts`, `playwright.config.ts` `serviceWorkers: 'block'` per D24) |
| 5 | T10 `features.admin-mutations.spec.ts` (incl. the all-switches-off viewer run, D25) + About privacy sentence + owner preview |

Every new user-facing feature merges switched **off** in production (D4). The owner flips each one on from `/admin/features` after preview.
