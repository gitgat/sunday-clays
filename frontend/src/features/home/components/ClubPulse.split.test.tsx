import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { homeMeta, seasonEvents } from '../mocks';
import { ClubPulse } from './ClubPulse';
import type * as TurnoutChartModule from './TurnoutChart';

// Holds the chart module (ChartFrame and ECharts behind it) until the test releases it, as a
// slow network would: the rest of the card must not wait for it.
const chartModule = vi.hoisted(() => {
  let release = () => {};
  const loaded = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { loaded, release: () => release() };
});
vi.mock('./TurnoutChart', async (importOriginal) => {
  await chartModule.loaded;
  return importOriginal<typeof TurnoutChartModule>();
});

describe('ClubPulse code splitting', () => {
  // ChartFrame (and ECharts) are not held: warm them so the released import resolves quickly.
  beforeAll(async () => {
    await import('../../../components/charts/ChartFrame');
  });

  it('shows the season stats while the chart module is still loading', async () => {
    server.use(
      http.get('*/api/meta', () => HttpResponse.json(homeMeta)),
      http.get('*/api/events', () => HttpResponse.json(seasonEvents)),
    );
    renderWithProviders(<ClubPulse />);
    const pulse = await screen.findByRole('region', { name: 'Club pulse' });
    expect(await within(pulse).findByText('Highest score')).toBeInTheDocument();
    expect(screen.getByRole('status', { name: 'Loading the turnout chart' })).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Turnout per Sunday' })).not.toBeInTheDocument();

    chartModule.release();
    expect(await screen.findByRole('region', { name: 'Turnout per Sunday' })).toBeInTheDocument();
    expect(
      screen.queryByRole('status', { name: 'Loading the turnout chart' }),
    ).not.toBeInTheDocument();
  });
});
