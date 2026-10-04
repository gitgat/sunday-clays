# Sunday Clays: Club events & registration — Design Spec (Plan 20)

> Date: 2026-10-02 · Status: draft for owner review · Parent spec: `2026-09-27-sunday-clays-design.md` · Contract: master plan C1–C12 · Depends on: Plan 19 (launch switches; Plan 19 adds one migration (`0009`, the page cache, D28), so this plan's migration is `0010`) · Implementation plan: `docs/superpowers/plans/2026-10-02-20-club-events.md` (written after approval)
> Base: `main` @ `fc2a101` (Plans 15, 16 and 17 merged) plus Plan 19.

A **club event** is a one-off, club-only gathering that members sign up for in the app: a work party, a fun shoot, a banquet, a lesson day. It is not a Sunday shoot, has no scores and no ScoreChaser link. Organizers (admins) create it; members (viewers past the club password) see it, say they are coming, and can bring guests.

---

## 1. Context and goals

**Today.** The site only knows Sundays, which arrive as score sheets. Club events are announced by word of mouth and head counts are guessed. Organizers have no list of who is coming and no way to reach them.

**Goals.**

1. Organizers create, edit, cancel and delete an event with a title, a date and start time (America/Los_Angeles), plain-text notes, an optional capacity with an automatic waitlist, a sign-up deadline and a guest rule.
2. Members see upcoming events (past ones collapsed) on a **Club events** page and the next one on a **Coming up** card on Home, and sign up in under 30 seconds on a phone, without an account.
3. Everyone can see **Who's coming**: names and guests in order. Nobody but organizers ever sees an email.
4. Capacity is never overbooked, even when two people tap "Sign up" for the last spot at the same moment. The waitlist moves up on its own, in a predictable order.
5. A member can cancel from the same phone with one tap, or from any device by typing the email they gave. Organizers can remove anyone.
6. Organizers see emails, export the roster as CSV and copy the emails into their own mail program. **The site never sends email.**
7. Personal data is minimal, admin-only, never logged, and deleted on a fixed schedule that the About page states.
8. The whole feature ships dark behind the Plan 19 launch switch `events` and is turned on later with no redeploy.

**Non-goals** are in §8.

---

## 2. Binding owner rules (restated) and where this spec meets them

| Rule | Where |
|---|---|
| Copy never uses he/she/his/her | §5.8 copy table; lint test in §7.3 |
| Named-shooter copy is positive or neutral only | §5.8 (every string names a person neutrally: "Ike Hadley +1"); no comparisons |
| No rating ranking, rivals or head-to-head | Roster order is sign-up order only, never by score or rating (D9) |
| Every data chart has Table, CSV, fullscreen and an ELI5 explainer | This feature adds **no chart** (D12). The roster is a list, and the admin roster has its own CSV |
| Time windows use the header window | The Club events pages show no window filter (D12) |
| The password gate stays | Every viewer route needs `require_viewer` (D2) |
| Nothing is removed from Home | The Coming up card is added; nothing moves out (§5.7.4) |
| Real names never in tracked files | Tests use `Hadley, Ike`, `Amy Ace`, `Bob Bee`, `Cal Cy`, `Pat Kim`, `Dana Quill`; emails on `example.com` |
| Persistent data under `/var/data/sunday-clays/<svc>` | Only new Postgres tables; Postgres already binds there. No new service, volume or image |
| Images are multi-arch | No new image; the existing `api`/`web` images keep their amd64+arm64 build |
| No IPs stored, no access log | Rate limits store `ip_fingerprint` only (§6); no request or body logging (§6.3) |
| Launch switch | §5.1 |

---

## 3. Decisions

**D1. One launch switch, key `events`, default off.** The whole feature (viewer pages, Home card, the About bullet, viewer API) is gated by the Plan 19 switch `events`. While off: admins see every viewer surface with Plan 19's "Admin preview" badge; viewers see no nav item, no Home card, no About bullet, and `/club-events` renders the app's not-found page; every `/api/club-events*` route answers **404 with exactly the body of an unknown `/api` path** (`{"detail":"Not Found"}`, Plan 19 D2) to a viewer session. Admin routes (`/api/admin/club-events*`, `/api/admin/shooter-contacts*`) work regardless, so organizers can prepare the first event before launch. *Rationale:* the shared, owner-approved launch decision; the feature can be tried end to end in production by admins before members see it.

**D2. Members are anonymous viewers; no accounts.** Sign-up and cancel need only the club password session (`require_viewer`). Identity comes from the name picked or typed, and ownership from a per-registration token or the email given. *Rationale:* the password gate stays and there are no logins beyond it (About page promise).

**D3. Name "Club events", path `/club-events`, API `/api/club-events`, tables `club_event*`.** The nav already has **Events** for Sundays (`/events`, `/events/:date`, table `events`). This feature never reuses that word alone. In copy, Sundays are still never called "events" (insights D7); "club event" means only this feature. *Rationale:* two things called "Events" would confuse members and collide with the `events` table and routes.

**D4. Picked names link to shooters; typed names stay event-only.** The picker lists the live shooters (§4: a canonical shooter with a `shooter_profiles` row whose `status` is not `deceased`, which is exactly what `GET /api/shooters` returns minus `status = 'deceased'`). "I'm not listed" accepts a typed name that is stored **on the registration only** (`club_event_registrations.registrant_name`); it never creates a `shooters` row, alias or rule. An organizer can later link that registration to a shooter (D15). *Rationale:* owner decision; the shooter directory stays fed only by score sheets, so a typo or prank cannot create a profile.

**D5. Emails: one per shooter in `shooter_contacts`, one per event-only registration.** A picked shooter with an email on file is never asked again; the form says "We'll use the email we have for you" and never shows it. A picked shooter without one is asked, and the address is saved to `shooter_contacts` (source `signup`). A typed name is always asked, and the address is stored on that registration. A sign-up never overwrites an email on file; only an organizer can change one. *Rationale:* owner decision; asking once keeps sign-up fast, and never overwriting stops a second person from hijacking a shooter's contact.

**D6. Email is required whenever it is asked.** *Rationale:* without it an organizer cannot reach the person and the person cannot cancel from another device (D10b). The field explains who sees it.

**D7. No outbound email at all.** No SMTP setting, no mail library, no "confirm your email" step. Organizers export CSV or copy the addresses (§5.7.5) into their own mail program. *Rationale:* owner decision; no mail infrastructure to secure, no deliverability or spam-law questions.

**D8. Capacity counts spots: one per sign-up plus its guests.** `capacity` is optional (`NULL` = unlimited, so no waitlist ever). *Rationale:* owner decision; guests use a station slot and a lunch plate like anyone else.

**D9. One queue in sign-up order; strict order, no skipping.** Every active registration has a place in one queue ordered by `id`. The row is inserted after the event row lock is taken (D13), so the sequence hands out ids in lock order, which is the order the server decided the sign-ups. `queue_at` is not used for ordering: it defaults to `now()`, the transaction start, which can be earlier for a request that got the lock later. A new sign-up is `going` only if the waitlist is empty **and** its spots fit; otherwise it joins the waitlist at the back. Promotion walks the waitlist from the front and promotes each party that fits; it **stops at the first party that does not fit** (a +3 party at the front is never jumped by a solo behind it). *Rationale:* "deterministic" and easy to explain in one sentence ("Spots go in sign-up order"); members with guests are never penalised. The admin roster shows "1 spot open; the next sign-up on the waitlist needs 3" so an organizer can raise capacity on purpose (§5.7.5).

**D10. Three ways to cancel.** (a) **Same device:** the browser keeps the registration's token in `localStorage` (`sc.clubEvents`) and "Cancel my spot" sends it. (b) **Any device:** "Cancel" next to a name, then type the email given at sign-up (for a picked shooter: the shooter's email on file). (c) **Organizer:** "Remove" in admin. Members may cancel until the event's start time (after the sign-up deadline too, and while the event is cancelled); organizers any time. *Rationale:* owner decision; letting people cancel after the deadline frees spots for the waitlist.

**D11. Cancel by email is constant-time, rate limited, and says nothing.** The typed email is normalised (§5.3.6). Both sides are then hashed to fixed-length bytes, `hmac.new(key, s.encode("utf-8", "surrogatepass"), hashlib.sha256).digest()` with `key = settings.session_secret`, and the two 32-byte digests are compared with `hmac.compare_digest`. When nothing is stored, the typed digest is compared with a fixed dummy digest (`hmac.new(key, b"\x00no-email", sha256).digest()`), so a missing email and a wrong one take the same path and time. Hashing first means a non-ASCII address (`ü@x.de`, which the §5.3.6 regex allows and NFKC keeps) never reaches `compare_digest` as a `str` (where it raises `TypeError`), and the comparison never leaks the stored address's length. Every failure answers the same **403 `cancel_not_matched`**, "That email doesn't match this sign-up. Check it and try again." Failures are limited per client and per registration (§5.3.7). *Rationale:* the response must never reveal which email is on file, or that a typed one is close.

  *Accepted exception (owner's form requirement):* `signup-check` returns `has_email` per shooter, so a member past the password can learn, shooter by shooter, **whether** an email is on file (never the address). The owner's form needs that bit to skip the email field ("We'll use the email we have for you"). It is bounded by the `check` limit (§5.3.7) and every call is an attempt row. D11's "say nothing" covers the cancel response only.

**D12. No charts and no time-window filter on these pages.** Pages register `handle.filters = NO_FILTERS`. Upcoming events are by definition in the future and past ones are a short collapsed list, so the header window would hide nothing useful. *Rationale:* filters-not-in-sidenav: each page shows only the filters it honours. Any future chart (for example turnout per club event) must use ChartFrame with Table, CSV, fullscreen and an explainer, and the header window.

**D13. Concurrency: one row lock per event.** Every write that can change who holds a spot (sign up, cancel, remove, guest change, capacity change, restore) first runs `SELECT … FROM club_events WHERE id = :id FOR UPDATE` in its transaction, then reads the queue, decides, writes and commits. Partial unique indexes (§5.2) back the duplicate rule. *Rationale:* writes for one event serialise, writes for different events do not, and the rule is visible in one place. An advisory lock would work too but adds a second lock namespace for no gain.

**D14. Duplicate rule per event.** While a registration is `going` or `waitlist`: one per shooter (after resolving merges), and one per typed-name key. A typed name that equals a directory name (in either "First Last" or "Last, First" order) is refused and the member is sent back to the picker. *Rationale:* owner's spam rule; also stops "I'm not listed" being used to double-book a listed shooter.

**D15. Linking is an organizer action, not an overlay rule.** `POST /api/admin/club-events/{id}/registrations/{rid}/link` sets the registration's `shooter_id`, moves its email into `shooter_contacts` if the shooter has none (source `link`), and clears `registrant_email`. When the shooter already has a contact, the registration's email is **deleted**, not merged (the contact on file wins, D5); the audit row records `email_discarded: true`, and the admin UI says so before confirming ("Hadley, Ike already has an email on file. The email typed at sign-up will be deleted."). The admin roster suggests a match when the typed name is similar to a directory name (`ingest.names.similar_name_keys`). *Rationale:* overlay rules (`rules`) feed the score rebuild; registrations are not score data, so a rebuild must never touch them. The owner's "later admin rule" is this audited action.

**D16. Retention: 30 days after the event.** The daily job `club_event_retention` (§5.6) handles each event whose `starts_at` is more than **30 days** ago: it snapshots the counts into `final_signups` and `final_spots`, then deletes **every** registration of that event (so every name, typed or picked, every event-only email and every token goes). Nothing else about who came is kept: the viewer roster is `[]` once purged, and recording attendance is out of scope (§8), so a kept list would have no use. Cancelled and removed registrations lose their email and token **at the moment** of cancelling. A shooter's email in `shooter_contacts` is deleted when unused for **730 days** (no sign-up and no organizer edit). *Rationale for 30:* organizers follow up after an event (money, lost property, photos, "thanks for coming") within a week or two; 30 days covers that with margin and also gives an organizer time to link new names once the next score sheet adds them to the directory. Anything longer keeps emails of one-time guests for no purpose. *Rationale for 730:* a member's email on file is what makes the next sign-up one tap; two years without a sign-up means the person has likely left, and the About page can state one simple rule.

**D17. Rate limits are keyed HMAC fingerprints.** All limits use `auth.deps.ip_fingerprint` in a new `club_event_attempts` table, pruned after a day, exactly as `bump_attempts` and `page_view_attempts`. *Rationale:* Plan 16 privacy rule; no IP is stored.

**D18. Plain text only.** Notes, titles and names are rendered as React text with `white-space: pre-line`; there is no HTML, Markdown or auto-linking. *Rationale:* owner decision; React text escaping plus the existing CSP makes stored-XSS impossible by construction.

**D19. Migration `0010_club_events`, expand-only, one file.** `down_revision` is the Alembic head on `main` when this plan merges. Plan 19 lands `0009` (its page-cache table, Plan 19 D28) first, so today that is `"0009"`. If anything else lands a `0010` first, this file is renumbered to the next free number with `down_revision` set to that head. **Pre-merge check** (a task step and a CI-visible test): `uv run alembic heads` prints exactly one head, `0010_club_events` (or its renumbered name), and `test_migration_chain_is_linear` passes. Four new durable tables; nothing existing changes. *Rationale:* safe while the previous release runs (it never reads them), and `domain/rebuild.py` `LIVE_TABLES` never lists them, so a rebuild keeps them.

**D20. Viewer responses are never cached or ETagged.** `"/api/club-events"` (no trailing slash, so the root list path `/api/club-events` matches too) joins both `NO_ETAG_PREFIXES` and `NO_STORE_PREFIXES` in `api/etag.py`, beside `/api/auth/`, `/api/admin/` and Plan 19's `/api/features`. *Rationale:* the roster changes without a `data_version` bump; an ETag would answer 304 with a stale list (the Plan 15 bumps lesson).

**D21. Times are entered and shown in America/Los_Angeles.** The admin form takes a local date and time (`settings.timezone`); the API stores `timestamptz`. A local time that does not exist (the spring-forward gap) is refused; an ambiguous one (the fall-back hour) takes the first occurrence. *Rationale:* the club is in Oregon; members never think in UTC. The server also sends every date and time a member reads already in club time (`local_date`, `local_time`, `deadline_local_date`, `deadline_local_time`) and decides every open / closed / started / upcoming state itself (`state`, the `upcoming` / `past` split). The client never formats a timestamp with the device's time zone and never compares anything with the device clock.

**D22. Database errors never carry an email out of the app.** A CHECK or NOT NULL violation on a table with an email column makes Postgres attach `DETAIL: Failing row contains (…)`, which includes the email, and SQLAlchemy's `StatementError` appends `[parameters: {…}]`. Four layers stop that reaching a log:
  1. `db.make_engine` passes `hide_parameters=True` to `create_engine` (app-wide; no existing log relies on bound parameters).
  2. Every write in `api/routes/club_events.py`, `api/routes/admin_club_events.py` and `api/routes/admin_shooter_contacts.py` (including the link route) runs inside `domain.club_events.scrub_db_errors()`, a context manager that catches `sqlalchemy.exc.DBAPIError` (which covers `IntegrityError`), logs one line with the exception class name and the constraint name only (`exc.orig.diag.constraint_name`), and raises `DomainError(500, "internal", "Internal server error")` **from `None`**, so neither the message nor the cause chain reaches the unhandled-error handler's `exc_info`. A unique violation on `uq_club_event_registrations_shooter` or `_name` (a race the lock should already prevent) maps to 409 `already_signed_up` instead.
  3. The domain validates every value a CHECK covers before writing (length, status, guests, the who rule, the scrub rule), so a CHECK violation is a bug backstop, not a user path.
  4. Postgres's own server log is outside the app: the deploy runbook (`deploy/README.md`, this plan's deploy task) adds a one-time step for the operator, `ALTER DATABASE sunday_clays SET log_error_verbosity = 'terse';` run as the database superuser on `autopirate`, which drops `DETAIL` lines from the server log.
  *Rationale:* the reviewer's finding was right: a missing index does not keep an email out of an error message, because the failing-row detail quotes every column.

**D23. Gated routes and malformed JSON.** `feature_gate("events")` is a router-level dependency, so it runs before body validation and before the handler (no attempt row is written while the switch is off). FastAPI decodes the raw JSON before any dependency, so a POST whose body is not valid JSON gets a 422 even while gated. *Rationale for accepting it:* it reveals only that a path exists, only to someone past the club password, and working around it would mean hand-parsing every body.

**D24. No crawler or service-worker bypass.** Club-event pages are members-only. Plan 19 sends crawler user agents on any SPA path to `/api/og/page/<path>`; its `og/facts.py facts_for_path` maps every `club-events/*` path to the **generic** club preview (no title, date, count or name), and a test pins that. "Copy link" copies the plain `/club-events/:id` URL, never a `/l/` share link; a person who is not a member lands on the password page. Any future crawler allowance must keep `/club-events*` and `/api/club-events*` generic. Plan 19's service worker ignores every `/api/` request and fetches navigations network-first, so it can never serve a stale roster; a stale lazy chunk after a deploy behaves as for every other lazy route today (the route error page, fixed by a reload), and this plan adds no special handling.

**D25. Review points not adopted, and why.**
  - *Crawler e2e asserting the login page:* with Plan 19 merged, a crawler UA on `/club-events/1` is routed to the generic OG page, not the password page. The e2e (§7.4) instead asserts the generic preview with no event title, so it checks the real privacy property (nothing leaks) against the real routing.
  - *"The app has no service worker":* true on `main` today, but Plan 19 (a dependency of this plan) adds `/sw.js`; D24 states how it interacts.
  - *A `vite:preloadError` reload for the new lazy routes:* not added; a stale chunk is existing app-wide behaviour, and a fix belongs to all lazy routes at once, not to one feature.

---

## 4. Terms

| Term | Meaning |
|---|---|
| Registration | One sign-up row: one person (picked or typed) plus `guests` unnamed guests |
| Spots | `1 + guests` for one registration; an event's spots taken = sum over `going` registrations |
| Active | Status `going` or `waitlist` |
| Queue order | `id` ascending (assigned under the event lock, D9); `queue_at` is the displayed sign-up time and never changes |
| Waitlist position | 1-based rank of a `waitlist` registration in queue order among waitlist rows |
| Open | Not cancelled and server `now() < signup_deadline` |
| Started | Server `now() >= starts_at` |
| Upcoming / past | Upcoming while the event's local date (club time zone) is the server's local today or later; past after that. An event at 23:30 LA (07:30 UTC the next day) stays upcoming, and shows "Happening now" once started, until LA midnight |
| Purged | `roster_purged_at` set by the retention job |
| Live shooter | A canonical shooter (not a merge source in `domain.identity.merge_map`) with a `shooter_profiles` row whose `status` is not `deceased`. A shooter with no profile row (every round hidden, or no live rounds) is not live: it cannot be picked and does not block a typed name |
| Display name | `shooter_profiles.display_name` (rename rules applied), falling back to `shooters.display_name` when a linked shooter later loses its profile row |

---

## 5. Design

### 5.1 Launch switch (consumed from Plan 19)

Plan 19 owns the mechanism: the admin **Features** page, the `app_state` storage, the audit row for a flip, the backend dependency that 404s a viewer when a switch is off, the frontend hook that reports `on | preview | off` for the current session, the route-handle gate and the "Admin preview" badge. This spec uses that contract with the key **`events`** (label on the Features page: "Club events", description "Club event sign-ups: the Club events page, the Coming up card on Home and the sign-up line on About."). The exact integration points, all named in Plan 19 §3.0:

| Piece | Name (Plan 19) | Use here |
|---|---|---|
| Registry | `domain/features.py` `FEATURES` tuple and `FeatureKey` | gains `Feature(key="events", label=…, description=…)` |
| Backend gate | `api/routes/_features.py` `feature_gate("events")` | router-level dependency of `api/routes/club_events.py`: `APIRouter(prefix="/api/club-events", dependencies=[feature_gate("events")])` (Plan 19's `feature_gate` returns `Depends(gate)` and `gate` depends on `require_viewer`; discovery adds `require_viewer` too) |
| Frontend hook | `lib/features.ts` `useFeature('events')` → `{ visible, preview, on }` | Home card, About bullets, the "Admin preview" badge |
| Route gate | `<FeatureGate feature="events">` (`components/FeatureGate.tsx`) | wraps both lazy pages in `features/club-events/routes.tsx` |
| Nav key | `NavItem.feature: 'events'` | the "Club events" nav item |
| Badge | `components/ui/AdminPreviewBadge.tsx` | beside the page `h1`, the Home card title and the About bullets when `preview` |
| Test stack | `FEATURES_DEFAULT_ON` | `compose.test.yaml` does **not** list `events`: the read-only e2e checks the off state and the admin-mutations spec flips it (§7.4) |
Gated surfaces:

| Surface | Off, viewer | Off, admin | On |
|---|---|---|---|
| Nav item "Club events" | hidden | shown, badge | shown |
| `/club-events`, `/club-events/:id` | not-found page | page, badge by the title | page |
| Home "Coming up" card | not rendered (no request sent) | card, badge | card |
| About bullet (§5.7.6) | not rendered | rendered, badge | rendered |
| `GET/POST /api/club-events*` | 404 `{"detail":"Not Found"}` | served | served |
| `/api/admin/club-events*`, `/api/admin/shooter-contacts*` | 403 (not admin) | served | served |

The 404 is decided before body validation, rate limiting or any read (except a body that is not valid JSON, D23), so a viewer cannot tell the feature exists. Flipping the switch takes effect on the next request (Plan 19 reads `app_state` per request); the frontend refetches the switch state on window focus and at most every 60 s, as Plan 19 defines.

**Switch flipped off mid-sign-up.** The sheet's POST gets the 404. Because the gate runs before the handler, no attempt row, registration or contact is written; nothing is half-done. The sheet shows "Club events aren't available right now. Nothing was saved." with a Close button, then invalidates `['/api/features']`, so the page falls to `NotFoundView` on the refetch. Stored tokens are kept for when the switch comes back on.

### 5.2 Data model (migration `0010_club_events`)

All tables are durable (never in `LIVE_TABLES`), use the repo's `conv()` constraint names, and are created in one migration. Downgrade drops the four tables.

**`club_events`**

| Column | Type | Rule |
|---|---|---|
| `id` | `integer` PK | |
| `title` | `text NOT NULL` | CHECK `char_length(title) BETWEEN 1 AND 80` |
| `starts_at` | `timestamptz NOT NULL` | |
| `signup_deadline` | `timestamptz NOT NULL` | CHECK `signup_deadline <= starts_at` |
| `notes` | `text NOT NULL DEFAULT ''` | CHECK `char_length(notes) <= 2000` |
| `capacity` | `smallint NULL` | CHECK `capacity IS NULL OR capacity BETWEEN 1 AND 500` |
| `allow_guests` | `boolean NOT NULL DEFAULT false` | |
| `max_guests` | `smallint NOT NULL DEFAULT 0` | CHECK `max_guests BETWEEN 0 AND 10`; CHECK `(allow_guests AND max_guests >= 1) OR (NOT allow_guests AND max_guests = 0)` |
| `cancelled_at` | `timestamptz NULL` | set by cancel, cleared by restore |
| `roster_purged_at` | `timestamptz NULL` | set by the retention job |
| `final_signups` | `smallint NULL` | going registrations at purge |
| `final_spots` | `smallint NULL` | going spots at purge |
| `created_at`, `updated_at` | `timestamptz NOT NULL DEFAULT now()` | |

Index `ix_club_events_starts_at (starts_at)`.

**`club_event_registrations`**

| Column | Type | Rule |
|---|---|---|
| `id` | `integer` PK | |
| `event_id` | `integer NOT NULL` FK `club_events.id ON DELETE CASCADE` | |
| `shooter_id` | `integer NULL` FK `shooters.id` | set for a picked name or after a link |
| `registrant_name` | `text NULL` | the typed name (cleaned with `ingest.names.clean_display_name`); kept after a link so the organizer sees what was typed; CHECK `char_length <= 60` |
| `name_key` | `text NULL` | signup key of `registrant_name` (§5.3.5) |
| `registrant_email` | `text NULL` | event-only email, normalised; CHECK `char_length <= 254` |
| `guests` | `smallint NOT NULL DEFAULT 0` | CHECK `guests BETWEEN 0 AND 10` |
| `status` | `text NOT NULL` | CHECK `status IN ('going','waitlist','cancelled','removed')` |
| `queue_at` | `timestamptz NOT NULL DEFAULT clock_timestamp()` | display only ("Signed up" time); inserted after the lock, so `clock_timestamp()` is the decision time. Never used for ordering (D9) |
| `token_hash` | `text NULL` | hex SHA-256 of the device token; NULL once inactive or purged |
| `promoted_at` | `timestamptz NULL` | set when moved from waitlist to going |
| `cancelled_at` | `timestamptz NULL` | |
| `cancelled_via` | `text NULL` | CHECK `IN ('device','email','organizer')` |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | |

Table checks: `ck_…_who`: `shooter_id IS NOT NULL OR (registrant_name IS NOT NULL AND name_key IS NOT NULL)`; `ck_…_email_owner`: `registrant_email IS NULL OR shooter_id IS NULL`; `ck_…_inactive_scrubbed`: `status IN ('going','waitlist') OR (registrant_email IS NULL AND token_hash IS NULL)`.

Indexes: `ix_club_event_registrations_queue (event_id, status, id)`; partial unique `uq_club_event_registrations_shooter (event_id, shooter_id) WHERE status IN ('going','waitlist') AND shooter_id IS NOT NULL`; partial unique `uq_club_event_registrations_name (event_id, name_key) WHERE status IN ('going','waitlist') AND shooter_id IS NULL`. No index includes `registrant_email`, so a unique-violation `DETAIL` never quotes one. A CHECK or NOT NULL violation still quotes the whole failing row, email included; D22 keeps that out of the app log and the Postgres server log.

**`shooter_contacts`**

| Column | Type | Rule |
|---|---|---|
| `shooter_id` | `integer` PK, FK `shooters.id` | |
| `email` | `text NOT NULL` | normalised; CHECK `char_length(email) BETWEEN 3 AND 254` |
| `source` | `text NOT NULL` | CHECK `IN ('signup','organizer','link')` |
| `created_at`, `updated_at` | `timestamptz NOT NULL DEFAULT now()` | |
| `last_used_at` | `timestamptz NULL` | set on every sign-up that uses it |

**`club_event_attempts`** (rate-limit log)

| Column | Type | Rule |
|---|---|---|
| `id` | `integer` PK | |
| `ip` | `text NOT NULL` | `ip_fingerprint(request)`, never an address |
| `action` | `text NOT NULL` | CHECK `IN ('signup','check','cancel_fail')` |
| `registration_id` | `integer NULL` | no FK (a purge must not cascade the limiter) |
| `at` | `timestamptz NOT NULL DEFAULT now()` | |

Indexes `(ip, action, at)` and `(registration_id, at)`. Every insert goes through `auth.ratelimit._insert_and_prune` with `keep_for = timedelta(days=1)`, so the table is pruned on write (as `bump_attempts` and `page_view_attempts` are) as well as by the daily job.

**Rollback limit** (stated in the migration docstring, as `0008` does): the previous release never reads these tables, so rolling the app back is safe at any time; `alembic downgrade 0009` deletes every event, registration and stored email.

### 5.3 Domain rules (`domain/club_events.py`)

Pure functions where possible, so the queue logic is unit-tested without a database.

1. **Admit.** `admit(queue, capacity, new_spots) -> 'going' | 'waitlist'`: `going` when `capacity IS NULL`, or when no row is `waitlist` and `going_spots + new_spots <= capacity`; else `waitlist`.
2. **Promote.** `promotions(queue, capacity) -> list[registration_id]`: walk `waitlist` rows in queue order; promote while `going_spots + spots <= capacity`; stop at the first that does not fit. With `capacity IS NULL`, every waitlist row is promoted. Runs after cancel, remove, guest decrease, capacity increase and restore, inside the same locked transaction, and only while the event has not started and is not cancelled. Each promoted row gets `status = 'going'`, `promoted_at = now()`; `id` and `queue_at` are unchanged.
3. **Capacity change.** An organizer may not set `capacity` below the spots already `going`: 409 `capacity_below_going`, "N spots are already taken. Remove people first, or set at least N." Lowering it otherwise never demotes anyone. Changing `capacity` from a number to `NULL` promotes the whole waitlist.
4. **Guest rules.** A sign-up's `guests` must be `0` when `allow_guests` is false, else `0..max_guests`. Changing `allow_guests` or `max_guests` later never alters existing registrations. An organizer may change a registration's guests (0..10, ignoring `max_guests`); an increase on a `going` row that would exceed capacity is refused with 409 `over_capacity`, "That would go over capacity by N."
5. **Signup key.** `signup_key(name) = " ".join(sorted(ingest.names.name_key(name).split()))`, so "Ike Hadley" and "Hadley, Ike" share a key. A typed name must have at least two words after cleaning (400 `name_needs_last`, "Add your last name too, so organizers know who you are.") and 2–60 characters. A typed name is refused with 409 `name_on_list` when its key is in `listed_keys(session)`, which contains, for **live shooters only** (§4): `signup_key(display_name)` of each, and `signup_key(alias.name_key)` of every `shooter_aliases` row whose shooter resolves (through `domain.identity.merge_map`) to a live shooter. Alias keys go through `signup_key` too, because `name_key` is not word-sorted. `alias_name` rules (`domain.identity.alias_rule_targets`) are included the same way: each rule key whose target resolves to a live shooter. A name that belongs only to a profile-less or deceased shooter is accepted as a typed name, because that shooter cannot be picked either; this removes the dead end where the picker has no row and typing is refused.
6. **Email normalisation.** Strip, NFKC, lowercase. Valid when it matches `^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$` and is at most 254 characters; else 400 `bad_email`, "Enter an email like name@example.com." Validation lives in the domain. The request field is an **unconstrained** `email: str | None = None` (no `max_length`, no pattern); Caddy's existing 264 KiB request-body cap is the size bound, and the domain refuses anything over 254 characters with the same 400. Likewise `name: str | None = None` has no constraint (the domain checks 2–60 characters), and "exactly one of `shooter_id` and `name`" is a domain check (400 `pick_or_type`, "Pick a name from the list, or choose I'm not listed."), not a Pydantic `model_validator`. So the only 422 these bodies can produce is a field of the wrong JSON type (whose `detail.input` echoes that one non-string value) or a body that is not a JSON object (echoed only to the sender; 422s are never logged).
7. **Limits** (settings, so the e2e stack can raise them in `compose.test.yaml`):

   | Setting (env) | Default | Counted | Window | Over the limit |
   |---|---|---|---|---|
   | `club_event_signup_limit` (`CLUB_EVENT_SIGNUP_LIMIT`) | 100 | every sign-up POST, success or not | 60 min, per fingerprint | 429 `rate_limited` |
   | `club_event_check_limit` (`CLUB_EVENT_CHECK_LIMIT`) | 60 | every `signup-check` | 10 min, per fingerprint | 429 |
   | `club_event_cancel_fail_limit` (`CLUB_EVENT_CANCEL_FAIL_LIMIT`) | 10 | failed cancels (wrong email or token) | 60 min, per fingerprint | 429 |
   | constant `CANCEL_FAIL_PER_REGISTRATION` | 5 | failed **email** cancels on one registration, any fingerprint | 60 min | 429 on the **email** path only; the token path and organizer removal are never blocked by it |
   | constant `MAX_ACTIVE_PER_EVENT` | 200 | active registrations on one event | — | 409 `signups_full`, "This list has reached its limit. Ask an organizer." |

   The attempt row is written and committed before the request is validated (as bumps do), so a refused request still counts. A 429 says "Too many tries from here. Wait a bit and try again."

   *Why 100 sign-ups an hour.* Club Wi-Fi and carrier NAT put 20–30 phones behind one address (the Plan 15 bump limit comment), and a banquet announced at the shoot can send most of them to the form within minutes, each with a typo retry or two. 100 per hour per address covers 40 people with 1.5 tries each with room to spare, while a script is still capped at 100 junk rows an hour and `MAX_ACTIVE_PER_EVENT` caps any one event at 200. Organizers can remove junk rows (each is audited).

   *Why 60 checks per 10 minutes.* Each name picked in the sheet is one check; 30 phones picking a name and maybe a second one fit. A script walking a 200-name directory for `has_email` needs over 30 minutes, and every call is an attempt row (D11 accepted exception). The previous 120 let a walk finish in about 15 minutes.

   *Accepted risk on the per-registration limit.* Anyone past the password can type five wrong emails on someone else's registration and lock that registration's **email** cancel for an hour. The owner keeps the limit because without it the email path can be guessed at the per-fingerprint rate from many addresses. The person still cancels from the signing-up device (the token path is exempt), and an organizer can remove the registration or reset its counter (`POST /api/admin/club-events/{id}/registrations/{rid}/reset-cancel-limit`, §5.5) at any time, whatever the counter says.
8. **Merges.** The picker shows live shooters only (§4). A stored `shooter_id` that a later merge rule maps away is resolved through `domain.identity.merge_map` everywhere: display name, duplicate check, and contact lookup (the canonical shooter's contact, else the most recently updated contact among shooters merged into it). Roster names are the display name (§4): `shooter_profiles.display_name` of the resolved shooter, else `shooters.display_name`.
9. **Lock order.** Every write takes the event row lock (D13) before anything else and before touching `shooter_contacts`; contact writes use `INSERT … ON CONFLICT (shooter_id) DO NOTHING` for sign-ups so the first email wins and a racing second sign-up keeps its registration but its email is ignored (the response says `email_used: 'on_file'`, and the sheet shows the §5.8 "on file" line). A job or route that locks several events (only the retention job, §5.6) locks them in ascending `id` order.
10. **Link suggestions.** `suggested_shooter` calls `ingest.names.similar_name_keys(key, frozenset(), candidates)` with `key = name_key` of the typed name, an empty `key_dates` set (a registration has no shoot dates) and `candidates = {name_key(display_name): frozenset() for each live shooter}` (empty date sets, so no candidate is excluded by a shared date). The first match in the sorted result is suggested; none → `null`.
11. **Edits to an event (PATCH).** `starts_local` is re-validated (`starts_in_past`, `bad_local_time`) **only when it changes**; a PATCH that touches only notes, title, capacity or guests on a past event is accepted. Moving the start of an event that has **started** or is **purged** is refused with 409 `event_started`, "This event has already started, so its date can't change." (otherwise a purged, empty event could come back as upcoming). `deadline_local` is re-validated only when it changes, against the new or current start (`deadline_after_start`); a deadline moved into the past is allowed and closes sign-ups at once (`state` becomes `closed` on the next read). Moving the start (earlier or later, still in the future) changes no registration: `going` stays `going`, the waitlist keeps its order, and promotions run as after any PATCH.

### 5.4 Viewer API (`api/routes/club_events.py`, discovered, `require_viewer`, launch-gated)

All responses carry `Cache-Control: no-store` and no ETag (D20). Times are ISO 8601 with offset; every event object also carries `local_date` (`YYYY-MM-DD`) and `local_time` (`HH:MM`) for the start, and `deadline_local_date` and `deadline_local_time` for the deadline, all in the club time zone. The client formats only these local fields (as plain calendar parts, never through `new Date(iso)`), and takes every open / closed / started / upcoming decision from `state` and the `upcoming` / `past` split, never from the device clock (D21).

**`GET /api/club-events`** → `{ "upcoming": [EventSummaryOut], "past": [EventSummaryOut] }`. Upcoming in `starts_at` ascending, including cancelled ones (shown with a badge); past in `starts_at` descending, all of them.

`EventSummaryOut`: `id, title, starts_at, local_date, local_time, signup_deadline, deadline_local_date, deadline_local_time, state ('open' | 'closed' | 'started' | 'cancelled'), capacity, spots_taken, waitlist_count, allow_guests, max_guests, signups (going registrations count), purged (bool)`. For a purged event, `spots_taken` and `signups` come from `final_spots` and `final_signups`.

**`GET /api/club-events/{id}`** → `EventDetailOut` = summary + `notes` + `roster`. `roster` is `[]` once purged. Roster rows: `{ registration_id, name, shooter_id | null, guests, status ('going' | 'waitlist'), waitlist_position | null }`, going rows first in queue order, then waitlist rows in queue order. `name` is the display name (§4) of the resolved shooter, else `registrant_name`. Cancelled and removed rows are never listed. A cancelled event's roster is shown as usual (with `state: 'cancelled'`), so the per-name Cancel stays available until the start (§5.9). No email, token, `queue_at` or `created_at` is ever in a viewer response. 404 `club_event_not_found` for an unknown id.

**`GET /api/club-events/{id}/signup-check?shooter_id=N`** → `{ "has_email": bool, "already_signed_up": bool }`. Counts toward the `check` limit. `has_email` is the one bit the owner's form needs ("We'll use the email we have for you"); the address itself is never returned.

**`POST /api/club-events/{id}/registrations`** body `{ "shooter_id": int | null, "name": str | null, "email": str | null, "guests": int }` (all fields unconstrained, §5.3.6). Steps, in order: launch gate (dependency); record `signup` attempt and commit; exactly one of `shooter_id` and `name`, else 400 `pick_or_type`; limit check; lock event; refuse when cancelled (409 `event_cancelled`), past the deadline (409 `signups_closed`, "Sign-ups for this event have closed."), or at `MAX_ACTIVE_PER_EVENT`; validate guests (400 `bad_guests`); for `shooter_id`: shooter must resolve to a live shooter (§4; else 404 `shooter_not_found`), duplicate check (409 `already_signed_up`, "{name} is already on the list."), contact on file → email ignored, else email required (400 `email_required`) and saved to `shooter_contacts`; for `name`: §5.3.5 checks, duplicate check (409 `already_signed_up`), email required and stored on the row; admit (§5.3.1); insert the row (its `id` from the sequence, `queue_at = clock_timestamp()`, both after the lock, D9); generate a token (`secrets.token_urlsafe(32)`), store its SHA-256; update `shooter_contacts.last_used_at`. The whole write runs inside `scrub_db_errors()` (D22). → **201** `{ registration_id, token, status, waitlist_position | null, email_used: 'on_file' | 'given' }`. The token is returned exactly once.

**`POST /api/club-events/{id}/registrations/{rid}/cancel`** body `CancelIn{ token: str | None = None, email: str | None = None }`, a discriminated "exactly one of": both or neither non-null → 400 `token_or_email`, "Send the sign-up's token or an email, not both." Steps: launch gate; exactly-one check; lock event; the registration must belong to the event and be active, else 404 `registration_not_found`; started → 409 `event_started`, "This event has started. Ask an organizer to change the list."; check limits: the per-fingerprint failure limit for both paths, and `CANCEL_FAIL_PER_REGISTRATION` for the **email path only** (429); verify (D11): for a token, `hmac.compare_digest(hashlib.sha256(token.encode("utf-8", "surrogatepass")).hexdigest().encode(), (token_hash or DUMMY_TOKEN_HASH).encode())`; for an email, normalise and compare HMAC digests (D11) with the registration's `registrant_email`, else the resolved shooter contact, else the dummy digest; on failure record `cancel_fail` (with `registration_id`), commit, then 403 `cancel_not_matched`. On success: `status = 'cancelled'`, `cancelled_at`, `cancelled_via`, `registrant_email = NULL`, `token_hash = NULL`; run promotions → 200 `{ "status": "cancelled", "promoted": int }`. A registration at its per-registration limit therefore answers 429 even to the right **email** for the rest of the hour, but a correct token still cancels it. Cancelling is allowed on a cancelled event (D10).

### 5.5 Admin API

All under `require_admin` via `admin_actor`, `no-store`, never ETagged (existing `/api/admin/` rules). Every mutation, every export and every read that shows emails (the roster and the contacts list) writes one `audit_log` row through `record_audit` in the same transaction. **Audit details never include an email or a person's name** (typed or picked); a registration is identified by `registration_id` and a contact by `shooter_id`, and an email change is recorded as `{"email_changed": true}`. Audit rows have no end date, so they must hold nothing the 30-day purge is meant to remove. The two audited reads are fetched with `refetchOnWindowFocus: false` and `staleTime: Infinity` (refetched after a mutation), so a tab switch does not write an audit row.

`api/routes/admin_club_events.py`, prefix `/api/admin/club-events`:

| Method and path | Body / result | Audit action |
|---|---|---|
| `GET /` | every event, newest first, with counts | — |
| `POST /` | `{ title, starts_local: "YYYY-MM-DDTHH:MM", deadline_local, notes, capacity, allow_guests, max_guests }` → 201 event. `starts_local` must be in the future (400 `starts_in_past`); deadline ≤ start (400 `deadline_after_start`); unknown local time 400 `bad_local_time` | `club_events.create` `{id, title, starts_at}` |
| `PATCH /{id}` | any subset of the create fields; §5.3.11 for start and deadline, §5.3.3 for capacity; runs promotions | `club_events.update` `{id, changed: [field names]}` |
| `POST /{id}/cancel` | sets `cancelled_at`; registrations stay as they are (so a restore puts everyone back) | `club_events.cancel` `{id, going, waitlist}` |
| `POST /{id}/restore` | clears `cancelled_at`; 409 `event_started` once started; runs promotions | `club_events.restore` `{id}` |
| `DELETE /{id}` | hard delete, cascades registrations; the UI asks "Delete {title} and its sign-up list? This can't be undone." | `club_events.delete` `{id, title, registrations}` |
| `GET /{id}/roster` | every registration, all statuses: `id, name, typed_name, shooter_id, email, email_source ('contact' | 'registration' | null), guests, status, waitlist_position, signed_up_at, promoted_at, cancelled_at, cancelled_via, suggested_shooter ({id, name} | null), cancel_fail_count` | `club_events.roster_view` `{id, rows}` |
| `GET /{id}/roster.csv` | `text/csv; charset=utf-8`, `Content-Disposition: attachment; filename="club-event-{id}-{local_date}-roster.csv"`; columns `status, waitlist_position, name, shooter_id, email, guests, spots, signed_up_local`; active rows only, queue order; every cell passes through `csv_safe(cell)` (below) | `club_events.roster_export` `{id, rows}` |
| `GET /{id}/emails?status=going\|waitlist\|active` | `{ "emails": [str] }` distinct, queue order, for "Copy emails" | `club_events.emails_copy` `{id, status, count}` |
| `DELETE /{id}/registrations/{rid}` | `status = 'removed'`, `cancelled_via = 'organizer'`, scrub email and token; runs promotions; never blocked by any rate limit | `club_events.registration.remove` `{id, registration_id}` |
| `PATCH /{id}/registrations/{rid}` | `{ guests }` (§5.3.4); runs promotions on a decrease | `club_events.registration.guests` `{id, registration_id, from, to}` |
| `POST /{id}/registrations/{rid}/reset-cancel-limit` | deletes `club_event_attempts` rows with `action = 'cancel_fail'` and this `registration_id` → 200 `{ "cleared": int }` | `club_events.registration.reset_cancel_limit` `{id, registration_id, cleared}` |
| `POST /{id}/registrations/{rid}/link` | `{ shooter_id }`; D15; 409 `already_signed_up` if that shooter is already active on the event; 409 `already_linked` | `club_events.registration.link` `{id, registration_id, shooter_id, email_moved: bool, email_discarded: bool}` |

`csv_safe(cell: str) -> str` lives in `api/csv_safe.py` and is the only escaping path for this CSV (and for any later server-side CSV). It prefixes `'` when the cell's first character is `=`, `+`, `-`, `@`, a tab (`\t`) or a carriage return (`\r`), or when the cell starts with any run of whitespace followed by one of `= + - @`. It is unit-tested on its own (§7.1).

Organizers sign up on members' behalf through the normal viewer form (an admin session is also a viewer); there is no separate admin "add" endpoint.

`api/routes/admin_shooter_contacts.py`, prefix `/api/admin/shooter-contacts`:

| Method and path | Body / result | Audit action |
|---|---|---|
| `GET /` | `[{ shooter_id, name, email, source, updated_at, last_used_at }]`, by name | `shooter_contacts.view` `{rows}` |
| `PUT /{shooter_id}` | `{ email }` → upsert with source `organizer` | `shooter_contacts.set` `{shooter_id, email_changed: true}` |
| `DELETE /{shooter_id}` | 204; 404 `contact_not_found` | `shooter_contacts.delete` `{shooter_id}` |

### 5.6 Retention job (`jobs/club_event_retention.py`)

Kind `club_event_retention`, enqueued by `jobs/scheduler.schedule_due` once per local day after `ROLLUP_LOCAL_HOUR` (03:00), with `dedupe_key="club_event_retention"`, before the weather early return (like `page_view_rollup`). One transaction:

1. Select every event with `starts_at < now() − interval '30 days'` and `roster_purged_at IS NULL`, `ORDER BY id FOR UPDATE` (one statement, so the locks are taken in ascending `id` order, §5.3.9). For each: set `final_signups`, `final_spots` from `going` rows; delete **all** its registrations; set `roster_purged_at = now()`. The 30 days count from the `starts_at` instant (an event at 23:30 LA on Sat, Oct 17 is `2026-10-18T06:30Z`; it becomes due at `2026-11-17T06:30Z`, so the Nov 16 03:00 LA run, at `11:00Z` on Nov 16, keeps it and the Nov 17 run purges it; counting from the local date would wrongly purge it on Nov 16).
2. Delete `shooter_contacts` where `greatest(updated_at, coalesce(last_used_at, updated_at)) < now() − interval '730 days'`.
3. Delete `club_event_attempts` older than one day (a backstop; inserts already prune, §5.2).
4. Log counts only: `"club events purged=%d contacts expired=%d"`.

The constants are `ROSTER_RETENTION_DAYS = 30` and `CONTACT_RETENTION_DAYS = 730` in `domain/club_events.py`, each with a comment pointing at the About page line that states it.

### 5.7 Frontend

New feature folders follow C10: `routes.tsx`, `api.ts`, `mocks.ts`, `homeWidget.tsx`, components and pages. `app/router.tsx` and `api/app.py` are not edited.

#### 5.7.1 `features/club-events/` routes and nav

- Routes: `/club-events` (`ClubEventsPage`) and `/club-events/:id` (`ClubEventPage`), both lazy, `handle: { filters: NO_FILTERS }` plus Plan 19's launch handle for key `events`.
- Nav: `{ label: 'Club events', path: '/club-events', icon: CalendarHeart, order: 25 }` (after Events at 20, before Leaderboards at 30). Not a mobile tab (the bottom bar keeps its four tabs); it is in the "More" list.
- Plan 16 page views: `PageKind` gains `'club-events'`, and the pathname mapper sends both paths to it (code only, no migration, per Plan 16 D3).

#### 5.7.2 Club events page (`/club-events`)

- Title "Club events", intro line "Club get-togethers beyond Sunday shoots. Sign up so organizers know who's coming."
- **Upcoming:** one card per event in date order. Card: title; "Sat, Oct 17 · 9:00 AM" (from `local_date` / `local_time`); spots line (§5.8); deadline line (from `deadline_local_date` / `deadline_local_time`, shown only while `state` is `open`); a "Cancelled" badge when cancelled; a chip "You're in" / "Waitlist #2" when this device holds an active registration; the whole card links to the detail page.
- **Past:** a collapsed disclosure "Past events (N)", closed by default (state kept per device in `localStorage` `sc.clubEvents.pastOpen`). Each row: title, date, "28 came" (from `signups` / `final_signups`, "came" meaning signed up and going).
- Empty upcoming: `EmptyState` "No club events coming up. Check back soon."

#### 5.7.3 Event page (`/club-events/:id`)

Top to bottom:

1. Title, date and time, a **Share** button (`lib/share.ts` image of the event card; the roster carries `data-share-exclude` so names never leave in an image) and a "Copy link" button.
2. Status banner for this device's registration, if any (§5.8).
3. **Notes** as plain text, `whitespace-pre-line`, `break-words`; no links are made clickable.
4. Facts list: spots, guests rule ("Guests welcome, up to 2 each" / "Members only, no guests"), deadline.
5. **Sign up** button (primary, full width at 390) when `state` is `open` and this device has no active registration on it. Otherwise disabled with "Sign-ups closed" (or hidden when `cancelled`, where the Cancelled banner shows instead).
6. **Who's coming** list: going rows, then a "Waitlist" sub-heading with numbered rows. Each row: name (a picked shooter's name links to `/shooters/:id`), a "+2" chip for guests, a "You" chip when this device holds the token, and a trailing **Cancel** text button (44 px tap target) while `state` is not `started` (including while the event is cancelled). Below: "12 of 20 spots taken · 3 on the waitlist".

**Sign-up sheet** (`Sheet`, bottom sheet at 390, dialog at 1440):

1. "Who are you?" search box over the shooter directory (`GET /api/shooters`, deceased removed client-side). Matching ignores case, commas and word order, so "ike had" finds "Hadley, Ike". Up to 8 results; then a fixed **"I'm not listed"** row.
2. After a pick: `signup-check` runs. `already_signed_up` → "{name} is already on the list." and the submit is disabled. `has_email` → note "We'll use the email we have for you." and no email field. Otherwise an email field.
3. After "I'm not listed": "Your first and last name" field and an email field.
4. Email field label "Your email", help "Only organizers see it. This site never sends email."
5. Guests stepper (0..`max_guests`), shown only when guests are allowed: "Bringing guests?".
6. If the event has a capacity and the waitlist is non-empty or the spots do not fit: a line "This will put you on the waitlist." before submit.
7. Submit "Sign me up". On 201: store `{ eventId, token }` under `sc.clubEvents[registrationId]`, close the sheet, show the status banner, refetch the event. When the response says `email_used: 'on_file'` but the sheet had asked for an email (the §5.9 race), the banner adds "We'll use the email already on file for {name}. To cancel, use this device or ask an organizer."
8. If the deadline passes while the sheet is open, the POST gets 409 `signups_closed`: the sheet shows "Sign-ups for this event have closed." in place of the submit button, keeps what was typed visible (nothing was saved), and refetches the event so the page shows "Sign-ups closed". The same refetch-on-409 applies to `event_cancelled` ("This event was cancelled by the organizers.") and `signups_full`.

The "Which one are you?" choice (`lib/me.ts`) pre-selects that shooter in the picker when set; the member can change it. Nothing about the sign-up is written back to `lib/me.ts`.

**Cancel:** on this device's own row (token in storage) "Cancel" opens a confirm sheet "Cancel your spot{ and 2 guests}?" → token cancel. On any other row it opens "Cancel {name}'s spot" with an email field "Type the email used for this sign-up." → email cancel. On 403 the generic message (§5.8), on 429 the rate message. On success the token is removed from storage. A stored token whose registration is no longer in the roster (cancelled elsewhere, removed, purged) is dropped on the next load.

`localStorage` is read and written through try/catch helpers in `features/club-events/tokens.ts`; with storage blocked the page works and only the same-device cancel is missing (the email path still works).

#### 5.7.4 Home "Coming up" card (`features/club-events/homeWidget.tsx`)

`{ id: 'club-events-next', order: 15, slot: 'main' }`: in the main column **after** Next Sunday (`predictions`, order 10) and before the Year in review card (`yir`, order 40). Insights is in the `hero` slot, not `main`, and is untouched. Nothing on Home moves or goes. Rendered only when `useFeature('events').visible`, and only when an upcoming non-cancelled event exists; otherwise renders nothing. Placing it after Next Sunday means that when it appears it can only push content **below** it (the YIR card, usually below the fold at 390), never the first card of the main column. To keep even that from shifting, the card's query result is kept in the TanStack cache (`staleTime: 60_000`), and on later visits the card renders at once from cache; on a first visit it appears once, after Next Sunday has already rendered above it. Content: "Coming up" title; event title; date and time; spots line; deadline line or "Sign-ups closed"; this device's chip; button "See details" (or "Sign up" when open and this device has no registration) linking to `/club-events/:id`. If an event this device signed up for was cancelled and is still upcoming, the card first shows "{title} on {date} was cancelled."

#### 5.7.5 Admin page (`features/admin-club-events/`, `/admin/club-events`)

Nav `{ label: 'Club events', path: '/admin/club-events', icon: CalendarCog, order: 915, adminOnly: true }`, `NO_FILTERS`, inside `RequireRole role="admin"`. Tabs **Events** and **Contacts**.

- **Events tab:** "New event" button; list of events (upcoming first) with going/waitlist counts and a "Cancelled" badge. Selecting one opens its editor: the form (title, date, start time, deadline date and time defaulting to 20:00 the day before, notes with a live "1,840 / 2,000" counter, capacity "Leave empty for no limit", guests toggle and max), then the roster table with columns Name, Email, Guests, Status, Signed up, Source ("List" / "New name"), and row actions Remove, Guests, Link. A "Looks like Hadley, Ike? Link" hint shows on unlinked rows with a suggestion. Above the table: **Export CSV**, **Copy emails** (going), **Cancel event** / **Restore**, **Delete**. When the waitlist head does not fit: "1 spot open; the next sign-up on the waitlist needs 3."
- **Contacts tab:** table Name, Email, Source, Last used, with Edit and Remove; an "Add email" action with a shooter picker.

At 390 the roster table becomes stacked rows (the DataTable mobile pattern) with no sideways scroll.

#### 5.7.6 About page

`PRIVACY` changes from a constant list to a list built with the launch state:

1. "No accounts. There are no logins beyond the club’s shared password." (unchanged)
2. "Browsing the site collects nothing about you: no name, no email. The site processes the club’s score sheets and analyses them." (replaces "We don’t collect your name, email or anything else about you…")
3. **New, shown when `events` is on or preview:** "If you sign up for a club event, we keep your name and the email you give us so organizers can reach you."
4. **New, same condition:** "Only organizers see emails. We never show them on the site and never send email from it. Sign-ups are deleted 30 days after the event (the nightly backups keep a copy for up to 8 more weeks); an email saved for a shooter stays for quicker sign-ups until an organizer removes it or it goes two years unused."
5. "“Which one are you?” is remembered on your device and never sent anywhere." (unchanged)
6. "Fist bumps and visit counts are anonymous. They use a random ID your browser makes up, never tied to a name. We don’t store IP addresses for any of it." → "…We don’t store IP addresses for any of it, sign-ups included."
7. "No ads, no third-party trackers." (unchanged)

### 5.8 Copy

All strings use "you", the person's name, or no pronoun. "Sunday" is never called an event.

| Where | String |
|---|---|
| Spots, capacity | "12 of 20 spots taken" · full: "Full · 3 on the waitlist" · no waitlist yet when full: "Full · join the waitlist" |
| Spots, no capacity | "14 going" (1: "1 going") |
| Deadline | "Sign up by Fri, Oct 16, 8:00 PM" · after: "Sign-ups closed" |
| Started | "Happening now" until local midnight |
| Cancelled badge / banner | "Cancelled" / "This event was cancelled by the organizers." |
| Status banner, going | "You're in. See you there!" (with guests: "You're in, plus 2 guests. See you there!") |
| Status banner, waitlist | "You're on the waitlist: #3. If a spot opens, you move up automatically." |
| Promoted (stored token now going, was waitlist on this device) | "Good news: a spot opened and you're in." |
| Picker | "Who are you?" · "Search your name" · "I'm not listed" |
| Email on file | "We'll use the email we have for you." · after the race (`email_used: 'on_file'` when an email was typed): "We'll use the email already on file for {name}. To cancel, use this device or ask an organizer." |
| Switch off mid-sign-up (404) | "Club events aren't available right now. Nothing was saved." |
| `pick_or_type` / `token_or_email` | "Pick a name from the list, or choose I'm not listed." / "Send the sign-up's token or an email, not both." |
| Started move refused | "This event has already started, so its date can't change." |
| Email help | "Only organizers see it. This site never sends email." |
| Guests | "Bringing guests?" · "Guests welcome, up to 2 each" · "Members only, no guests" |
| Waitlist warning | "This will put you on the waitlist." |
| Submit | "Sign me up" |
| Cancel own | "Cancel my spot" · confirm "Cancel your spot and 2 guests?" |
| Cancel other | "Cancel {name}'s spot" · "Type the email used for this sign-up." |
| Cancel mismatch (403) | "That email doesn't match this sign-up. Check it and try again." |
| Rate limited (429) | "Too many tries from here. Wait a bit and try again." |
| Errors | `name_on_list`: "That name is already on the shooter list. Pick it from the list instead." · `name_needs_last`: "Add your last name too, so organizers know who you are." · `already_signed_up`: "{name} is already on the list." · `signups_closed`: "Sign-ups for this event have closed." · `event_started`: "This event has started. Ask an organizer to change the list." · `bad_email`: "Enter an email like name@example.com." |
| Roster empty | "No one has signed up yet. Be the first." |
| Purged past event | "The sign-up list was cleared 30 days after the event." |
| Home card title | "Coming up" |

A Vitest copy lint (as `insights` lints do) scans `features/club-events/**` and `features/admin-club-events/**` strings for `\b(he|she|his|her|him|hers|himself|herself)\b` and fails on a match.

### 5.9 Edge cases

| Case | Behaviour |
|---|---|
| Two people take the last spot at once | Row lock serialises; the second is waitlisted (or refused if closed). Integration test proves a blocked second session. |
| Same shooter signs up twice at once | Lock + `uq_…_shooter`; the second gets 409 `already_signed_up`. |
| Cancel and sign-up race | Lock; promotion sees the committed cancel. |
| Waitlist head needs 3, 1 spot opens | Nobody promoted (D9); admin hint shown. |
| Capacity raised from 20 to 25 | Promotions run in the same request; promoted members see the "Good news" banner on next load. |
| Capacity set to empty | Whole waitlist promoted. |
| Capacity lowered below going | 409 `capacity_below_going`. |
| Event cancelled | Sign-ups refused (409 `event_cancelled`); the page shows the "Cancelled" banner **above the roster, which stays visible** with its per-name Cancel buttons; registrations untouched so Restore brings everyone back; member cancels (token and email) still allowed until start; no promotions while cancelled. |
| Event deleted | Cascade; stored tokens dropped on next load (404 → remove). |
| Start time moved earlier than the deadline | 400 `deadline_after_start`; the form moves the deadline with the start by default. |
| Deadline passed, someone cancels | Allowed until start; waitlist promotes until start. |
| Event started | Viewer cancel 409; no promotions; organizer can still remove. |
| Shooter merged after signing up | Displayed and de-duplicated by the canonical shooter (§5.3.8). |
| Shooter renamed | Roster shows the new display name (it is read live). |
| Picked shooter has no email; two devices race | First email wins (`ON CONFLICT DO NOTHING`); second registration stands, its typed email is discarded, response `email_used: 'on_file'`, and the sheet says so (§5.7.3 step 7), because the email that person just typed will not cancel the sign-up. |
| Deadline passes while the sheet is open | 409 `signups_closed`; sheet message, nothing saved, event refetched (§5.7.3 step 8). |
| Device in another time zone (UTC, Tokyo) | Every date, time and state shown is the server's club-time value (D21). |
| Event at 23:30 LA | Upcoming and "Happening now" until LA midnight, although it is already the next day in UTC; purge counted from the instant (§5.6). |
| PATCH notes on a past event | Accepted; the start is re-validated only when it changes (§5.3.11). |
| PATCH start of a started or purged event | 409 `event_started`. |
| Typed name of a profile-less or deceased shooter | Accepted as a typed name (that shooter cannot be picked either, §5.3.5). |
| Someone types 5 wrong emails on another's sign-up | That registration's email cancel 429s for the hour; the token path still works; an organizer can remove it or reset the counter. Accepted risk (§5.3.7). |
| Crawler UA on `/club-events/1` | Plan 19 serves the generic club preview; no title, date or name (D24). |
| Postgres CHECK violation during a write | 500 `internal`; the log line has the class and constraint name only (D22). |
| Someone else's name picked to grab their contact | The email on file is never shown; a first-time email from an impostor is visible to organizers with source `signup` and can be fixed in Contacts; the real person can still sign up only once per event (organizer resolves). Accepted risk inside the password gate. |
| Typed name equals a listed shooter | 409 `name_on_list`. |
| Typed one-word name | 400 `name_needs_last`. |
| Notes with `<script>` or Markdown | Shown literally as text. |
| Spring-forward local time 02:30 | 400 `bad_local_time`, "That time doesn't exist on that day (clocks spring forward)." |
| localStorage blocked | No same-device cancel; email cancel works; page renders. |
| Token of a purged or removed registration | Dropped from storage silently. |
| CSV cell `=HYPERLINK(...)` in a name | Exported as `'=HYPERLINK(...)`. |
| Switch flipped off while a member has the page open | Next request 404s; the page shows the not-found state; stored tokens are kept for when it returns. Mid-sign-up: §5.1 (nothing written, sheet message). |
| Admin session signs up | Allowed; admins are members too. Not counted differently. |
| 500 during sign-up | Generic `internal`; logs path and method only (existing handler), never the body. |

---

## 6. Privacy

1. **What is stored.** For a typed name: the name, the email, guests count, times and status, on the registration. For a picked shooter: the shooter id on the registration, and the email once in `shooter_contacts`. A token hash (not the token). Rate-limit rows with an HMAC fingerprint, never an IP.
2. **Who sees it.** Viewers: names, guest counts, order and status of active registrations, and one boolean per shooter (`has_email`) from `signup-check`. That boolean does reveal, shooter by shooter, whether an email is on file (never the address); it is the owner's form requirement, recorded as an accepted exception in D11 and bounded by the `check` limit. Organizers: everything, including emails, through admin routes only, and each admin read that shows emails is audited (§5.5). Emails never appear in any viewer route, never in an insight, never in page-view data, never in an image share (roster excluded), never in `audit_log` details; names never appear in `audit_log` details either.
3. **Never logged.** No route logs a request body or an email. The unhandled-error handler's `exc_info` traceback is the one place a database error could carry an email (a CHECK violation's `Failing row contains (…)` and SQLAlchemy's `[parameters: …]`), so D22 applies: `hide_parameters=True` on the engine, `scrub_db_errors()` re-raising `DBAPIError` as a plain `DomainError` from `None` in every club-event and contact write (link included), domain validation before every write, and `log_error_verbosity = terse` on the database so the Postgres server log drops `DETAIL`. Request fields are unconstrained and validated in the domain, so FastAPI's 422 body cannot echo an email (§5.3.6). A backend test signs up, cancels, exports, forces each domain error path, **and forces a real CHECK violation (`ck_…_inactive_scrubbed`, by bypassing the domain check with a monkeypatched validator) and a real unique violation (`uq_club_event_registrations_name`, by bypassing the duplicate pre-check)** with `caplog` at DEBUG, and asserts no captured record, message or formatted traceback contains the test email or `@example.com`. Caddy and cloudflared keep access logs off (Plan 16); this plan adds nothing that logs requests.
4. **No IPs.** `club_event_attempts.ip` stores `ip_fingerprint(request)`. `audit_log.ip` stays the owner's raw admin trail (existing rule, admin actions only).
5. **Deletion.** Cancel and organizer removal scrub email and token immediately. The daily job deletes every registration of an event 30 days after its start (keeping only the two counts `final_signups` and `final_spots`) and contacts unused for 730 days. Audit rows identify registrations by id only, so they keep no name or email past the purge. Deleting an event deletes its registrations at once. An organizer can delete any shooter contact at any time.
6. **No outbound email,** no third parties, no new external request; the CSP is unchanged (all calls same-origin).
7. **Backups.** The existing nightly Postgres backup includes these tables, so a purged sign-up or contact survives in backups for the rotation period in `deploy/README.md`: daily dumps for 14 days and weekly dumps for 8 weeks, so at most about 8 weeks past the purge. The About bullet says so ("the nightly backups keep a copy for up to 8 more weeks").

---

## 7. Testing strategy

Strict TDD with evidence (RED then GREEN pasted per step; reviewers re-run new tests on the base to prove they fail). Coverage floor 90% lines and branches, backend and frontend separately. Test names below are binding where given.

### 7.1 Unit (backend, no DB)

- `admit` and `promotions`: empty queue; exact fit; one over; waitlist non-empty blocks a fitting newcomer (`test_newcomer_never_jumps_the_waitlist`); head too big stops promotion even when a later party fits (`test_promotion_stops_at_first_party_that_does_not_fit`); `capacity=None` promotes all; queue order is by `id` even when a later `id` has an earlier `queue_at` (`test_queue_orders_by_id_not_queue_at`; kills "order by time").
- `signup_key`: "Ike Hadley" == "Hadley, Ike" == " hadley  IKE "; idempotent. `listed_keys` word-sorts alias keys (an alias `hadley ike` blocks "Ike Hadley").
- Email normalisation and validation: case, whitespace, NFKC; rejects `a@b`, `a b@c.de`, 255 chars; accepts `ü@x.de`.
- Email match (D11): `test_email_match_non_ascii` (stored `ü@x.de`, typed `Ü@x.de` matches; typed `ü@x.de` against stored `u@x.de` is a plain mismatch, no `TypeError`); `test_email_match_nothing_stored` (stored `None` and stored `""` both compare against the dummy and return `False`); a lone-surrogate token (`"\ud800"`) is a mismatch, not a 500.
- Local time: `2026-03-08T02:30` refused; `2026-11-01T01:30` maps to the PDT instant (fold 0).
- `csv_safe`: prefixes `= + - @`, `\t`, `\r`, and `"  =1+1"` / `"\t-2"` (whitespace then a trigger); leaves `Ike`, `1-2`, `a=b` alone.
- `similar_name_keys` called with empty date sets suggests "Hadley, Ike" for "Ike Hadly".
- Copy lint for pronouns over the backend error messages.

### 7.2 Integration (backend, real Postgres)

- Migration `0010_club_events` upgrades from `0009` and downgrades cleanly; `test_migration_chain_is_linear` (one Alembic head); CHECKs reject bad rows (guests 11, `max_guests` with guests off, an inactive row with an email).
- Launch gate: with `events` off, every viewer route answers 404 to a viewer and is served to an admin; the 404 happens before a rate-limit row is written (`test_gated_signup_leaves_no_attempt_row`).
- Sign-up happy paths for picked-with-email, picked-without-email (contact created, source `signup`), typed name; `email_used` values; token returned once and only its hash stored.
- Duplicate rules: same shooter; same typed key in the other word order; typed name equal to a live shooter's renamed display name, to an alias in the other word order, and to an `alias_name` rule key; merged source and target treated as one. `test_profileless_shooter_name_can_be_typed`: a shooter in `shooters` and `shooter_aliases` with no `shooter_profiles` row is absent from the picker, and typing that name succeeds (201), as does a deceased shooter's name.
- Display names: a renamed shooter's roster name is the profile `display_name`; a linked shooter whose profile row goes away falls back to `shooters.display_name`.
- Bodies: `pick_or_type` is a 400 (not 422) for both and neither; a 300-character email is 400 `bad_email` with no `input` echo; cancel with both or neither of token/email is 400 `token_or_email`.
- Time zone: `test_late_evening_event_stays_upcoming` (an event at 23:30 LA, frozen server clock at 23:45 LA = 06:45Z next day: listed in `upcoming` with `state: 'started'`; at 00:01 LA it is in `past`); `deadline_local_date` / `deadline_local_time` are club time; `test_purge_counts_from_starts_at` (the §5.6 example: kept by the Nov 16 run, purged by the Nov 17 run).
- PATCH: notes on a past event accepted; start of a started event 409 `event_started`; start of a purged event 409; a deadline moved into the past makes `state` `closed` at once; moving the start keeps the waitlist order.
- Capacity: guests count toward spots; waitlist position; promotion after cancel, removal, guest decrease, capacity increase, capacity cleared, restore; no promotion after start or while cancelled; capacity below going refused.
- **Concurrency:** `test_last_spot_race_never_overbooks`: two sessions sign up for the last spot; the test waits until the second session is blocked on the event row lock (polling `pg_locks`), then commits the first; asserts one `going`, one `waitlist`. Without the `FOR UPDATE` the test fails every time, not sometimes (Plan 16 pattern). Same shape for cancel-vs-signup. `test_queue_order_follows_lock_order`: session A begins its transaction first (so its `now()` is earlier) but is held before the lock; session B begins later, takes the lock, signs up and commits; then A proceeds. With capacity 1, B is `going` and A is `waitlist`, and A's `id` and `queue_at` are both greater than B's. Ordering by a transaction-start `queue_at` fails this test.
- Cancel: token right/wrong; email right (registration email, contact email, case-different) / wrong / no email on file; all failures identical in status, code and message (`test_cancel_failures_are_indistinguishable`); per-fingerprint and per-registration limits; a registration at its limit refuses even the right email; `test_token_cancel_ignores_registration_fail_limit` (five wrong emails from five fingerprints, then the right token cancels, 200); organizer remove and `reset-cancel-limit` work at the limit, and after a reset the right email cancels; a non-ASCII stored email cancels with its typed form (no 500); cancel works on a cancelled (not started) event; cancel scrubs email and token; signup limit 100 per hour and check limit 60 per 10 minutes at their boundaries; inserts prune `club_event_attempts` older than a day.
- Viewer responses never contain an email: every viewer endpoint's JSON, after seeding emails, is searched for `@` (`test_no_viewer_response_contains_an_email`).
- Logs: `test_db_errors_never_log_an_email`, the `caplog` test from §6.3, including the forced CHECK and unique violations; plus `make_engine(...)` has `hide_parameters` set.
- ETag: `/api/club-events` (the root list path, no trailing slash), `/api/club-events/{id}` and `/signup-check` are `no-store` with no `ETag`.
- Admin: every mutation, the roster read and the contacts read write exactly one audit row with the listed action; `test_audit_details_never_hold_a_name_or_email` seeds typed and picked names, runs every admin action, and asserts no `details` value contains either name, any `@`, or a `name` key; CSV headers, filename, escaping and order; `emails` endpoint audited; link moves the email (`email_moved: true`) or, when the shooter already has a contact, deletes it (`email_discarded: true`); link refuses a double link; contacts CRUD.
- Retention job: an event 31 days old is purged (every registration gone, counts snapshotted); 29 days old untouched; two due events are locked in `id` order; contact at 731 days unused deleted, 729 kept, recently used kept; attempts older than a day pruned; scheduler enqueues it once per local day after 03:00 with weather off.

### 7.3 Frontend (Vitest, Testing Library, MSW)

- Picker matching ("ike had" finds "Hadley, Ike"; deceased hidden; "I'm not listed" always present).
- `signup-check` drives the form: "We'll use the email we have for you." with no email field; email field otherwise; already-signed-up disables submit.
- Waitlist warning shown exactly when the server would waitlist (same `admit` rule mirrored in `features/club-events/spots.ts`, with a shared fixture table tested on both sides).
- Token storage: written on 201, used for "Cancel my spot", dropped when the registration is missing; all paths work with `localStorage` throwing.
- Notes render `<b>x</b>` literally and keep line breaks.
- Launch states: `off` + viewer renders nothing (nav, Home card, About bullets 3–4); `preview` + admin shows the badge; `on` shows all.
- About page renders the new bullets 2 and 6 always, 3 and 4 only when visible.
- `test_home_widget_after_next_sunday` (in `features/home/widgets.test.ts`): the `main` slot order is `predictions` (10), `club-events-next` (15), `yir` (40); insights stays in `hero`. The card renders nothing with no upcoming event, and while its query is pending the Next Sunday card's `getBoundingClientRect().top` is the same before and after the club-events data resolves (no shift of anything above it).
- Time zone: the event card, page and Home card tests run under `TZ=UTC` and `TZ=Asia/Tokyo` (two Vitest runs of `features/club-events/**` via the `test:tz` script, both in CI); a fixture event at `2026-10-17` 23:30 club time (`2026-10-18T06:30Z`) shows "Sat, Oct 17 · 11:30 PM" and "Sign up by Fri, Oct 16, 8:00 PM" in both, and open / closed / started follow `state` only (a fixture with `state: 'open'` and a deadline in the device's past still shows the Sign up button).
- Sheet: `signups_closed` 409 shows the closed message and refetches; a 404 mid-sign-up shows "Club events aren't available right now. Nothing was saved."; `email_used: 'on_file'` after a typed email shows the on-file line.
- Cancelled event: banner above a visible roster with Cancel buttons.
- Admin page: form validation messages, capacity-below-going error, roster stacked layout at 390, CSV and Copy emails buttons call their endpoints.
- Pronoun copy lint over both feature folders.

### 7.4 End to end (Playwright, 390×844 and 1440×900)

- **`e2e/club-events.spec.ts`** (read-only projects, both viewports): with the default switch state (off), a viewer sees no "Club events" nav item, `/club-events` shows the not-found page, `GET /api/club-events` is 404, Home has no "Coming up" card, About has neither new sign-up bullet; no sideways scroll.
- **`e2e/club-events.crawler.spec.ts`** (read-only, request-level, no cookie): `GET /club-events/1` with `User-Agent: facebookexternalhit/1.1` returns the Plan 19 generic preview HTML (`og:title` "Sunday Clays · Tri-County Gun Club" and the generic description), and the body contains no event title and no name; `GET /api/club-events` with the same UA and no cookie is 401 `unauthenticated` (Caddy's crawler matcher excludes `/api/*`, and `require_viewer` runs before the gate). The review asked for the login page here; with Plan 19 merged a crawler gets the generic preview instead (D25).
- **`e2e/club-events.admin-mutations.spec.ts`** (the `admin-mutations` project; loops over both viewports with `page.setViewportSize`, as `special-events.admin-mutations.spec.ts` does; viewer pages in fresh contexts with `VIEWER_STATE`):
  1. Admin opens `/club-events` with the switch off: page and "Admin preview" badge visible.
  2. Admin creates "Fall Fun Shoot" (capacity 2, guests on, max 1) in `/admin/club-events`, starting **14 days after the test's today at 10:00 club time** (computed in the spec with `Intl.DateTimeFormat` in `America/Los_Angeles`, never a fixed date), with the default deadline, then turns `events` on in the Features page.
  3. Viewer A: Home shows "Coming up · Fall Fun Shoot"; signs up as "Hadley, Ike" with `ike.hadley@example.com` and +1 → "You're in, plus 1 guest."
  4. Viewer B: "I'm not listed" → "Dana Quill", `dana.quill@example.com` → "You're on the waitlist: #1."
  5. Viewer C: "I'm not listed" → "Ike Hadley" → "That name is already on the shooter list…".
  6. Viewer A: "Cancel my spot" → B's page reload shows "Good news: a spot opened and you're in."
  7. Viewer C: Cancel next to "Dana Quill" with `wrong@example.com` → generic mismatch; with `dana.quill@example.com` → cancelled.
  8. Every viewer API response captured in the run contains no `@`.
  9. Admin roster shows both emails; Export CSV downloads a file whose header row matches §5.5; the audit list on the Ops page shows the export.
  10. `expectNoSideScroll` on every page at both sizes.
  11. Home position: at both sizes the "Coming up" card is below the Next Sunday card in the main column (bounding boxes), and the Next Sunday card's top does not move between first paint and the club-events response.
  - `test.beforeEach` and `test.afterEach`, each on a fresh admin request context: delete every club event titled "Fall Fun Shoot", `DELETE /api/admin/shooter-contacts/{hadleyId}` (a 404 is fine), and set the switch to off. The `beforeEach` copy covers a run that died mid-way, which would otherwise leave Hadley's contact behind and turn step 3 into "We'll use the email we have for you."
- `compose.test.yaml` sets `CLUB_EVENT_SIGNUP_LIMIT=1000` and `CLUB_EVENT_CHECK_LIMIT=100000` (one IP runs the whole suite), as it already raises `PAGE_VIEW_LIMIT`.

---

## 8. Out of scope

- Sending any email or SMS (confirmations, reminders, waitlist notices, "event cancelled" notices).
- Payments, ticketing, QR check-in, or recording who actually attended.
- Named guests, per-guest details, dietary or shirt-size questions, custom form fields.
- Member self-service edits (changing guests or name after signing up; members cancel and sign up again, losing their place).
- Recurring events, calendar (ICS) export, maps or location fields (the location goes in notes).
- Linking a club event to a Sunday, to scores, to ScoreChaser, to insights, trophies or page analytics beyond the `club-events` page kind.
- Creating shooters from registrations, or overlay rules for registrants.
- Charts or reports about club events (any later chart follows ChartFrame and the header window, D12).
- Multiple organizer roles or per-event organizers: every admin is an organizer.
- Public (outside the password) event pages or share links that bypass the gate.
