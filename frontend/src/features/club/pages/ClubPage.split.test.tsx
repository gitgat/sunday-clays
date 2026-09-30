import { screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import {
  clubAttendance,
  clubCohorts,
  clubConversion,
  clubDistribution,
  clubParity,
  clubRegulars,
  clubSummary,
  clubTrends,
} from '../mocks';

/** Holds back the ECharts wrapper (and so ECharts) until the test releases it. */
const echarts = vi.hoisted(() => {
  let release = () => {};
  const loaded = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { loaded, release: () => release() };
});

vi.mock('../../../components/charts/EChart', async (importOriginal) => {
  await echarts.loaded;
  return importOriginal();
});

describe('ClubPage code splitting', { timeout: 15_000 }, () => {
  // Load the real ECharts graph into the module cache (bypassing the gate), so after the release
  // the charts appear without a cold import.
  beforeAll(async () => {
    await vi.importActual('../../../components/charts/EChart');
  });

  it('shows the header and the regulars while the chart code is still loading', async () => {
    server.use(
      http.get('*/api/club/summary', () => HttpResponse.json(clubSummary)),
      http.get('*/api/club/attendance', () => HttpResponse.json(clubAttendance)),
      http.get('*/api/club/cohorts', () => HttpResponse.json(clubCohorts)),
      http.get('*/api/club/distribution', () => HttpResponse.json(clubDistribution)),
      http.get('*/api/club/regulars', () => HttpResponse.json(clubRegulars)),
      http.get('*/api/club/conversion', () => HttpResponse.json(clubConversion)),
      http.get('*/api/club/parity', () => HttpResponse.json(clubParity)),
      http.get('*/api/club/trends', () => HttpResponse.json(clubTrends)),
      http.post('*/api/explore', () =>
        HttpResponse.json({ columns: [], rows: [], n_rounds: 0, truncated: false }),
      ),
    );
    const { ClubPage } = await import('./ClubPage');
    renderWithProviders(<ClubPage />, { route: '/club' });

    expect(screen.getByRole('heading', { level: 1, name: 'Club' })).toBeInTheDocument();
    expect(await screen.findByText('7,480')).toBeInTheDocument();
    expect(await screen.findByText('Core regulars (2)')).toBeInTheDocument();
    // Each chart holds its place with a titled loading card; no chart control exists yet.
    expect(screen.getByRole('region', { name: 'How open is the competition?' })).toHaveTextContent(
      'Loading',
    );
    expect(screen.queryAllByRole('button', { name: 'CSV' })).toHaveLength(0);

    echarts.release();
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'CSV' })).toHaveLength(11), {
      timeout: 5000,
    });
    // The turnout card waits for the window's anchor, then runs its query.
    expect(await screen.findByText('No data for these filters')).toBeInTheDocument();
  });
});
