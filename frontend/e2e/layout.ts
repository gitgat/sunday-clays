import type { Page } from '@playwright/test';

import { expect } from './fixtures';

/**
 * Wait until every lazy section and query on the page has finished loading, so layout checks
 * measure the final page and not a half-rendered one.
 */
export async function whenSettled(page: Page): Promise<void> {
  // Placeholders hold their space until the feeds arrive; give slow CI runs room to load them.
  const settled = { timeout: 15_000 };
  await expect(page.getByRole('status')).toHaveCount(0, settled);
  await expect(page.locator('[aria-busy="true"]')).toHaveCount(0, settled);
}

export async function expectNoSideScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(overflow.scroll, 'page scrollWidth').toBeLessThanOrEqual(overflow.client);
}

/** Every link and button in the page body is at least 44 × 44 px. */
export async function expectTapTargets(page: Page): Promise<void> {
  const small = await page
    .locator('main')
    .locator('a:visible, button:visible')
    .evaluateAll((elements) =>
      elements.flatMap((el) => {
        const { width, height } = el.getBoundingClientRect();
        const name = el.textContent?.trim() || el.getAttribute('aria-label');
        return width < 44 || height < 44
          ? [`${name}: ${Math.round(width)}×${Math.round(height)}`]
          : [];
      }),
    );
  expect(small, 'tap targets under 44 px').toEqual([]);
}

/** No card title is cut off with an ellipsis. */
export async function expectTitlesUntruncated(page: Page): Promise<void> {
  await expect
    .poll(
      () =>
        page
          .locator('main h2')
          .evaluateAll((elements) =>
            elements.flatMap((el) =>
              el.scrollWidth > el.clientWidth ? [`${el.textContent ?? ''}`] : [],
            ),
          ),
      { message: 'truncated titles' },
    )
    .toEqual([]);
}
