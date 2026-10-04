import type { Page } from '@playwright/test';
import { expect, test } from './fixtures';
import { expectNoSideScroll } from './layout';

test.use({ tourSeen: false });

const TITLES = [
  'The latest Sunday',
  'Which one are you?',
  'Insights and fist bumps',
  'Trophies',
  'Time window',
];

const dialog = (page: Page) => page.getByRole('dialog');

test('a first visit walks the five steps, then never again', async ({ page }) => {
  await page.goto('/');
  await expect(dialog(page)).toHaveAccessibleName(TITLES[0] as string, { timeout: 10_000 });
  await expect(page.getByText('Step 1 of 5')).toBeVisible();
  for (const title of TITLES.slice(1)) {
    await page.getByRole('button', { name: 'Next' }).click();
    await expect(dialog(page)).toHaveAccessibleName(title);
  }
  await page.getByRole('button', { name: 'Done' }).click();
  await expect(dialog(page)).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1, name: 'Sunday Clays' })).toBeFocused();
  await page.reload();
  await page.waitForTimeout(2000);
  await expect(dialog(page)).toHaveCount(0);
});

test('?tour=1 reopens it, drops the parameter, and Esc closes it', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('sc.tour.v1', 'done'));
  await page.goto('/?tour=1');
  await expect(dialog(page)).toBeVisible({ timeout: 10_000 });
  await expect(page).not.toHaveURL(/tour=1/);
  await page.keyboard.press('Escape');
  await expect(dialog(page)).toHaveCount(0);
});

test('keyboard: Tab stays inside the dialog', async ({ page }) => {
  await page.goto('/');
  await expect(dialog(page)).toBeVisible({ timeout: 10_000 });
  for (let i = 0; i < 6; i += 1) {
    await page.keyboard.press('Tab');
    const inside = await page.evaluate(
      () => document.activeElement?.closest('[role="dialog"]') !== null,
    );
    expect(inside, `Tab ${String(i + 1)}`).toBe(true);
  }
});

test('reduced motion still shows every step', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(dialog(page)).toBeVisible({ timeout: 10_000 });
  await page.getByRole('button', { name: 'Next' }).click();
  await expect(dialog(page)).toHaveAccessibleName(TITLES[1] as string);
});

test('at phone width the dialog docks to the bottom with 44 px controls', async ({
  page,
  isMobile,
}) => {
  test.skip(!isMobile, 'phone layout only');
  await page.goto('/');
  await expect(dialog(page)).toBeVisible({ timeout: 10_000 });
  const box = await dialog(page).boundingBox();
  const viewport = page.viewportSize();
  expect(box !== null && viewport !== null && box.y + box.height > viewport.height * 0.6).toBe(
    true,
  );
  for (const name of ['Next', 'Skip tour']) {
    const button = await page.getByRole('button', { name }).boundingBox();
    expect(button?.height ?? 0, name).toBeGreaterThanOrEqual(44);
  }
  await expectNoSideScroll(page);
});

test('on wider screens the dialog stays clear of the personal panel and the time window', async ({
  page,
  isMobile,
}) => {
  test.skip(isMobile, 'the phone dock sits at the bottom by design');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(dialog(page)).toBeVisible({ timeout: 10_000 });
  for (let i = 0; i < TITLES.length; i += 1) {
    await expect(dialog(page)).toHaveAccessibleName(TITLES[i] as string);
    const ring = page.getByTestId('tour-ring');
    // Steps 2 and 5 point at small side or header targets; the others point at big content cards.
    if (i === 1 || i === 4) {
      await expect(ring).toBeVisible();
      await page.waitForTimeout(400);
      const [ringBox, dialogBox] = await Promise.all([
        ring.boundingBox(),
        dialog(page).boundingBox(),
      ]);
      if (ringBox !== null && dialogBox !== null) {
        const apart =
          dialogBox.x >= ringBox.x + ringBox.width ||
          dialogBox.x + dialogBox.width <= ringBox.x ||
          dialogBox.y >= ringBox.y + ringBox.height ||
          dialogBox.y + dialogBox.height <= ringBox.y;
        expect(apart, `step ${String(i + 1)} dialog clear of the ring`).toBe(true);
      }
    }
    if (i < TITLES.length - 1) await page.getByRole('button', { name: 'Next' }).click();
  }
});
