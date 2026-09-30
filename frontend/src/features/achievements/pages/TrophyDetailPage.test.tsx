import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { Link, MemoryRouter, Route, Routes } from 'react-router';
import { describe, expect, it } from 'vitest';
import { expectChartControls, expectExplainer } from '../../../test/charts';
import { server } from '../../../test/msw/server';
import { trophyDetailFixture } from '../mocks';
import { TrophyDetailPage } from './TrophyDetailPage';

function renderAt(url: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/achievements/:code" element={<TrophyDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('TrophyDetailPage', () => {
  it('opens the next trophy with its holders collapsed again', async () => {
    const [first] = trophyDetailFixture.holders;
    if (!first) throw new Error('fixture has a holder');
    const holders = Array.from({ length: 12 }, (_, i) => ({ ...first, shooter_id: 200 + i }));
    server.use(
      http.get('*/api/achievements/:code', () =>
        HttpResponse.json({ ...trophyDetailFixture, holders }),
      ),
    );
    const user = userEvent.setup();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/achievements/a']}>
          <Link to="/achievements/b">other</Link>
          <Routes>
            <Route path="/achievements/:code" element={<TrophyDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await user.click(await screen.findByRole('button', { name: 'Show all 12 holders' }));
    expect(
      within(screen.getByRole('list', { name: 'Holders' })).getAllByRole('listitem'),
    ).toHaveLength(12);
    await user.click(screen.getByRole('link', { name: 'other' }));
    expect(await screen.findByRole('button', { name: 'Show all 12 holders' })).toBeInTheDocument();
  });

  it('shows the trophy and every holder', async () => {
    renderAt('/achievements/clays_broken%3A3');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Clays Broken' }),
    ).toBeInTheDocument();
    expect(screen.getByText('1,000 clays broken')).toBeInTheDocument();
    const holders = screen.getByRole('list', { name: 'Holders' });
    expect(within(holders).getAllByRole('listitem')).toHaveLength(2);
    expect(within(holders).getByRole('link', { name: 'Hadley, Ike' })).toHaveAttribute(
      'href',
      '/shooters/12',
    );
    expect(within(holders).getByText('In memoriam')).toBeInTheDocument();
  });

  it('requests the decoded trophy code', async () => {
    let requested = '';
    server.use(
      http.get('*/api/achievements/:code', ({ params }) => {
        requested = decodeURIComponent(String(params.code));
        return HttpResponse.json(trophyDetailFixture);
      }),
    );
    renderAt('/achievements/clays_broken%3A3');
    await screen.findByRole('heading', { level: 1, name: 'Clays Broken' });
    expect(requested).toBe('clays_broken:3');
  });

  it('exposes Table and CSV controls on every chart', async () => {
    renderAt('/achievements/clays_broken%3A3');
    await screen.findByRole('heading', { level: 1, name: 'Clays Broken' });
    expectChartControls(screen.getByRole('region', { name: 'Holders over time' }));
    expect(screen.getAllByRole('button', { name: /table/i })).toHaveLength(1);
    await expectExplainer(screen.getByRole('region', { name: 'Holders over time' }), undefined, {
      read: true,
    });
  });

  it('says "1 holder" for a single holder', async () => {
    server.use(
      http.get('*/api/achievements/:code', () =>
        HttpResponse.json({
          ...trophyDetailFixture,
          trophy: { ...trophyDetailFixture.trophy, holders: 1 },
        }),
      ),
    );
    renderAt('/achievements/clays_broken%3A3');
    expect(await screen.findByText(/^1 holder ·/)).toBeInTheDocument();
  });

  it('shows a one-off trophy without a tier label and counts repeats', async () => {
    const [holder] = trophyDetailFixture.holders;
    if (!holder) throw new Error('fixture has holders');
    server.use(
      http.get('*/api/achievements/:code', () =>
        HttpResponse.json({
          trophy: { ...trophyDetailFixture.trophy, code: 'welcome_back', label: null },
          holders: [{ ...holder, count: 3 }],
        }),
      ),
    );
    renderAt('/achievements/welcome_back');
    await screen.findByRole('heading', { level: 1, name: 'Clays Broken' });
    expect(screen.queryByText('1,000 clays broken')).not.toBeInTheDocument();
    expect(screen.getByText(/×3/)).toBeInTheDocument();
  });

  it('says so when nobody holds the trophy', async () => {
    server.use(
      http.get('*/api/achievements/:code', () =>
        HttpResponse.json({ ...trophyDetailFixture, holders: [] }),
      ),
    );
    renderAt('/achievements/clays_broken%3A3');
    expect(await screen.findByText('Nobody holds this trophy yet.')).toBeInTheDocument();
  });

  it('shows an error for an unknown trophy', async () => {
    server.use(http.get('*/api/achievements/:code', () => new HttpResponse(null, { status: 404 })));
    renderAt('/achievements/nope');
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load this trophy.');
  });

  it('shows dates as Sep 13, 2026, not ISO', async () => {
    renderAt('/achievements/clays_broken%3A3');
    const holders = await screen.findByRole('list', { name: 'Holders' });
    expect(within(holders).getByText('May 5, 2024')).toHaveAttribute('datetime', '2024-05-05');
  });

  it('shows 10 holders, then every one after "Show all N"', async () => {
    const [first] = trophyDetailFixture.holders;
    if (!first) throw new Error('fixture has a holder');
    const holders = Array.from({ length: 23 }, (_, i) => ({ ...first, shooter_id: 200 + i }));
    server.use(
      http.get('*/api/achievements/:code', () =>
        HttpResponse.json({ ...trophyDetailFixture, holders }),
      ),
    );
    const user = userEvent.setup();
    renderAt('/achievements/clays_broken%3A3');
    const list = await screen.findByRole('list', { name: 'Holders' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(10);
    await user.click(screen.getByRole('button', { name: 'Show all 23 holders' }));
    expect(within(list).getAllByRole('listitem')).toHaveLength(23);
    expect(screen.queryByRole('button', { name: /Show all/ })).not.toBeInTheDocument();
  });
});
