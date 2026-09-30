import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { expect, test as setup } from '@playwright/test';
import type { APIRequestContext } from '@playwright/test';

import { ADMIN_STATE, VIEWER_STATE, e2ePassword } from './authState';

// Resolved from this module's location, not the working directory.
const FIXTURES_DIR = fileURLToPath(new URL('../../backend/tests/fixtures/', import.meta.url));
const XLSX_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
const SEED = [
  { kind: 'scores', file: 'scores_2026-09-27.xlsx' },
  { kind: 'stations', file: 'stations_2026-09-27.xlsx' },
] as const;

interface ImportRow {
  id: number;
  kind: string;
  status: string;
}

interface JobRow {
  status: string;
  error?: string | null;
}

async function waitForJob(request: APIRequestContext, jobId: number): Promise<void> {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    const response = await request.get(`/api/admin/jobs/${jobId}`);
    expect(response.status()).toBe(200);
    const job = (await response.json()) as JobRow;
    if (job.status === 'done') return;
    if (job.status === 'failed') throw new Error(`job ${jobId} failed: ${job.error ?? ''}`);
    await new Promise((resolveWait) => setTimeout(resolveWait, 1_000));
  }
  throw new Error(`job ${jobId} was not done after 120 s`);
}

async function seedFixtureImports(request: APIRequestContext): Promise<void> {
  const listed = await request.get('/api/admin/imports');
  expect(listed.status()).toBe(200);
  const imports = (await listed.json()) as ImportRow[];
  for (const { kind, file } of SEED) {
    if (imports.some((row) => row.kind === kind && row.status === 'committed')) continue;
    const upload = await request.post('/api/admin/imports', {
      multipart: {
        file: { name: file, mimeType: XLSX_TYPE, buffer: readFileSync(join(FIXTURES_DIR, file)) },
      },
    });
    expect(upload.status(), await upload.text()).toBe(200);
    const { import_id: importId } = (await upload.json()) as { import_id: number };
    const commit = await request.post(`/api/admin/imports/${importId}/commit`, {
      data: { confirm_removals: false },
    });
    expect(commit.status(), await commit.text()).toBe(200);
    const { job_id: jobId } = (await commit.json()) as { job_id: number };
    await waitForJob(request, jobId);
  }
}

setup('log in as viewer', async ({ request }) => {
  const response = await request.post('/api/auth/login', {
    data: { password: e2ePassword('viewer') },
  });
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ role: 'viewer' });
  await request.storageState({ path: VIEWER_STATE });
});

setup('log in as admin and seed the fixture imports', async ({ request }) => {
  setup.setTimeout(300_000);
  const response = await request.post('/api/auth/login', {
    data: { password: e2ePassword('admin') },
  });
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ role: 'admin' });
  await request.storageState({ path: ADMIN_STATE });
  await seedFixtureImports(request);
});
