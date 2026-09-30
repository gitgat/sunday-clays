/** Storage-state files written by the `setup` project (e2e/auth.setup.ts); gitignored. */
export const VIEWER_STATE = 'e2e/.auth/viewer.json';
export const ADMIN_STATE = 'e2e/.auth/admin.json';

/** The e2e login passwords, exported by CI (C11 `e2e` job) or by hand for a local run. */
export function e2ePassword(role: 'viewer' | 'admin'): string {
  const name = role === 'viewer' ? 'E2E_VIEWER_PASSWORD' : 'E2E_ADMIN_PASSWORD';
  const value = process.env[name];
  if (!value) throw new Error(`${name} must be set for the e2e run`);
  return value;
}
