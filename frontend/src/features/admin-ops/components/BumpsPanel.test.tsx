import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { auditEntries, bumpedPosts } from '../mocks';
import { BumpsPanel } from './BumpsPanel';

describe('BumpsPanel', () => {
  it('lists bumped posts with their counts, dates and keys, and flags stale ones', async () => {
    renderWithProviders(<BumpsPanel />);
    const list = await screen.findByRole('list', { name: 'Bumped posts' });
    const [first, stale] = within(list).getAllByRole('listitem');
    expect(first).toHaveTextContent('New personal best for Ike Hadley: 46.');
    expect(first).toHaveTextContent('4 bumps · Sep 27, 2026');
    expect(first).toHaveTextContent('k-pb-3');
    expect(stale).toHaveTextContent('1 bump · Sep 13, 2026 · no longer on a Sheet');
  });

  it('wipes only after a second, explicit tap, then refreshes the list', async () => {
    const posts = [...bumpedPosts];
    const wiped: string[] = [];
    server.use(
      http.get('*/api/admin/sheet/bumps', () => HttpResponse.json(posts)),
      http.delete('*/api/admin/sheet/bumps/:postKey', ({ params }) => {
        const key = String(params['postKey']);
        wiped.push(key);
        posts.splice(
          posts.findIndex((p) => p.post_key === key),
          1,
        );
        return HttpResponse.json({ post_key: key, wiped: 4 });
      }),
      http.get('*/api/admin/audit', () => HttpResponse.json(auditEntries)),
    );
    const { user } = renderWithProviders(<BumpsPanel />);
    const list = await screen.findByRole('list', { name: 'Bumped posts' });
    const first = within(list).getAllByRole('listitem')[0] as HTMLElement;
    await user.click(within(first).getByRole('button', { name: 'Wipe bumps' }));
    expect(wiped).toEqual([]);
    await user.click(within(first).getByRole('button', { name: 'Keep them' }));
    await user.click(within(first).getByRole('button', { name: 'Wipe bumps' }));
    await user.click(within(first).getByRole('button', { name: 'Yes, wipe 4 bumps' }));
    await waitFor(() =>
      expect(screen.queryByText('New personal best for Ike Hadley: 46.')).toBeNull(),
    );
    expect(screen.getByText('Trophy retired_trophy, 2026-09-13')).toBeInTheDocument();
    expect(wiped).toEqual(['k-pb-3']);
  });

  it('shows a refused wipe next to the post', async () => {
    server.use(
      http.delete('*/api/admin/sheet/bumps/:postKey', () =>
        HttpResponse.json({ error: { code: 'forbidden', message: 'Forbidden' } }, { status: 403 }),
      ),
    );
    const { user } = renderWithProviders(<BumpsPanel />);
    const list = await screen.findByRole('list', { name: 'Bumped posts' });
    const first = within(list).getAllByRole('listitem')[0] as HTMLElement;
    await user.click(within(first).getByRole('button', { name: 'Wipe bumps' }));
    await user.click(within(first).getByRole('button', { name: 'Yes, wipe 4 bumps' }));
    expect(await within(first).findByRole('alert')).toHaveTextContent(
      'Admins only — sign in with the admin password.',
    );
  });

  it('says when nothing has been bumped', async () => {
    server.use(http.get('*/api/admin/sheet/bumps', () => HttpResponse.json([])));
    renderWithProviders(<BumpsPanel />);
    expect(await screen.findByText('No bumps yet.')).toBeInTheDocument();
  });

  it('shows a refused list', async () => {
    server.use(
      http.get('*/api/admin/sheet/bumps', () =>
        HttpResponse.json({ error: { code: 'forbidden', message: 'Forbidden' } }, { status: 403 }),
      ),
    );
    renderWithProviders(<BumpsPanel />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Admins only');
  });
});
