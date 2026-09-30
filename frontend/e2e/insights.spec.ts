import type { Page } from '@playwright/test';

import { expect, test } from './fixtures';
import { expectNoSideScroll, whenSettled } from './layout';

interface Chart {
  type: 'explorer' | 'page';
  route: string | null;
  anchor: string | null;
  window: { from: string; to: string };
  highlight: Record<string, unknown[] | null>;
}
interface Insight {
  key: string;
  subject_type: string;
  subject_id: string;
  chart: Chart;
}
interface Feed {
  as_of: string | null;
  pinned: Insight | null;
  hero: Insight | null;
  top: Insight[];
  kudos: unknown[];
  more: Insight[];
}
interface Shooter {
  shooter_id: number;
  n_events: number;
}

// Expectations come from the API at run time, never from hard-coded fixture values.
async function getJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), path).toBe(true);
  return (await response.json()) as T;
}

/** The cards of a profile's "Top insights" list, in screen order (the digest line first). */
function profileCards(feed: Feed): Insight[] {
  return [...(feed.pinned === null ? [] : [feed.pinned]), ...feed.top];
}

/** A card whose chart is a profile chart with something to ring (spec §5 e2e). */
function ringsAProfileChart(insight: Insight): boolean {
  const { chart } = insight;
  return (
    chart.type === 'page' &&
    (chart.route ?? '').startsWith('/shooters/') &&
    Object.values(chart.highlight).some((items) => (items ?? []).length > 0)
  );
}

/**
 * A regular whose profile has a card linking a highlighted profile chart (the fx world has
 * many), with that card's position in the list.
 */
async function shooterWithInsights(
  page: Page,
): Promise<{ id: number; card: Insight; index: number }> {
  const shooters = await getJson<Shooter[]>(page, '/api/shooters');
  const regulars = [...shooters].sort((a, b) => b.n_events - a.n_events).slice(0, 20);
  for (const s of regulars) {
    const feed = await getJson<Feed>(page, `/api/insights/shooters/${String(s.shooter_id)}`);
    const cards = profileCards(feed);
    const index = cards.findIndex(ringsAProfileChart);
    const card = cards[index];
    if (card !== undefined) return { id: s.shooter_id, card, index };
  }
  throw new Error('the fx world needs a regular with a highlighted profile-chart insight');
}

test('home shows the recap, the top story, the insight cards and kudos', async ({ page }) => {
  const feed = await getJson<Feed>(page, '/api/insights/home');
  expect(feed.pinned, 'the fx world has a latest Sunday to recap').not.toBeNull();
  await page.goto('/');
  await whenSettled(page);
  await expect(page.getByRole('region', { name: 'Last Sunday' })).toBeVisible();
  if (feed.hero !== null) {
    await expect(page.getByRole('list', { name: 'Top story' })).toBeVisible();
  }
  if (feed.top.length > 0) {
    await expect(
      page.getByRole('list', { name: 'Around the club' }).getByRole('listitem'),
    ).toHaveCount(feed.top.length);
  }
  if (feed.kudos.length > 0) {
    await expect(page.getByRole('region', { name: /^Kudos/ })).toBeVisible();
  }
  await expectNoSideScroll(page);
});

test('a profile insight opens its chart with the link window, and explains itself', async ({
  page,
}) => {
  const { id, card: insight, index } = await shooterWithInsights(page);
  await page.goto(`/shooters/${String(id)}`);
  await whenSettled(page);
  const section = page.getByRole('region', { name: 'Insights' });
  const top = section.getByRole('list', { name: 'Top insights' });
  await expect(top.getByRole('listitem').first()).toBeVisible();
  await expectNoSideScroll(page);

  const card = top.getByRole('listitem').nth(index);
  const how = card.getByRole('button', { name: 'How we worked it out' });
  await how.click();
  await expect(how).toHaveAttribute('aria-expanded', 'true');
  await expect(card.getByRole('heading', { name: 'How we worked it out' })).toBeVisible();

  // A profile chart (trend, rating, calendar, finishes, tough days or trophies), never only the
  // Sunday's Results: the page anchor, its window and the ringed evidence are all checked.
  const { chart } = insight;
  await card.getByRole('link', { name: /^See the chart/ }).click();
  await expect(page).toHaveURL(new RegExp(`#chart-${chart.anchor ?? ''}$`));
  await expect(page).toHaveURL(new RegExp(`${chart.anchor ?? ''}\\.from=${chart.window.from}`));
  const target = page.locator(`#chart-${chart.anchor ?? ''}`);
  await expect(target).toBeVisible();
  const chip = target.locator('[data-marked]');
  await expect(chip).toContainText('Showing what the insight points to.');
  await expect(chip).not.toHaveAttribute('data-marked', '0');
  await whenSettled(page);
  await expectNoSideScroll(page);
});

test('the latest Sunday shows its insights without side scroll', async ({ page }) => {
  const home = await getJson<Feed>(page, '/api/insights/home');
  if (home.as_of === null) throw new Error('the fx world has held Sundays');
  const feed = await getJson<Feed>(page, `/api/insights/sundays/${home.as_of}`);
  await page.goto(`/events/${home.as_of}`);
  await whenSettled(page);
  if (feed.top.length > 0) {
    await expect(
      page.getByRole('region', { name: 'Insights' }).getByRole('list', { name: 'Top insights' }),
    ).toBeVisible();
  }
  await expectNoSideScroll(page);
});

test('the club page shows its insights above the charts', async ({ page }) => {
  const feed = await getJson<Feed>(page, '/api/insights/club');
  await page.goto('/club');
  await whenSettled(page);
  if (feed.top.length > 0) {
    await expect(page.getByRole('region', { name: 'Insights' })).toBeVisible();
  }
  await expectNoSideScroll(page);
});
