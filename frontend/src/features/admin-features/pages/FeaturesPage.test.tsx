import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { useFeatures } from '../../../lib/features';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { featureSwitches } from '../mocks';
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
  it('lists exactly the six switches with labels, descriptions and dates', async () => {
    renderWithProviders(<FeaturesPage />, { role: 'admin', route: '/admin/features' });
    expect(screen.getByRole('heading', { level: 1, name: 'Features' })).toBeInTheDocument();
    const switches = await screen.findAllByRole('switch');
    expect(switches.map((s) => s.textContent)).toEqual(featureSwitches.map((f) => f.label));
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
