import { expect, test as base } from '@playwright/test';

/**
 * Shared `test`/`expect` for every spec (C10): a test fails if the page throws an uncaught
 * error or the browser reports a Content Security Policy violation.
 *
 * Plan 19: `tourSeen` (default true) marks the first-visit tour as done before every page load,
 * so specs never meet the tour; the tour spec sets it false.
 */
export const test = base.extend<{ pageProblems: string[]; tourSeen: boolean; seenFlags: boolean }>({
  tourSeen: [true, { option: true }],
  seenFlags: [
    async ({ page, tourSeen }, use) => {
      if (tourSeen) {
        await page.addInitScript(() => {
          try {
            localStorage.setItem('sc.tour.v1', 'done');
          } catch {
            // storage blocked: the spec meets the tour, as a real visitor would
          }
        });
      }
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
