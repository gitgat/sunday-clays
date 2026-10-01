import type { Page } from '@playwright/test';

import { expect, test } from './fixtures';

interface Listed {
  shooter_id: number;
  display_name: string;
  status: string;
  n_rounds: number;
}

/** The living shooter with the most rounds and the latest year they shot, all read from the API. */
async function pickShooter(page: Page) {
  const listed = await page.request.get('/api/shooters');
  expect(listed.status()).toBe(200);
  const shooters = ((await listed.json()) as Listed[]).filter((s) => s.status !== 'deceased');
  const chosen = shooters.reduce((a, b) => (b.n_rounds > a.n_rounds ? b : a));
  const rounds = await page.request.get(`/api/shooters/${chosen.shooter_id}/rounds`);
  expect(rounds.status()).toBe(200);
  const dates = ((await rounds.json()) as { event_date: string }[]).map((r) => r.event_date);
  const latestYear = dates.reduce((a, b) => (b > a ? b : a)).slice(0, 4);
  const shotDates = new Set(dates.filter((d) => d.startsWith(`${latestYear}-`)));
  return { ...chosen, latestYear, shotDates };
}

/** The phone top bar has a select, the desktop content header a segmented control; only one is visible. */
async function windowControl(page: Page) {
  const select = page.getByRole('combobox', { name: 'Time window' });
  const group = page.getByRole('group', { name: 'Time window' });
  await expect(select.or(group)).toBeVisible();
  if (await select.isVisible()) return { kind: 'select' as const, select };
  return { kind: 'buttons' as const, group };
}

async function chooseWindow(
  page: Page,
  value: '8w' | '3m' | '6m' | 'ytd',
  short: '8W' | '3M' | '6M' | 'YTD',
) {
  const control = await windowControl(page);
  if (control.kind === 'select') await control.select.selectOption(value);
  else await control.group.getByRole('button', { name: short }).click();
}

test('choosing a time window writes it to the URL and in-app links keep it', async ({ page }) => {
  const shooter = await pickShooter(page);
  await page.goto(`/shooters/${shooter.shooter_id}`);
  const control = await windowControl(page);
  if (control.kind === 'select') {
    await expect(control.select).toHaveValue('8w');
    const box = await control.select.boundingBox();
    expect(box?.height).toBeGreaterThanOrEqual(44);
  } else {
    const eight = control.group.getByRole('button', { name: '8W' });
    await expect(eight).toHaveAttribute('aria-pressed', 'true');
    const box = await control.group.getByRole('button', { name: '6M' }).boundingBox();
    expect(box?.height).toBeGreaterThanOrEqual(44);
    expect(box?.width).toBeGreaterThanOrEqual(44);
  }
  // The default is never written to the URL.
  expect(new URL(page.url()).searchParams.has('w')).toBe(false);

  await chooseWindow(page, '6m', '6M');
  await expect(page).toHaveURL(/[?&]w=6m(&|$)/);

  // An in-app link carries `w` like it carries `rt`.
  const home = page.getByRole('link', { name: 'Sunday Clays' }).first();
  await expect(home).toHaveAttribute('href', /[?&]w=6m/);
  await home.click();
  await expect(page).toHaveURL(/[?&]w=6m(&|$)/);
  // The Sunday Sheet keeps `w` in its URL but shows no window control; back on the profile the
  // window still applies.
  await expect(page.getByRole('heading', { level: 1, name: 'The Sunday Sheet' })).toBeVisible();
  await page.goBack();
  const after = await windowControl(page);
  if (after.kind === 'select') await expect(after.select).toHaveValue('6m');
  else {
    await expect(after.group.getByRole('button', { name: '6M' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  }

  // Choosing the default again removes the key.
  await chooseWindow(page, '8w', '8W');
  await expect(page).not.toHaveURL(/[?&]w=/);
});

test('the attendance calendar explains itself and lists only Sundays', async ({ page }) => {
  const shooter = await pickShooter(page);
  await page.goto(`/shooters/${shooter.shooter_id}`);
  const region = page.getByRole('region', {
    name: `Attendance calendar ${shooter.latestYear}`,
    exact: true,
  });
  await expect(region).toBeVisible();

  const about = region.getByRole('button', { name: 'About this chart' });
  await expect(about).toHaveAttribute('aria-expanded', 'false');
  const box = await about.boundingBox();
  expect(box?.height).toBeGreaterThanOrEqual(44);
  await about.click();
  await expect(about).toHaveAttribute('aria-expanded', 'true');
  await expect(region.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  await expect(region.getByRole('heading', { name: "How it's worked out" })).toBeVisible();
  await expect(region.getByText('All time')).toBeVisible();
  await about.click();
  await expect(region.getByRole('heading', { name: 'What this shows' })).toHaveCount(0);

  // A Sunday-only grid: no 7-day calendar, and every listed date is a Sunday.
  await region.getByRole('button', { name: 'Table' }).click();
  const table = page.getByRole('table', { name: `Attendance calendar ${shooter.latestYear}` });
  await expect(table).toBeVisible();
  const cells = await table
    .locator('tbody tr')
    .evaluateAll((rows) =>
      rows.map((row) => [...row.querySelectorAll('td, th')].map((c) => c.textContent ?? '')),
    );
  expect(cells.length).toBeGreaterThan(0);
  for (const [date] of cells) {
    expect(new Date(`${date ?? ''}T00:00:00Z`).getUTCDay(), `${date} is a Sunday`).toBe(0);
  }
  // Every Sunday the API says they shot is a "shot" row; the rest are "missed" Sundays.
  const shot = cells.filter(([, state]) => state === 'shot').map(([date]) => date);
  expect(new Set(shot)).toEqual(shooter.shotDates);
  for (const [, state] of cells) expect(['shot', 'missed']).toContain(state);
});

test('the page does not scroll sideways with the time window and an open explainer', async ({
  page,
}) => {
  const shooter = await pickShooter(page);
  await page.goto(`/shooters/${shooter.shooter_id}?w=all`);
  const region = page.getByRole('region', {
    name: `Attendance calendar ${shooter.latestYear}`,
    exact: true,
  });
  await region.getByRole('button', { name: 'About this chart' }).click();
  await expect(region.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test('the time window offers 8W and YTD, and a retired w=season link reads as 8W', async ({
  page,
}) => {
  await page.goto('/club');
  const control = await windowControl(page);
  if (control.kind === 'select') {
    await expect(control.select.locator('option')).toHaveText([
      '8W',
      '3M',
      '6M',
      '12M',
      'YTD',
      'All',
      'Custom…',
    ]);
  } else {
    await expect(control.group.getByRole('button')).toHaveText([
      '8W',
      '3M',
      '6M',
      '12M',
      'YTD',
      'All',
      'Custom',
    ]);
  }
  await chooseWindow(page, '3m', '3M');
  await expect(page).toHaveURL(/[?&]w=3m(&|$)/);
  await chooseWindow(page, 'ytd', 'YTD');
  await expect(page).toHaveURL(/[?&]w=ytd(&|$)/);

  await page.goto('/club?w=season');
  const retired = await windowControl(page);
  if (retired.kind === 'select') await expect(retired.select).toHaveValue('8w');
  else {
    await expect(retired.group.getByRole('button', { name: '8W' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  }
});
