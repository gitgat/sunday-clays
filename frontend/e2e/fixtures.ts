import { expect, test as base } from '@playwright/test';

/**
 * Shared `test`/`expect` for every spec (C10): a test fails if the page throws an uncaught
 * error or the browser reports a Content Security Policy violation.
 */
export const test = base.extend<{ pageProblems: string[] }>({
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
