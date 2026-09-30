import { defineConfig, devices } from '@playwright/test';

import { ADMIN_STATE, VIEWER_STATE } from './e2e/authState';

/**
 * E2E against the compose stack on http://localhost:8080 (compose.test.yaml in CI). A local run
 * against a stack on another host port (E2E_PORT) sets E2E_BASE_URL to match; see CONTRIBUTING.md.
 * Both projects are Chromium: WebKit drops Secure cookies on http://localhost, so an iPhone
 * preset would break login. Only Plan 01 T4, Plan 04 T1 and Plan 08 T5a edit this file (C10).
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8080',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.ts$/ },
    {
      name: 'desktop',
      dependencies: ['setup'],
      testIgnore: /admin-mutations\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        storageState: VIEWER_STATE,
      },
    },
    {
      name: 'mobile',
      dependencies: ['setup'],
      testIgnore: /admin-mutations\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 390, height: 844 },
        deviceScaleFactor: 3,
        isMobile: true,
        hasTouch: true,
        storageState: VIEWER_STATE,
      },
    },
    {
      // Plan 08 T5a (D17): mutating admin specs run once, desktop only, one worker, after every
      // read-only spec. A re-run on the same stack is fine (a rolled-back variant is not a duplicate); only a run
      // that died between commit and roll back needs a fresh stack (`down -v`).
      name: 'admin-mutations',
      testMatch: /admin-mutations\.spec\.ts/,
      dependencies: ['mobile', 'desktop'],
      workers: 1,
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        storageState: ADMIN_STATE,
      },
    },
  ],
});
