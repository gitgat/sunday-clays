import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { useFeatures } from '../../../lib/features';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { featureSwitches, pageCacheStatus } from '../mocks';
import { FeaturesPage } from './FeaturesPage';

function rowOf(label: string): HTMLElement {
  const row = screen.getByRole('switch', { name: label }).closest('li');
  if (row === null) throw new Error(`no row for ${label}`);
  return row;
}

/** Keeps GET /api/features observed, as the nav does, so an invalidation refetches it. */
function FeaturesProbe() {
  useFeatures();
  return null;
}

describe('FeaturesPage', () => {
  it('lists exactly the seven switches with labels, descriptions and dates', async () => {
    renderWithProviders(<FeaturesPage />, { role: 'admin', route: '/admin/features' });
    expect(screen.getByRole('heading', { level: 1, name: 'Features' })).toBeInTheDocument();
    const launch = await screen.findByRole('region', { name: 'Launch switches' });
    const switches = within(launch).getAllByRole('switch');
    expect(switches).toHaveLength(7);
    expect(switches.map((s) => s.textContent)).toEqual(
      featureSwitches.filter((f) => f.kind === 'feature').map((f) => f.label),
    );
    const first = rowOf('Link previews');
    expect(within(first).getByText('Changed Oct 2, 2026')).toBeInTheDocument();
    expect(switches[0]).toHaveAttribute('aria-checked', 'true');
    const second = rowOf('Welcome tour and glossary');
    expect(within(second).getByText('Never changed')).toBeInTheDocument();
  });

  it('flips a switch with a PUT, then refetches the list and the switch set', async () => {
    const puts: unknown[] = [];
    let featureGets = 0;
    server.use(
      http.get('*/api/features', () => {
        featureGets += 1;
        return HttpResponse.json({ switches: {} });
      }),
      http.get('*/api/admin/features', () =>
        HttpResponse.json(
          featureSwitches.map((row) =>
            row.key === 'pwa' && puts.length > 0 ? { ...row, enabled: true } : row,
          ),
        ),
      ),
      http.put('*/api/admin/features/:key', async ({ params, request }) => {
        puts.push({ key: params.key, body: await request.json() });
        return HttpResponse.json({
          ...featureSwitches[3],
          enabled: true,
          updated_on: '2026-10-02',
        });
      }),
    );
    const { user } = renderWithProviders(
      <>
        <FeaturesPage />
        <FeaturesProbe />
      </>,
      { role: 'admin' },
    );
    const toggle = await screen.findByRole('switch', { name: 'Add to Home Screen' });
    await waitFor(() => expect(featureGets).toBe(1));
    expect(toggle).toHaveAttribute('aria-checked', 'false');
    await user.click(toggle);
    await waitFor(() => expect(puts).toEqual([{ key: 'pwa', body: { enabled: true } }]));
    await waitFor(() =>
      expect(screen.getByRole('switch', { name: 'Add to Home Screen' })).toHaveAttribute(
        'aria-checked',
        'true',
      ),
    );
    await waitFor(() => expect(featureGets).toBe(2));
  });

  it('disables every switch while a change is being saved', async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.put('*/api/admin/features/:key', async () => {
        await gate;
        return HttpResponse.json({ ...featureSwitches[3], enabled: true });
      }),
    );
    const { user } = renderWithProviders(<FeaturesPage />, { role: 'admin' });
    await user.click(await screen.findByRole('switch', { name: 'Add to Home Screen' }));
    await waitFor(() => {
      for (const toggle of screen.getAllByRole('switch')) expect(toggle).toBeDisabled();
    });
    release();
    await waitFor(() => {
      for (const toggle of screen.getAllByRole('switch')) expect(toggle).toBeEnabled();
    });
  });

  it('says so when a flip fails, naming the switch', async () => {
    server.use(
      http.put('*/api/admin/features/:key', () =>
        HttpResponse.json({ error: { code: 'x', message: 'x' } }, { status: 500 }),
      ),
    );
    const { user } = renderWithProviders(<FeaturesPage />, { role: 'admin' });
    await user.click(await screen.findByRole('switch', { name: 'Summary card' }));
    expect(
      await screen.findByText('Could not change Summary card. Try again.'),
    ).toBeInTheDocument();
  });

  it('says so when the list cannot load', async () => {
    server.use(http.get('*/api/admin/features', () => HttpResponse.error()));
    renderWithProviders(<FeaturesPage />, { role: 'admin' });
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the switches.');
  });
});

describe('FeaturesPage infrastructure group', () => {
  it('lists the page cache under Infrastructure with its status line and no badge', async () => {
    renderWithProviders(<FeaturesPage />, { role: 'admin' });
    const infra = await screen.findByRole('region', { name: 'Infrastructure' });
    expect(
      within(infra).getByText(
        'Behind-the-scenes settings. They change how fast pages open, never what they show.',
      ),
    ).toBeInTheDocument();
    expect(within(infra).getByRole('switch', { name: 'Page cache' })).toHaveAttribute(
      'aria-checked',
      'true',
    );
    expect(
      await within(infra).findByText(
        '1,240 pages stored · 38 MB · last refreshed Oct 2, 2026 (27 pages in 41 s)',
      ),
    ).toBeInTheDocument();
    expect(within(infra).queryByText('Admin preview')).not.toBeInTheDocument();
  });

  it('disables the toggle when the deployment forces the cache off', async () => {
    server.use(
      http.get('*/api/admin/page-cache', () =>
        HttpResponse.json({ ...pageCacheStatus, enabled: false, forced_off: true }),
      ),
    );
    renderWithProviders(<FeaturesPage />, { role: 'admin' });
    const infra = await screen.findByRole('region', { name: 'Infrastructure' });
    const status = await within(infra).findByText('Turned off on the server');
    const toggle = within(infra).getByRole('switch', { name: 'Page cache' });
    expect(toggle).toBeDisabled();
    expect(toggle).toHaveAttribute('aria-describedby', status.id);
    expect(status.id).not.toBe('');
  });

  it('shows plain "Status unavailable" while loading or when the status fails', async () => {
    server.use(http.get('*/api/admin/page-cache', () => HttpResponse.error()));
    renderWithProviders(<FeaturesPage />, { role: 'admin' });
    const infra = await screen.findByRole('region', { name: 'Infrastructure' });
    expect(await within(infra).findByText('Status unavailable')).toBeInTheDocument();
    expect(within(infra).queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(within(infra).getByRole('switch', { name: 'Page cache' })).toBeEnabled();
  });
});
