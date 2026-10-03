import { expect, test as base } from '@playwright/test';

/**
 * Shared `test`/`expect` for every spec (C10): a test fails if the page throws an uncaught
 * error or the browser reports a Content Security Policy violation.
 *
 * Plan 19: `tourSeen` and `installTipSeen` (both default true) mark the tour as done and the
 * install tip as dismissed before every page load; the tour and PWA specs set them false.
 */
export const test = base.extend<{
  pageProblems: string[];
  tourSeen: boolean;
  installTipSeen: boolean;
  seenFlags: boolean;
}>({
  tourSeen: [true, { option: true }],
  installTipSeen: [true, { option: true }],
  seenFlags: [
    async ({ page, tourSeen, installTipSeen }, use) => {
      await page.addInitScript(
        ({ tour, tip }) => {
          try {
            if (tour) localStorage.setItem('sc.tour.v1', 'done');
            if (tip) localStorage.setItem('sc.install.dismissed', '1');
          } catch {
            // storage blocked: the spec meets the tour and the tip, as a real visitor would
          }
        },
        { tour: tourSeen, tip: installTipSeen },
      );
      await use(tourSeen);
    },
    { auto: true },
  ],
  pageProblems: [
    async ({ page }, use) => {
      const problems: string[] = [];
      page.on('pageerror', (error) => problems.push(`pageerror: ${error.message}`));
      page.on('console', (message) => {
        if (/Content Security Policy/i.test(message.text())) {
          problems.push(`csp: ${message.text()}`);
        }
      });
      await use(problems);
      expect(problems, 'uncaught page errors and CSP violations').toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };
