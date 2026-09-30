import { readFile } from 'node:fs/promises';
import type { Page } from '@playwright/test';
import { expect, test } from './fixtures';
import {
  expectNoSideScroll,
  expectTapTargets,
  expectTitlesUntruncated,
  whenSettled,
} from './layout';
import {
  WEATHER_EFFECTS,
  WEATHER_EVENTS,
  WEATHER_SENSITIVITY,
  WEATHER_TURNOUT,
} from '../src/features/weather/mocks';

// compose.test.yaml sets WEATHER_ENABLED=false: no Sunday has weather, so every weather surface
// shows its empty state here. The charts are covered by Vitest + MSW.
async function shooterId(page: Page, name: string): Promise<number> {
  const response = await page.request.get(`/api/shooters?q=${encodeURIComponent(name)}`);
  expect(response.ok()).toBe(true);
  const rows = (await response.json()) as { shooter_id: number; display_name: string }[];
  const row = rows.find((r) => r.display_name === name);
  if (row === undefined) throw new Error(`${name} is not in the seeded fixtures`);
  return row.shooter_id;
}

test('the weather page shows its empty state', async ({ page }) => {
  await page.goto('/weather');
  await expect(page.getByRole('heading', { level: 1, name: 'Weather' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'No weather data yet' })).toBeVisible();
});

test('the weather page grouped by time of year still shows its empty state', async ({ page }) => {
  await page.goto('/weather?wdim=time_of_year');
  await expect(page.getByRole('heading', { level: 1, name: 'Weather' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'No weather data yet' })).toBeVisible();
});

test('the profile weather section explains what it needs', async ({ page }) => {
  const hadley = await shooterId(page, 'Hadley, Ike');
  await page.goto(`/shooters/${hadley}`);
  await expect(
    page.getByText(
      'Not enough rounds with weather yet. This needs 10 rounds with a weather record.',
    ),
  ).toBeVisible();
});

test('the populated weather page fits the viewport (stubbed API)', async ({ page }) => {
  // The stack has no weather (WEATHER_ENABLED=false), so stub the four endpoints to lay out the
  // charts at 390 and 1440 px.
  const stubs: [string, unknown][] = [
    ['events', WEATHER_EVENTS],
    ['effects', WEATHER_EFFECTS],
    ['sensitivity', WEATHER_SENSITIVITY],
    ['turnout', WEATHER_TURNOUT],
  ];
  for (const [name, body] of stubs) {
    await page.route(`**/api/weather/${name}*`, (route) => route.fulfill({ json: body }));
  }
  // The window anchors on the latest scored Sunday; the stub pins it next to the mock Sundays.
  await page.route('**/api/meta', async (route) => {
    const real = (await (await route.fetch()).json()) as Record<string, unknown>;
    await route.fulfill({ json: { ...real, last_score_date: '2026-09-27' } });
  });
  const effects: string[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/api/weather/effects')) effects.push(r.url());
  });
  await page.goto('/weather');
  await expect(page.getByRole('region', { name: 'Weather sensitivity' })).toBeVisible();
  await whenSettled(page);
  // No w in the URL: Weather opens on the last 12 months (anchor 2026-09-27 in the stub), the
  // header says so, and a thin window is named with one-tap 12M / All (the stub holds 3 Sundays).
  await expect(page).not.toHaveURL(/[?&]w=/);
  expect(new URL(effects[0] ?? '').searchParams.get('from')).toBe('2025-09-28');
  const desktop = (page.viewportSize()?.width ?? 0) >= 1024;
  if (desktop) {
    await expect(
      page.getByRole('group', { name: 'Time window' }).getByRole('button', { name: '12M' }),
    ).toHaveAttribute('aria-pressed', 'true');
  } else {
    await expect(page.getByRole('combobox', { name: 'Time window' })).toHaveValue('12m');
  }
  const nudge = page.getByRole('note');
  await expect(nudge).toContainText(
    'Only 3 Sundays in the last 12 months. Weather patterns need more.',
  );
  await expect(nudge.getByRole('button', { name: 'Show the last 12 months' })).toHaveCount(0);
  await expect(page.getByText('3 of 3 Sundays in the last 12 months match.')).toBeVisible();
  await expect(page.getByText('All, last 12 months', { exact: true })).toBeVisible();
  await expectNoSideScroll(page);
  await expectTitlesUntruncated(page);
  await expectTapTargets(page);
  for (const title of [
    'Conditions explorer',
    'Difficulty and weather',
    'Wind rose',
    'Scores by conditions',
    'Turnout by conditions',
    'Weather sensitivity',
  ]) {
    const heading = page.getByRole('heading', { level: 2, name: title, exact: true });
    await expect(heading).toBeVisible();
    // The whole title shows: no ellipsis, and the heading is not squeezed to a sliver.
    const box = await heading.evaluate((el) => ({
      wide: el.scrollWidth <= el.clientWidth,
      width: el.getBoundingClientRect().width,
    }));
    expect(box.wide, `${title} is cut off`).toBe(true);
    expect(box.width, `${title} width`).toBeGreaterThan(60);
  }
});

test('the band charts group by Time of year, winter to fall (stubbed API)', async ({ page }) => {
  const stubs: [string, unknown][] = [
    ['events', WEATHER_EVENTS],
    ['effects', WEATHER_EFFECTS],
    ['sensitivity', WEATHER_SENSITIVITY],
    ['turnout', WEATHER_TURNOUT],
  ];
  for (const [name, body] of stubs) {
    await page.route(`**/api/weather/${name}*`, (route) => route.fulfill({ json: body }));
  }
  await page.route('**/api/meta', async (route) => {
    const real = (await (await route.fetch()).json()) as Record<string, unknown>;
    await route.fulfill({ json: { ...real, last_score_date: '2026-09-27' } });
  });
  await page.goto('/weather?wdim=time_of_year&wb=table&wt=table');
  const scores = page.getByRole('region', { name: 'Scores by conditions' });
  await expect(scores.getByRole('combobox', { name: 'Group scores by' })).toHaveValue(
    'time_of_year',
  );
  await expect(scores.getByRole('cell', { name: 'Summer' })).toBeVisible();
  const turnout = page.getByRole('region', { name: 'Turnout by conditions' });
  await expect(turnout.getByRole('cell', { name: 'Winter' })).toBeVisible();
  await whenSettled(page);
  await expectNoSideScroll(page);
  await expectTitlesUntruncated(page);
});

test('a temperature measure with no spread shows a note, not bars (stubbed API)', async ({
  page,
}) => {
  // What the owner saw: tau2 = 0 for temperature shrinks every effect to zero.
  const flat = {
    ...WEATHER_SENSITIVITY,
    tau2: WEATHER_SENSITIVITY.tau2.map((t) => (t.covariate === 'temp_f' ? { ...t, tau2: 0 } : t)),
    shooters: WEATHER_SENSITIVITY.shooters.map((s) => ({
      ...s,
      terms: s.terms.map((t) => (t.covariate === 'temp_f' ? { ...t, shrunk: 0, per_unit: 0 } : t)),
    })),
  };
  const stubs: [string, unknown][] = [
    ['events', WEATHER_EVENTS],
    ['effects', WEATHER_EFFECTS],
    ['sensitivity', flat],
    ['turnout', WEATHER_TURNOUT],
  ];
  for (const [name, body] of stubs) {
    await page.route(`**/api/weather/${name}*`, (route) => route.fulfill({ json: body }));
  }
  await page.route('**/api/meta', async (route) => {
    const real = (await (await route.fetch()).json()) as Record<string, unknown>;
    await route.fulfill({ json: { ...real, last_score_date: '2026-09-27' } });
  });
  await page.goto('/weather?wsc=temp_f');
  const card = page.getByRole('region', { name: 'Weather sensitivity' });
  await expect(
    card.getByText(/No one's scores move with temperature more than chance/),
  ).toBeVisible();
  await whenSettled(page);
  await expectNoSideScroll(page);
  await card.getByRole('combobox', { name: 'Sensitivity to' }).selectOption('gust_mph');
  await expect(card.getByText(/No one's scores move/)).toHaveCount(0);
  await expect(card.getByRole('img', { name: /weather sensitivity/ })).toBeVisible();
  await expectNoSideScroll(page);
});

test('fullscreen and the CSV cover every Sunday with weather (stubbed API)', async ({ page }) => {
  // The stack has no weather, so stub the endpoints. The 2018 Sunday gets a difficulty so it is
  // a point of its own, well outside the default window.
  const events = WEATHER_EVENTS.map((e) =>
    e.event_date === '2018-12-30' ? { ...e, difficulty: 0.5 } : e,
  );
  const effects: string[] = [];
  const turnout: string[] = [];
  await page.route('**/api/weather/events*', (route) => route.fulfill({ json: events }));
  await page.route('**/api/weather/sensitivity*', (route) =>
    route.fulfill({ json: WEATHER_SENSITIVITY }),
  );
  await page.route('**/api/weather/effects*', (route) => {
    effects.push(route.request().url());
    return route.fulfill({ json: WEATHER_EFFECTS });
  });
  await page.route('**/api/weather/turnout*', (route) => {
    turnout.push(route.request().url());
    return route.fulfill({ json: WEATHER_TURNOUT });
  });
  await page.route('**/api/meta', async (route) => {
    const real = (await (await route.fetch()).json()) as Record<string, unknown>;
    await route.fulfill({ json: { ...real, last_score_date: '2026-09-27' } });
  });
  const everySunday = events.filter((e) => e.difficulty !== null);

  await page.goto('/weather?wf=table');
  const card = page.getByRole('region', { name: 'Difficulty and weather' });
  await expect(card.getByRole('table')).toBeVisible();
  // The card holds only the default window; the stub has older Sundays too.
  const inlineRows = await card.getByRole('table').getByRole('row').count();
  expect(1 + everySunday.length).toBeGreaterThan(inlineRows);
  await card.getByRole('button', { name: 'Fullscreen' }).click();
  const dialog = page.getByRole('dialog', { name: 'Difficulty and weather' });
  await expect(dialog.getByText('Every Sunday with weather.')).toBeVisible();
  await expect(dialog.getByRole('table').getByRole('row')).toHaveCount(1 + everySunday.length);
  await dialog.getByRole('button', { name: 'Close' }).click();
  const download = page.waitForEvent('download');
  await card.getByRole('button', { name: 'CSV' }).click();
  const text = (await readFile(await (await download).path(), 'utf8')).replace(/^\uFEFF/, '');
  expect(text.trimEnd().split('\r\n')).toHaveLength(1 + everySunday.length);

  // The band and turnout charts fetch the whole history when fullscreen opens.
  const scores = page.getByRole('region', { name: 'Scores by conditions' });
  await scores.getByRole('button', { name: 'Fullscreen' }).click();
  await expect(
    page
      .getByRole('dialog', { name: 'Scores by conditions' })
      .getByText('Every Sunday with weather on record.'),
  ).toBeVisible();
  expect(effects.some((u) => !new URL(u).searchParams.has('from'))).toBe(true);
  expect(effects.some((u) => new URL(u).searchParams.has('from'))).toBe(true);
  await page
    .getByRole('dialog', { name: 'Scores by conditions' })
    .getByRole('button', { name: 'Close' })
    .click();
  const turnoutCard = page.getByRole('region', { name: 'Turnout by conditions' });
  await turnoutCard.getByRole('button', { name: 'Fullscreen' }).click();
  await expect(
    page
      .getByRole('dialog', { name: 'Turnout by conditions' })
      .getByText('Every Sunday with weather on record.'),
  ).toBeVisible();
  expect(turnout.some((u) => !new URL(u).searchParams.has('from'))).toBe(true);

  await page.setViewportSize({ width: 390, height: 844 });
  await whenSettled(page);
  await expectNoSideScroll(page);
});
