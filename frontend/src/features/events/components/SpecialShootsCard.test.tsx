import { screen, within } from '@testing-library/react';
import { http, HttpResponse, type JsonBodyType } from 'msw';
import { describe, expect, it } from 'vitest';
import { expectExplainer } from '../../../test/charts';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { hadleySpecials } from '../../shooters/mocks';
import { SpecialShootsCard } from './SpecialShootsCard';

function withSpecials(body: JsonBodyType, status = 200) {
  server.use(http.get('*/api/shooters/:id/special', () => HttpResponse.json(body, { status })));
}

describe('SpecialShootsCard', () => {
  it('lists each special shoot newest first, tagged with its targets, linking to the Sunday', async () => {
    withSpecials([
      { round_id: 8001, event_date: '2025-06-15', label: 'Flurry', target_total: 75, score: 61 },
      ...hadleySpecials,
    ]);
    renderWithProviders(<SpecialShootsCard shooterId={3} />, { route: '/shooters/3?rt=sporting' });
    const list = await screen.findByRole('list', { name: 'Special shoots' });
    const items = within(list).getAllByRole('listitem');
    expect(items[0]).toHaveTextContent('Sep 20, 2026');
    expect(items[0]).toHaveTextContent('3-Bird Shoot · Special · 60');
    expect(items[0]).toHaveTextContent('55 of 60');
    expect(items[1]).toHaveTextContent('Flurry · Special · 75');
    expect(items[1]).toHaveTextContent('61 of 75');
    expect(within(items[0] as HTMLElement).getByRole('link')).toHaveAttribute(
      'href',
      '/events/2026-09-20?rt=sporting',
    );
    await expectExplainer(
      screen.getByRole('region', { name: 'Special shoots' }),
      'About special shoots',
      { read: true },
    );
  });

  it('says nothing for a shooter with no special shoot, or while it cannot load', async () => {
    withSpecials([]);
    const { container } = renderWithProviders(<SpecialShootsCard shooterId={3} />);
    await new Promise((r) => setTimeout(r, 50));
    expect(container).toBeEmptyDOMElement();
  });

  it('stays silent when the list fails to load', async () => {
    withSpecials({ error: { code: 'x', message: 'nope' } }, 500);
    const { container } = renderWithProviders(<SpecialShootsCard shooterId={3} />);
    await new Promise((r) => setTimeout(r, 50));
    expect(container).toBeEmptyDOMElement();
  });

  it('tags a special shoot without a name from the sheet by its targets alone', async () => {
    withSpecials([
      { round_id: 8002, event_date: '2025-07-06', label: null, target_total: 40, score: 33 },
    ]);
    renderWithProviders(<SpecialShootsCard shooterId={3} />);
    const item = within(await screen.findByRole('list', { name: 'Special shoots' })).getByRole(
      'listitem',
    );
    expect(item).toHaveTextContent('Special · 40');
    expect(item).not.toHaveTextContent('·  ·');
    expect(item).toHaveTextContent('33 of 40');
  });
});
