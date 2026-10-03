import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { expectChartControls, expectExplainer } from '../../../test/charts';
import { LAZY_CHART } from '../../../test/lazyChart';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { clubMilestones } from '../mocks';
import { MilestonesSection } from './MilestonesSection';

describe('MilestonesSection', () => {
  it('lists milestones grouped by metric, newest first, linking to their Sunday', async () => {
    renderWithProviders(<MilestonesSection />, { route: '/club' });
    const list = await screen.findByRole('region', { name: 'Club milestones' });
    const link = await within(list).findByRole('link', {
      name: '350,000 clays thrown — Sep 13, 2026',
    });
    expect(link).toHaveAttribute('href', '/events/2026-09-13');
    expect(within(list).getByText('On the first Sunday on record')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: 'Milestones' })).toBeInTheDocument();
  });

  it('draws the totals chart with Table, CSV and an explainer', async () => {
    renderWithProviders(<MilestonesSection />, { route: '/club' });
    // The loading card carries the same title, so wait for the chart's own controls.
    await screen.findByRole('button', { name: 'CSV' }, LAZY_CHART);
    const chart = screen.getByRole('region', { name: 'Club totals over time' });
    expectChartControls(chart);
    await expectExplainer(chart, 'About this chart', { read: true });
  });

  it('has no heading, no cards and no request for a viewer while off', async () => {
    let asked = 0;
    server.use(
      http.get('*/api/features', () => HttpResponse.json({ switches: {} })),
      http.get('*/api/club/milestones', () => {
        asked += 1;
        return HttpResponse.json(clubMilestones);
      }),
    );
    const { container } = renderWithProviders(<MilestonesSection />, { route: '/club' });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
    expect(asked).toBe(0);
  });

  it('says "No milestones yet." when there are none', async () => {
    server.use(
      http.get('*/api/club/milestones', () =>
        HttpResponse.json({ ...clubMilestones, milestones: [], latest: null, series: [] }),
      ),
    );
    renderWithProviders(<MilestonesSection />, { route: '/club' });
    expect(await screen.findByText('No milestones yet.')).toBeInTheDocument();
  });
});
