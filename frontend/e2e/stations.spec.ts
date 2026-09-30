import { readFile } from 'node:fs/promises';

import type { Page } from '@playwright/test';

import { expect, test } from './fixtures';
import {
  expectNoSideScroll,
  expectTapTargets,
  expectTitlesUntruncated,
  whenSettled,
} from './layout';

interface StationStat {
  /** The station's label: "7", or "7A" for a lettered station. */
  label: string;
  station_no: number;
  hit_pct: number | null;
  n_rounds: number;
}
interface StationsBody {
  coverage: {
    n_station_sundays: number;
    first_date: string | null;
    last_date: string | null;
    n_scored_sundays: number;
    latest_date: string | null;
  };
  stations: StationStat[];
  by_event: { event_date: string }[];
  matrix: { shooter_id: number; display_name: string; n_rounds: number }[];
}
interface DetailBody {
  wind: { band: string; n_events: number; sufficient: boolean }[];
  leaders: { shooter_id: number; display_name: string }[];
}
interface ShooterStationsBody {
  coverage: {
    n_rounds: number;
    n_sundays: number;
    first_date: string | null;
    last_date: string | null;
    latest_date: string | null;
  };
  stations: { label: string; hit_pct: number; n_rounds: number; delta: number }[];
}

// Expectations come from the API at run time, never from hard-coded fixture values.
async function getJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), path).toBe(true);
  return (await response.json()) as T;
}

const escapeRe = (text: string): string => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const pct = (value: number | null): string =>
  value === null ? '—' : `${(value * 100).toFixed(2)}%`;
const points = (delta: number): string => `${delta > 0 ? '+' : ''}${(delta * 100).toFixed(2)} pts`;

test('stations page summarises every station from the API', async ({ page }) => {
  const body = await getJson<StationsBody>(page, '/api/stations');
  await page.goto('/stations?w=all');
  await expect(page.getByRole('heading', { level: 1, name: 'Stations' })).toBeVisible();
  const table = page.getByRole('table', { name: 'Station summary' });
  for (const station of body.stations) {
    await expect(
      table.getByRole('row', { name: new RegExp(`^Station ${station.label}\\b`) }),
    ).toContainText(pct(station.hit_pct));
  }
  await expect(page.getByRole('region', { name: 'Hit % by station' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Hit % over time' })).toBeVisible();
  // The heatmap needs a shooter with 3+ rounds at a station; the seeded data may have none.
  if (body.matrix.some((c) => c.n_rounds >= 3)) {
    await expect(page.getByRole('region', { name: 'Shooter × station' })).toBeVisible();
  } else {
    await expect(page.getByText('Nobody has shot any station three times so far.')).toBeVisible();
  }
  // Every chart explains itself in plain words.
  const about = page.getByRole('region', { name: 'Hit % by station' }).getByRole('button', {
    name: 'About this chart',
  });
  await about.click();
  await expect(page.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  await expect(page.getByRole('heading', { name: "How it's worked out" })).toBeVisible();
});

const fmt = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  timeZone: 'UTC',
});
const day = (iso: string | null): string => fmt.format(new Date(`${iso}T00:00:00Z`));
const span = (c: { first_date: string | null; last_date: string | null }): string =>
  c.first_date === c.last_date ? day(c.first_date) : `${day(c.first_date)} – ${day(c.last_date)}`;

test('the stations page notes how few Sundays the station data covers', async ({ page }) => {
  const { coverage } = await getJson<StationsBody>(page, '/api/stations');
  await page.goto('/stations?w=all');
  const note = page.getByRole('note', { name: 'Station data coverage' });
  await expect(note).toBeVisible();
  const noun = (n: number): string => `${n} ${n === 1 ? 'Sunday' : 'Sundays'}`;
  await expect(note).toContainText(
    `Station scores cover ${coverage.n_station_sundays} of ${noun(coverage.n_scored_sundays)} so far (${span(coverage)})`,
  );
  await whenSettled(page);
  await expectNoSideScroll(page);
});

test('the profile coverage note counts the shooter’s own rounds, not the club’s', async ({
  page,
}) => {
  const body = await getJson<StationsBody>(page, '/api/stations');
  const [cell] = body.matrix;
  if (!cell) throw new Error('the seeded fixtures have no station matrix');
  const mine = await getJson<ShooterStationsBody>(
    page,
    `/api/shooters/${cell.shooter_id}/stations`,
  );
  await page.goto(`/shooters/${cell.shooter_id}?w=all`);
  const note = page
    .getByRole('region', { name: 'Station breakdown for this shooter' })
    .getByRole('note', { name: 'Station data coverage' });
  const { n_rounds: rounds, n_sundays: sundays } = mine.coverage;
  await expect(note).toContainText(
    `Station scores for this shooter: ${rounds} ${rounds === 1 ? 'round' : 'rounds'} on ${sundays} ${sundays === 1 ? 'Sunday' : 'Sundays'} so far`,
  );
});

test('the era toggle is kept in the URL', async ({ page }) => {
  await page.goto('/stations?w=all');
  await page.getByRole('button', { name: 'All setups' }).click();
  await expect(page).toHaveURL(/era=all/);
  await expect(page.getByRole('button', { name: 'All setups' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  const all = await getJson<StationsBody>(page, '/api/stations?era=all');
  const [first] = all.stations;
  if (!first) throw new Error('the seeded fixtures have no station data');
  await expect(
    page.getByRole('row', { name: new RegExp(`^Station ${first.label}\\b`) }),
  ).toContainText(pct(first.hit_pct));
  await page.getByRole('button', { name: /^Since last reset/ }).click();
  await expect(page).not.toHaveURL(/era=/);
});

test('each station detail shows its wind cells and leaders as the API reports them', async ({
  page,
}) => {
  const body = await getJson<StationsBody>(page, '/api/stations');
  await page.goto('/stations?w=all');
  const picker = page.getByRole('group', { name: 'Choose a station' });
  for (const { label: no } of body.stations) {
    const detail = await getJson<DetailBody>(page, `/api/stations/${no}`);
    await picker.getByRole('button', { name: `Station ${no}` }).click();
    await expect(page).toHaveURL(new RegExp(`st=${no}(&|$)`));
    await expect(page.getByRole('region', { name: `Station ${no} eras` })).toBeVisible();
    if (detail.wind.length === 0) {
      await expect(page.getByText(`No weather data for station ${no} so far.`)).toBeVisible();
    } else {
      // Wind × station cells with too few Sundays are greyed and labelled with their Sundays.
      const wind = page.getByRole('region', { name: `Wind × station ${no}` });
      await expect(wind).toBeVisible();
      await wind.getByRole('button', { name: 'Table' }).click();
      for (const cell of detail.wind) {
        const row = wind.getByRole('row', { name: new RegExp(`^${escapeRe(cell.band)}`) });
        await expect(row).toContainText('mph gusts');
        await expect(row).toContainText(String(cell.n_events));
        await expect(row).toContainText(cell.sufficient ? 'yes' : 'no');
      }
    }
    const leaders = page.getByRole('region', { name: `Station ${no} leaders` });
    if (detail.leaders.length === 0) {
      await expect(leaders).toContainText(`Nobody has shot station ${no} three times so far.`);
    } else {
      // Ten leaders show; a longer list offers "Show all N" for the rest.
      if (detail.leaders.length > 10) {
        await expect(leaders.getByRole('listitem')).toHaveCount(10);
        await leaders.getByRole('button', { name: `Show all ${detail.leaders.length}` }).click();
      }
      await expect(leaders.getByRole('listitem')).toHaveCount(detail.leaders.length);
      for (const leader of detail.leaders) {
        await expect(leaders.getByRole('link', { name: leader.display_name })).toHaveAttribute(
          'href',
          `/shooters/${leader.shooter_id}`,
        );
      }
    }
  }
});

test('a profile shows where the shooter loses targets', async ({ page }) => {
  const body = await getJson<StationsBody>(page, '/api/stations');
  const [cell] = body.matrix;
  if (!cell) throw new Error('the seeded fixtures have no station matrix');
  const shooter = await getJson<ShooterStationsBody>(
    page,
    `/api/shooters/${cell.shooter_id}/stations`,
  );
  await page.goto(`/shooters/${cell.shooter_id}?w=all`);
  const section = page.getByRole('region', { name: 'Station breakdown for this shooter' });
  await expect(section).toBeVisible();
  for (const s of shooter.stations) {
    // Deltas are hidden until a station has been shot in at least two rounds.
    const row = section.getByRole('row', { name: new RegExp(`^Station ${s.label}\\b`) });
    await expect(row).toContainText(pct(s.hit_pct));
    if (s.n_rounds >= 2) await expect(row).toContainText(points(s.delta));
    else await expect(row).not.toContainText('pts');
  }
  if (!shooter.stations.some((s) => s.n_rounds >= 2)) {
    await expect(section).toContainText(
      'Deltas appear once a station has been shot at least twice so far.',
    );
  }
});

test('the stations page fits the viewport with 44 px targets and whole titles', async ({
  page,
}) => {
  const body = await getJson<StationsBody>(page, '/api/stations');
  await page.goto('/stations?w=all');
  await expect(page.getByRole('region', { name: 'Hit % by station' })).toBeVisible();
  await whenSettled(page);
  await expectNoSideScroll(page);
  await expectTapTargets(page);
  await expectTitlesUntruncated(page);
  const [first] = body.stations;
  if (first) {
    const detail = await getJson<DetailBody>(page, `/api/stations/${first.label}`);
    const [leader] = detail.leaders;
    if (leader) {
      await expect(page.getByRole('link', { name: leader.display_name })).toHaveCSS(
        'text-decoration-line',
        'underline',
      );
    }
  }
});

test('the profile stations section fits the viewport with 44 px targets and whole titles', async ({
  page,
}) => {
  const body = await getJson<StationsBody>(page, '/api/stations');
  const [cell] = body.matrix;
  if (!cell) throw new Error('the seeded fixtures have no station matrix');
  await page.goto(`/shooters/${cell.shooter_id}?w=all`);
  await expect(
    page.getByRole('region', { name: 'Station breakdown for this shooter' }),
  ).toBeVisible();
  await whenSettled(page);
  await expectNoSideScroll(page);
  await expectTapTargets(page);
  await expectTitlesUntruncated(page);
});

test('Hit % over time: fullscreen and the CSV cover every Sunday', async ({ page }) => {
  const body = await getJson<StationsBody & { by_event: unknown[] }>(
    page,
    '/api/stations?era=current',
  );
  expect(body.by_event.length).toBeGreaterThan(0);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/stations?sttime=table&w=all');
  const card = page.getByRole('region', { name: 'Hit % over time' });
  await expect(card.getByRole('table').getByRole('row')).toHaveCount(1 + body.by_event.length);
  await card.getByRole('button', { name: 'Fullscreen' }).click();
  const dialog = page.getByRole('dialog', { name: 'Hit % over time' });
  await expect(dialog.getByRole('table').getByRole('row')).toHaveCount(1 + body.by_event.length);
  // The card opens on the time window; fullscreen shows every Sunday and says so.
  await expect(dialog.getByText('All time', { exact: true })).toBeVisible();
  const download = page.waitForEvent('download');
  await dialog.getByRole('button', { name: 'CSV' }).click();
  const text = (await readFile(await (await download).path(), 'utf8')).replace(/^\uFEFF/, '');
  expect(text.trimEnd().split('\r\n')).toHaveLength(1 + body.by_event.length);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/stations?sttime=table,full&w=all');
  await expect(page.getByRole('dialog', { name: 'Hit % over time' })).toBeVisible();
  await expectNoSideScroll(page);
});

const shortDay = (iso: string | null): string =>
  new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' }).format(
    new Date(`${iso}T00:00:00Z`),
  );

/** The station Sundays the API reports, oldest first: windows below are built from them, never from today. */
async function stationSundays(page: Page): Promise<string[]> {
  const body = await getJson<StationsBody>(page, '/api/stations');
  const days = [...new Set(body.by_event.map((e) => e.event_date))].sort();
  if (days.length < 2) throw new Error('the seeded fixtures need two station Sundays');
  return days;
}

test('a custom window narrows the summary, the tags and the coverage to that Sunday', async ({
  page,
}) => {
  const days = await stationSundays(page);
  const last = days[days.length - 1] as string;
  const windowed = await getJson<StationsBody>(page, `/api/stations?since=${last}&as_of=${last}`);
  const everything = await getJson<StationsBody>(page, '/api/stations');
  await page.goto(`/stations?w=${last}..${last}`);
  const table = page.getByRole('table', { name: 'Station summary' });
  for (const station of windowed.stations) {
    await expect(
      table.getByRole('row', { name: new RegExp(`^Station ${station.label}\\b`) }),
    ).toContainText(pct(station.hit_pct));
  }
  await expect(page.getByRole('note', { name: 'Setups and dates shown' })).toContainText(
    `Current setups · ${day(last)} – ${day(last)}`,
  );
  await expect(page.getByRole('note', { name: 'Station data coverage' })).toContainText(
    `Station scores cover ${windowed.coverage.n_station_sundays} of `,
  );
  expect(windowed.coverage.n_station_sundays).toBeLessThan(everything.coverage.n_station_sundays);
  await whenSettled(page);
  await expectNoSideScroll(page);
  await expectTapTargets(page);
});

test('Hit % over time: the card follows the window, fullscreen and the CSV keep every Sunday', async ({
  page,
}) => {
  const days = await stationSundays(page);
  const last = days[days.length - 1] as string;
  const windowed = await getJson<StationsBody>(page, `/api/stations?since=${last}&as_of=${last}`);
  const everything = await getJson<StationsBody>(page, '/api/stations');
  expect(windowed.by_event.length).toBeLessThan(everything.by_event.length);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/stations?sttime=table&w=${last}..${last}`);
  const card = page.getByRole('region', { name: 'Hit % over time' });
  await expect(card.getByRole('table').getByRole('row')).toHaveCount(1 + windowed.by_event.length);
  await card.getByRole('button', { name: 'Fullscreen' }).click();
  const dialog = page.getByRole('dialog', { name: 'Hit % over time' });
  await expect(dialog.getByRole('table').getByRole('row')).toHaveCount(
    1 + everything.by_event.length,
  );
  const download = page.waitForEvent('download');
  await dialog.getByRole('button', { name: 'CSV' }).click();
  const text = (await readFile(await (await download).path(), 'utf8')).replace(/^\uFEFF/, '');
  expect(text.trimEnd().split('\r\n')).toHaveLength(1 + everything.by_event.length);
});

test('a window with no station sheets says so, names the latest and widens in one tap', async ({
  page,
}) => {
  const { coverage } = await getJson<StationsBody>(page, '/api/stations');
  await page.goto('/stations?w=2000-01-01..2000-01-31');
  const nudge = page.getByRole('note').filter({ hasText: 'No station sheets in ' });
  await expect(nudge).toContainText(
    `No station sheets in ${day('2000-01-01')} – ${day('2000-01-31')} (latest: ${shortDay(coverage.latest_date)}).`,
  );
  await expect(page.getByRole('table', { name: 'Station summary' })).toHaveCount(0);
  await whenSettled(page);
  await expectNoSideScroll(page);
  await expectTapTargets(page);
  await nudge.getByRole('button', { name: 'Show all time' }).click();
  await expect(page).toHaveURL(/w=all/);
  await expect(page.getByRole('table', { name: 'Station summary' })).toBeVisible();
});

test('a profile with no station sheets in the window says so for the shooter', async ({ page }) => {
  const body = await getJson<StationsBody>(page, '/api/stations');
  const [cell] = body.matrix;
  if (!cell) throw new Error('the seeded fixtures have no station matrix');
  const mine = await getJson<ShooterStationsBody>(
    page,
    `/api/shooters/${cell.shooter_id}/stations?since=2000-01-01&as_of=2000-01-31`,
  );
  expect(mine.stations).toEqual([]);
  await page.goto(`/shooters/${cell.shooter_id}?w=2000-01-01..2000-01-31`);
  const section = page.getByRole('region', { name: 'Station breakdown for this shooter' });
  await expect(
    section.getByRole('note').filter({ hasText: 'No station sheets for this shooter' }),
  ).toContainText(
    `No station sheets for this shooter in ${day('2000-01-01')} – ${day('2000-01-31')} (latest: ${shortDay(mine.coverage.latest_date)}).`,
  );
  await expect(section.getByRole('note', { name: 'Setups and dates shown' })).toContainText(
    'Current setups',
  );
  await whenSettled(page);
  await expectNoSideScroll(page);
  await expectTapTargets(page);
});
