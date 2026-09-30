import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { clubRegulars } from '../mocks';
import { RegularsCard } from './RegularsCard';

describe('RegularsCard', () => {
  it('lists core regulars with their share of held events and lapsed regulars with their last outing', async () => {
    server.use(http.get('*/api/club/regulars', () => HttpResponse.json(clubRegulars)));
    renderWithProviders(<RegularsCard />);
    const core = await screen.findByRole('region', { name: 'Core regulars' });
    expect(within(core).getByText('Core regulars (2)')).toBeInTheDocument();
    expect(within(core).getByRole('link', { name: 'Abernathy, Preston' })).toHaveAttribute(
      'href',
      '/shooters/7',
    );
    expect(within(core).getByText('46 of 48 Sundays')).toBeInTheDocument();
    const lapsed = screen.getByRole('region', { name: 'Lapsed regulars' });
    expect(within(lapsed).getByRole('link', { name: 'Nesbitt, Rolf' })).toHaveAttribute(
      'href',
      '/shooters/58',
    );
    expect(within(lapsed).getByText('last out May 31, 2026')).toBeInTheDocument();
  });

  it('labels each list with its fixed period and says the time window does not change it', async () => {
    server.use(http.get('*/api/club/regulars', () => HttpResponse.json(clubRegulars)));
    renderWithProviders(<RegularsCard />, { route: '/club?w=3m' });
    const core = await screen.findByRole('region', { name: 'Core regulars' });
    expect(within(core).getByText('Last 12 months · to Sep 27')).toBeVisible();
    const lapsed = screen.getByRole('region', { name: 'Lapsed regulars' });
    expect(within(lapsed).getByText('Last 90 days · to Sep 27')).toBeVisible();
    expect(screen.getByRole('region', { name: 'Regulars' })).toHaveTextContent(
      "the time window doesn't apply",
    );
  });

  it('shows 8 names, then "Show all N" and "Show fewer"', async () => {
    const core = Array.from({ length: 11 }, (_, i) => ({
      shooter_id: 100 + i,
      display_name: `Shooter, ${String(i)}`,
      events_attended: 40 - i,
      share: 0.8,
    }));
    server.use(http.get('*/api/club/regulars', () => HttpResponse.json({ ...clubRegulars, core })));
    const { user } = renderWithProviders(<RegularsCard />);
    const list = await screen.findByRole('region', { name: 'Core regulars' });
    expect(within(list).getAllByRole('link')).toHaveLength(8);
    expect(within(list).getByText('Core regulars (11)')).toBeVisible();
    await user.click(within(list).getByRole('button', { name: 'Show all 11' }));
    expect(within(list).getAllByRole('link')).toHaveLength(11);
    await user.click(within(list).getByRole('button', { name: 'Show fewer' }));
    expect(within(list).getAllByRole('link')).toHaveLength(8);
    // The short lapsed list has no toggle.
    expect(
      within(screen.getByRole('region', { name: 'Lapsed regulars' })).queryByRole('button', {
        name: /Show/,
      }),
    ).toBeNull();
  });

  it('keeps the global round-type filter on the shooter links', async () => {
    server.use(http.get('*/api/club/regulars', () => HttpResponse.json(clubRegulars)));
    renderWithProviders(<RegularsCard />, { route: '/club?rt=super_sporting' });
    const core = await screen.findByRole('region', { name: 'Core regulars' });
    expect(within(core).getByRole('link', { name: 'Abernathy, Preston' })).toHaveAttribute(
      'href',
      '/shooters/7?rt=super_sporting',
    );
    const lapsed = screen.getByRole('region', { name: 'Lapsed regulars' });
    expect(within(lapsed).getByRole('link', { name: 'Nesbitt, Rolf' })).toHaveAttribute(
      'href',
      '/shooters/58?rt=super_sporting',
    );
  });

  it('says none when a list is empty', async () => {
    server.use(
      http.get('*/api/club/regulars', () => HttpResponse.json({ ...clubRegulars, lapsed: [] })),
    );
    renderWithProviders(<RegularsCard />);
    const lapsed = await screen.findByRole('region', { name: 'Lapsed regulars' });
    expect(within(lapsed).getByText('None right now')).toBeInTheDocument();
  });

  it('shows a load failure', async () => {
    server.use(
      http.get('*/api/club/regulars', () =>
        HttpResponse.json(
          { error: { code: 'internal', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
    );
    renderWithProviders(<RegularsCard />);
    expect(await screen.findByText("Couldn't load regulars")).toBeInTheDocument();
  });
});
