# The Sunday Sheet: design

Status: approved in brainstorming, 2026-09-30. Branch: `feat/sunday-sheet` (integration branch; see "Delivery").

## Why

The site is rich but overwhelming on first visit, and it doesn't feel social. Every week the club emails the
results PDF. From now on the email also carries a link to the site.

That link should land on something that:

- reads like a club newspaper crossed with a social feed;
- needs no logins and no user-generated content;
- is easy to take in at a glance;
- gets people acquainted with the site by letting them follow stories into it.

## Goals and non-goals

**Goals**

- **One Sheet per Sunday.** A per-Sunday page, "The Sunday Sheet", becomes the site's front door at `/`.
- **Feed layout.** An edition-style top (masthead, four numbers, headline) sits over a feed of posts about the
  day and its people.
- **Nothing lost from Home.** Every chart, insight and card on today's Home finds a place on the Sheet. Every
  chart keeps its Table, CSV, fullscreen and explainer.
- **A personal hook without logins.** "Which one are you?" is picked once and remembered on the device.
- **A light social layer.** Anonymous 🤜🤛 fist bumps per post (one per device), plus Share-as-image.
- **Learning is organic.** Every post has "See why →" into its chart, and every name links to the shooter's
  profile.

**Non-goals**

- Logins, comments, follows, or any user-written text.
- Tips cards, tours or guides. The owner chose organic learning.
- A "Next Sunday" or tips post in the feed. Next Sunday stays in the rail.
- Removing the password gate or the Cloudflare gate.
- Server-rendered link-preview images; the site is password-gated.
- Frozen or immutable issues. A past Sheet reflects the current data, so corrections show up.

## Owner rules (unchanged, binding)

- Named-shooter posts are positive or neutral only. Negatives appear only at the club or field level.
- No skill-rating ranking and no rivals or head-to-head. Improvement is called out instead.
- App copy never uses he/she/his/her.
- Real people's names never appear in the repo. Tests and docs use the invented names.
- The spreadsheet score is authoritative.

## Page structure

### Routes

- `/` renders the Sheet for the latest scored Sunday.
- `/sheet/:date` renders any Sunday's issue.
- "All issues" links to the existing events calendar.
- The old Home route is retired; `/` is the Sheet.

### Order

The desktop layout puts the main column beside the right rail, at ≥1024 px. On phones everything stacks in
this order:

1. **Masthead.** "THE SUNDAY SHEET", the date, and "issue N" (the count of held Sundays up to and including this
   one). It has previous and next issue links and an "All issues" link.
2. **Four numbers.** Shooters, field median, top score, and trophies earned that Sunday. These come from today's
   Latest Sunday card.
3. **Your Sunday (rail).** Today's Your panel (last result, recent moves, odometer) and Your next trophy. With no
   "me" set, this slot shows "Which one are you?" (see below).
4. **Headline.** From today's Top story, with the "Last Sunday" recap text as its deck.
5. **Spotlight.** The featured insight with its chart, from today's Insights card spotlight.
6. **The feed.** Post types ①–⑥ (below), about 8–12 posts, interleaved by type.
7. **More from this Sunday ▾.** Collapsed. The remaining posts of the Sunday, grouped by family.
8. **Next Sunday (rail).** Today's predictions card: forecast and expected field median.
9. **Club pulse (rail).** Today's Club pulse stats and the Turnout per Sunday chart.
10. **Latest Sunday details (rail).** A link to the full event page.

### Behaviour

- **Loading.** Placeholders reserve each block's space while it loads, as the home layout-shift fix does.
- **Time window.** The Sheet is a single Sunday. The header time window does not apply, so the filter bar shows
  no date control and the cards say "not affected by the time filter".

## Posts

A post is one feed item, with a stable `post_key`.

| Type | Source | `post_key` |
|---|---|---|
| ① PBs and milestones | Insights anchored on the Sunday: `pf.pb`, `pf.season-best`, `pf.career-first`, `pf.first-since`, `pf.sunday-milestone`, `pf.targets-milestone`, `pf.average-milestone`, `pf.first-tier`, `pf.shooter-anniversary`, `ev.top-score`, `rec.*` | the insight `key` |
| ② Improvement | `pf.hot-form`, `pf.rank-climb` (rating gain), `pf.up-on-usual`, `pf.beat-own-usual`, `pf.three-rising`, `pf.year-up`, `lb.most-improved`, `lb.biggest-climb` | the insight `key` |
| ③ Trophies unlocked | That Sunday's `achievements_awarded`, one post per trophy (with its art) listing everyone who earned it | `trophy:{code}:{date}` |
| ④ Course and weather | `ev.how-it-played`, `ev.toughest-since`, `ev.rain-day`, `ev.week-jump` | the insight `key` |
| ⑤ Welcomes | `ev.new-faces`, `ev.second-visit`, and `pf.back-strong` (a return after a break) | the insight `key` |
| ⑥ On this day | The existing "on this day" data (1, 2 and 3 years back) | `otd:{date}:{years_ago}` |

- **Feed order.** The existing insight `rank_score` orders posts, interleaved so that no type appears more than
  twice in a row.
- **"More from this Sunday".** It holds insights of other kinds and posts past the feed cap. They are still
  bumpable.

A post carries:

- its type;
- its headline (the existing insight headline, or a template for trophy and on-this-day posts);
- the named shooter IDs, rendered as profile links;
- `see_why`: the insight chart link and target. A trophy post links to the Trophy Room entry, and an
  on-this-day post links to that Sunday's event page;
- `bumps` (a count) and `bumped` (whether this device has bumped it).

## API

### `GET /api/sheet/{date}` and `GET /api/sheet/latest`

Viewer only. The response has:

- `masthead`: the date, the issue number, and the previous and next dates.
- `numbers`: the four numbers above.
- `headline`, `recap` and `spotlight`.
- `posts`: the feed, in order.
- `more`: the remaining posts, grouped by family.

**Caching.** The body is cached by `data_version`, like the other reads.

**Bump counts are not in the cached body.** The client fetches them from
`GET /api/sheet/{date}/bumps?device_id=` (not cached), which returns `{post_key: {bumps, bumped}}`.

### `POST /api/sheet/bumps` and `DELETE /api/sheet/bumps`

Viewer only. The body is `{post_key, device_id}`. Both calls are idempotent, and both return the new
`{bumps, bumped}`.

The request is refused when:

- `device_id` is not a UUID (400);
- `post_key` does not resolve to a current post (404);
- the IP is over the rate limit (429).

### `DELETE /api/admin/sheet/bumps/{post_key}`

Admin only. Wipes every bump on one post, is audited, and is exposed on the admin ops page.

## Data

- **Table.** A new table `fist_bumps(post_key text, device_id uuid, created_at timestamptz, primary key
  (post_key, device_id))`, created in a new migration.
- **Durable.** The table is never truncated by a rebuild, like `rules` and `audit_log`.
- **Stale keys.** A bump on a post that later stops existing (after a data correction) is kept but not shown.
- **Rate limit.** 120 bump actions per client IP per 10 minutes, using the existing `client_ip` helper. The
  counting table is `bump_attempts`, pruned inline like `login_attempts`.

## Device identity and "Which one are you?"

**Device ID**

- `lib/device.ts` creates a random UUID once and keeps it in localStorage. It is never tied to a name and is
  sent only with bumps.
- If localStorage is unavailable, the bump buttons show counts but are disabled, with the text "Bumps need this
  browser to remember you".

**"Which one are you?"**

- With no "me" set, the Your Sunday slot shows the question card. It has a name search and a "Not a shooter /
  skip" option.
- Picking yourself uses the existing `lib/me.ts` and fills the card.
- Skip hides the card on that device.
- "Not me" (existing) clears the choice.
- There is no modal or tour.

**Fist bump UI (🤜🤛)**

- A tap updates the count immediately. On error it rolls back, with "Couldn't send that bump".
- Tapping again takes the bump back.
- Nobody is ever shown who bumped.
- You can bump posts about yourself.

## Sharing and "See why"

- **Post Share.** Uses `lib/share.ts` (html-to-image, then the Web Share API, or a download). The image is a
  branded card: a masthead strip, the post headline and the chart snippet when there is one.
- **"Share this Sheet".** Shares the `/sheet/{date}` link, with the four numbers as text. The site stays behind
  its password and Cloudflare gate, so there are no preview images.
- **"See why →".** Reuses the existing insight chart-target mechanism: the target page opens, scrolls to the
  chart and rings the row or bar.

## Where every current Home piece goes

| Today on Home | On the Sheet |
|---|---|
| Latest Sunday card (stats) | The four numbers, plus a "Latest Sunday details" rail link |
| "Last Sunday" recap | The headline's deck |
| Top story | The headline |
| Insights card: spotlight | Spotlight |
| Insights card: top, kudos, more insights | Feed posts ①–⑥ and "More from this Sunday" |
| Club pulse and Turnout per Sunday chart | Rail: Club pulse |
| Next Sunday (predictions) | Rail: Next Sunday |
| On this day | Feed post type ⑥ |
| Your panel | Rail: Your Sunday |
| Your next trophy | Rail: Your Sunday |

The home widget registry (`homeWidget.tsx` in each feature) is re-pointed to Sheet slots:

- `hero` → headline and spotlight;
- `main` → the feed and rail cards;
- `me` → Your Sunday.

So the features keep owning their components.

## Testing

**Backend**

- Sheet assembly on the fixture world (Sunday 2026-09-27): the type mapping, interleaving, the feed cap, and
  "more" grouping.
- Every `post_key` resolves.
- Named-shooter posts are positive only.
- Issue numbering and the previous and next dates.
- Bump behaviour:
  - idempotent POST and DELETE;
  - refusal of an unknown key;
  - the UUID check;
  - the rate limit (429);
  - the admin wipe, with its audit entry;
  - bumps survive a rebuild and recompute;
  - counts are never served from the cached body.

**Frontend**

- The Sheet's loading, empty and error states.
- The phone stacking order.
- Optimistic bumps, with rollback.
- Bumps disabled when localStorage is blocked.
- The "Which one are you?" flow (pick, skip, "Not me").
- Every chart on the Sheet exposes Table and CSV.
- Every former Home chart is present.

**e2e (both viewports)**

- `/` shows the Sheet, with no layout shift after load.
- Previous and next issue navigation.
- A bump increments and reverts.
- "See why" rings its chart.
- Share produces a download on desktop.

## Delivery

- **Integration branch.** All task PRs target `feat/sunday-sheet`, not `main`. CI runs on each PR. The
  deployer ignores the branch, because it only watches `main`.
- **Owner preview.** Before anything replaces Home, the owner previews the branch locally: the compose stack
  from the branch, with a copy of the production database.
- **Going live.** One final PR from `feat/sunday-sheet` to `main` puts it live, and only on the owner's say-so.
- **Order of work.**
  1. Sheet API and fist-bump store.
  2. Sheet page and rail.
  3. Move Home's components onto the Sheet and retire the Home route.
  4. Share and See why.
  5. The full e2e pass.
  6. The owner preview.
