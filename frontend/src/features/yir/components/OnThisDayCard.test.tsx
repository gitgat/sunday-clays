import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { expectExplainer } from '../../../test/charts';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { ON_THIS_DAY } from '../mocks';
import { OnThisDayCard } from './OnThisDayCard';

describe('OnThisDayCard', () => {
  it('lists the Sundays 1, 2 and 3 years back with every tied winner', async () => {
    server.use(http.get('*/api/on-this-day', () => HttpResponse.json(ON_THIS_DAY)));
    renderWithProviders(<OnThisDayCard />);
    const card = screen.getByRole('region', { name: 'On this day' });
    const link = await within(card).findByRole('link', { name: '1 year ago · Sun, Sep 28, 2025' });
    expect(link).toHaveAttribute('href', '/events/2025-09-28');
    expect(within(card).getByText('23 shooters · won by Rookwood, Derek (45)')).toBeInTheDocument();
    expect(
      within(card).getByText(
        '25 shooters · won by McMurtry, Zeb, Yoder, Gavin and Blakeslee, Ryder (40)',
      ),
    ).toBeInTheDocument();
    expect(within(card).getByText('30 shooters (attendance only)')).toBeInTheDocument();
  });

  it('keeps the round-type filter on its links and explains itself', async () => {
    server.use(http.get('*/api/on-this-day', () => HttpResponse.json(ON_THIS_DAY)));
    renderWithProviders(<OnThisDayCard />, { route: '/?rt=super_sporting' });
    const card = screen.getByRole('region', { name: 'On this day' });
    const link = await within(card).findByRole('link', { name: '1 year ago · Sun, Sep 28, 2025' });
    expect(link).toHaveAttribute('href', '/events/2025-09-28?rt=super_sporting');
    await expectExplainer(card, 'About this card');
  });

  it('handles events without scores or head count, and quiet dates', async () => {
    const [first] = ON_THIS_DAY.items;
    server.use(
      http.get('*/api/on-this-day', () =>
        HttpResponse.json({
          on: '2026-03-01',
          items: [{ ...first, has_scores: false, head_count: null, n_shooters: 0, winners: [] }],
        }),
      ),
    );
    renderWithProviders(<OnThisDayCard />);
    expect(await screen.findByText('No scores recorded')).toBeInTheDocument();
  });

  it('shows the top score when no winner is recorded', async () => {
    const [first] = ON_THIS_DAY.items;
    server.use(
      http.get('*/api/on-this-day', () =>
        HttpResponse.json({
          on: '2026-03-01',
          items: [{ ...first, has_scores: true, n_shooters: 12, top_score: 45, winners: [] }],
        }),
      ),
    );
    renderWithProviders(<OnThisDayCard />);
    expect(await screen.findByText('12 shooters · top score 45')).toBeInTheDocument();
  });

  it('says when nothing happened near this date', async () => {
    server.use(
      http.get('*/api/on-this-day', () => HttpResponse.json({ on: '2020-01-05', items: [] })),
    );
    renderWithProviders(<OnThisDayCard />);
    expect(
      await screen.findByText('No Sunday near this date in the last three years.'),
    ).toBeInTheDocument();
  });

  it('reports a failed request', async () => {
    server.use(
      http.get('*/api/on-this-day', () =>
        HttpResponse.json({ error: { code: 'internal', message: 'x' } }, { status: 500 }),
      ),
    );
    renderWithProviders(<OnThisDayCard />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load On this day.');
  });
});
