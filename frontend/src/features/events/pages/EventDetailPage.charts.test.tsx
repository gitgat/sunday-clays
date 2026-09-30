import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { Route, Routes } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import type { EventDetail } from '../api';
import { eventDetail } from '../mocks';
import { EventDetailPage } from './EventDetailPage';

// Counts loads of ECharts' core (imported only by the chart wrapper): a page that imports the
// heatmap statically loads it with the page itself, before any event is fetched.
const echarts = vi.hoisted(() => ({ loads: 0 }));
vi.mock('echarts/core', async (importOriginal) => {
  echarts.loads += 1;
  return importOriginal();
});

function renderEvent(detail: EventDetail) {
  server.use(http.get('*/api/events/:date', () => HttpResponse.json(detail)));
  return renderWithProviders(
    <Routes>
      <Route path="/events/:date" element={<EventDetailPage sections={[]} />} />
    </Routes>,
    { route: `/events/${detail.event_date}` },
  );
}

// The module registry is per file and these run in order: the second test loads ECharts for good.
describe('EventDetailPage chart loading', () => {
  it('never loads ECharts for an event without station data', async () => {
    renderEvent({ ...eventDetail, stations: null });
    expect(await screen.findByRole('table', { name: 'Results' })).toBeInTheDocument();
    expect(echarts.loads).toBe(0);
  });

  it('loads ECharts when the event has a station heatmap', async () => {
    renderEvent(eventDetail);
    expect(
      // A cold import of ECharts can outlast findBy's 1 s default under a loaded machine.
      await screen.findByRole(
        'img',
        { name: 'Station hits heatmap for Sep 13, 2026' },
        { timeout: 10_000 },
      ),
    ).toBeInTheDocument();
    expect(echarts.loads).toBe(1);
  });
});
