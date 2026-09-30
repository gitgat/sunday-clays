import type { Page } from '@playwright/test';

import { expect, test } from './fixtures';
import { expectNoSideScroll, expectTapTargets } from './layout';

/** Every date and number below is read from the API at run time: no wall clock, no member names. */

const EIGHT_WEEK_DAYS = 56;

function daysBack(iso: string, days: number): string {
  const [y = 0, m = 1, d = 1] = iso.split('-').map(Number);
  const t = new Date(Date.UTC(y, m - 1, d - days));
  return t.toISOString().slice(0, 10);
}

async function lastScoreDate(page: Page): Promise<string> {
  const meta = (await (await page.request.get('/api/meta')).json()) as {
    last_score_date: string | null;
  };
  expect(meta.last_score_date).not.toBeNull();
  return meta.last_score_date as string;
}

async function busiestShooter(page: Page) {
  const listed = (await (await page.request.get('/api/shooters')).json()) as {
    shooter_id: number;
    display_name: string;
    status: string;
    n_rounds: number;
  }[];
  const living = listed.filter((s) => s.status !== 'deceased');
  return living.reduce((a, b) => (b.n_rounds > a.n_rounds ? b : a));
}

const count = (n: number) => n.toLocaleString('en-US');

test('the club headline numbers follow the window, tagged with its dates', async ({ page }) => {
  const last = await lastScoreDate(page);
  const since = daysBack(last, EIGHT_WEEK_DAYS - 1);
  const windowed = (await (
    await page.request.get(`/api/club/summary?since=${since}&as_of=${last}`)
  ).json()) as { n_rounds: number; clays_broken: number };
  const lifetime = (await (await page.request.get('/api/club/summary')).json()) as {
    n_rounds: number;
  };

  await page.goto('/club');
  await expect(page.getByText(/^Last 8 weeks · /, { exact: false }).first()).toBeVisible();
  // The Rounds tile (the third stat) holds the windowed count.
  const tile = page.locator('header').filter({ has: page.getByRole('heading', { name: 'Club' }) });
  await expect(tile).toContainText(count(windowed.n_rounds));
  await expect(tile).toContainText(count(windowed.clays_broken));
  await expectNoSideScroll(page);

  await page.goto('/club?w=all');
  await expect(page.getByText(/^All time · through /).first()).toBeVisible();
  await expect(tile).toContainText(count(lifetime.n_rounds));
  await expectNoSideScroll(page);
});

test('the year-by-year charts sit under a heading that says the window does not apply', async ({
  page,
}) => {
  await page.goto('/club');
  const heading = page.getByRole('heading', {
    level: 2,
    name: "Year by year (every year; the time window doesn't apply)",
  });
  await expect(heading).toBeVisible();
  const section = page.locator('section').filter({ has: heading });
  await expect(section.getByRole('region', { name: 'Newcomers per year' })).toBeVisible({
    timeout: 15_000,
  });
  await expect(section.getByRole('region', { name: 'First rounds' })).toHaveCount(0);
  await expectNoSideScroll(page);
});

test('regulars are labelled with their fixed periods and cap at 8 names', async ({ page }) => {
  const regulars = (await (await page.request.get('/api/club/regulars')).json()) as {
    core: unknown[];
  };
  await page.goto('/club');
  const core = page.getByRole('region', { name: 'Core regulars' });
  await expect(core.getByText(/^Last 12 months · to /)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole('region', { name: 'Lapsed regulars' })).toContainText(
    /Last 90 days · to /,
  );
  const toggle = core.getByRole('button', { name: `Show all ${String(regulars.core.length)}` });
  if (regulars.core.length > 8) {
    await expect(core.getByRole('link')).toHaveCount(8);
    const box = await toggle.boundingBox();
    expect(box?.height).toBeGreaterThanOrEqual(44);
    await toggle.click();
    await expect(core.getByRole('link')).toHaveCount(regulars.core.length);
  } else {
    await expect(toggle).toHaveCount(0);
  }
  await expectNoSideScroll(page);
  await expectTapTargets(page);
});

test('the profile shows the window row above the lifetime numbers', async ({ page }) => {
  const last = await lastScoreDate(page);
  const since = daysBack(last, EIGHT_WEEK_DAYS - 1);
  const shooter = await busiestShooter(page);
  const detail = (await (
    await page.request.get(`/api/shooters/${shooter.shooter_id}?since=${since}&as_of=${last}`)
  ).json()) as {
    window_stats: { n_rounds: number; avg_score: number | null };
    stats: { n_rounds: number };
  };

  // The page asks for lifetime numbers at once and re-asks with the window once /api/meta answers.
  const asked = page.waitForRequest((r) => {
    const url = new URL(r.url());
    return (
      url.pathname === `/api/shooters/${String(shooter.shooter_id)}` &&
      url.searchParams.has('since')
    );
  });
  await page.goto(`/shooters/${shooter.shooter_id}`);
  const params = new URL((await asked).url()).searchParams;
  expect(params.get('since')).toBe(since);
  expect(params.get('as_of')).toBe(last);

  const hero = page.locator('header').filter({ has: page.getByRole('heading', { level: 1 }) });
  await expect(hero.getByRole('heading', { name: /^In the last 8 weeks/ })).toBeVisible();
  await expect(hero.getByRole('heading', { name: 'Lifetime' })).toBeVisible();
  if (detail.window_stats.n_rounds === 0) {
    await expect(hero.getByText(/^No rounds in the last 8 weeks/)).toBeVisible();
  } else {
    await expect(hero.getByText(`${String(detail.window_stats.n_rounds)}`).first()).toBeVisible();
  }
  await expect(hero).toContainText(String(detail.stats.n_rounds));
  await expectNoSideScroll(page);
});

test('the profile splits ask for the window and the calendar opens on its end year', async ({
  page,
}) => {
  const shooter = await busiestShooter(page);
  const rounds = (await (
    await page.request.get(`/api/shooters/${shooter.shooter_id}/rounds`)
  ).json()) as {
    event_date: string;
  }[];
  const years = [...new Set(rounds.map((r) => r.event_date.slice(0, 4)))].sort();
  test.skip(years.length < 2, 'needs a shooter with rounds in two calendar years');
  const first = years[0] as string;
  const w = `${first}-01-01..${first}-12-31`;

  const splits = page.waitForRequest((r) =>
    new URL(r.url()).pathname.endsWith(`/api/shooters/${String(shooter.shooter_id)}/splits`),
  );
  await page.goto(`/shooters/${shooter.shooter_id}?w=${w}`);
  const params = new URL((await splits).url()).searchParams;
  expect(params.get('since')).toBe(`${first}-01-01`);
  expect(params.get('as_of')).toBe(`${first}-12-31`);
  await expect(
    page.getByRole('region', { name: `Attendance calendar ${first}`, exact: true }),
  ).toBeVisible({ timeout: 15_000 });
});

test('the insights cards say what date they are as of, and More insights can show all', async ({
  page,
}) => {
  const shooter = await busiestShooter(page);
  const feed = (await (
    await page.request.get(`/api/insights/shooters/${shooter.shooter_id}`)
  ).json()) as {
    more: unknown[];
    n_more: number;
  };
  await page.goto(`/shooters/${shooter.shooter_id}`);
  const stats = page.getByRole('region', { name: 'Stats', exact: true });
  await expect(stats.getByText(/^As of .* · not affected by the time filter$/)).toBeVisible();
  const insights = page.getByRole('region', { name: 'Insights', exact: true });
  if (feed.n_more > 0) {
    await expect(insights.getByText(/^As of .* · not affected by the time filter$/)).toBeVisible();
    await insights.getByText(`More insights (${String(feed.n_more)})`).click();
    if (feed.n_more > feed.more.length) {
      const all = insights.getByRole('button', { name: `Show all ${String(feed.n_more)}` });
      const box = await all.boundingBox();
      expect(box?.height).toBeGreaterThanOrEqual(44);
      await all.click();
      await expect(all).toHaveCount(0);
    }
  }
  await expectNoSideScroll(page);
});

test('the shooters list explains what Active only means', async ({ page }) => {
  await page.goto('/shooters');
  await expect(
    page.getByText('Active = shot in the last 12 months and has 5+ rounds'),
  ).toBeVisible();
  await expectNoSideScroll(page);
});
