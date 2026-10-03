import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { featureSwitches } from '../mocks';
import { FeaturesPage } from './FeaturesPage';

describe('FeaturesPage', () => {
  it('lists exactly the six switches with labels, descriptions and dates', async () => {
    renderWithProviders(<FeaturesPage />, { role: 'admin', route: '/admin/features' });
    expect(screen.getByRole('heading', { level: 1, name: 'Features' })).toBeInTheDocument();
    const switches = await screen.findAllByRole('switch');
    expect(switches.map((s) => s.textContent)).toEqual(featureSwitches.map((f) => f.label));
    const first = screen.getByRole('listitem', { name: 'Link previews' });
    expect(within(first).getByText('Changed Oct 2, 2026')).toBeInTheDocument();
    expect(switches[0]).toHaveAttribute('aria-checked', 'true');
    const second = screen.getByRole('listitem', { name: 'Welcome tour and glossary' });
    expect(within(second).getByText('Never changed')).toBeInTheDocument();
  });

  it('flips a switch with a PUT and refetches the list', async () => {
    const puts: unknown[] = [];
    server.use(
      http.put('*/api/admin/features/:key', async ({ params, request }) => {
        puts.push({ key: params.key, body: await request.json() });
        return HttpResponse.json({
          ...featureSwitches[3],
          enabled: true,
          updated_on: '2026-10-02',
        });
      }),
    );
    const { user } = renderWithProviders(<FeaturesPage />, { role: 'admin' });
    await user.click(await screen.findByRole('switch', { name: 'Add to Home Screen' }));
    expect(puts).toEqual([{ key: 'pwa', body: { enabled: true } }]);
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
