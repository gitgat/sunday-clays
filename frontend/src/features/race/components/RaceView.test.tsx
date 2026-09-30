import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '../../../test/render';
import type { HistoryFrame } from '../api';
import type { RaceViewProps } from './RaceView';
import { RaceView } from './RaceView';

const row = (shooter_id: number, rank: number) => ({
  shooter_id,
  display_name: 'Desmond',
  status: 'guest' as const,
  value: 10,
  rank,
});
const FRAMES: HistoryFrame[] = [
  { event_date: '2026-01-04', rows: [row(7, 1)] },
  { event_date: '2026-01-11', rows: [row(7, 1), row(9, 2)] },
];

const QUERY: RaceViewProps['query'] = {
  period: 'rolling_12',
  metric: 'wins',
  from: '2025-09-29',
  to: '2026-09-27',
};

describe('RaceView', () => {
  it('renders nothing without frames', () => {
    const { container } = renderWithProviders(
      <RaceView frames={[]} metric="wins" mode="rolling_12" query={QUERY} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('keeps the date readout polite while paused and silent while playing', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RaceView frames={FRAMES} metric="wins" mode="rolling_12" query={QUERY} />);
    const date = screen.getByText('Jan 11, 2026', { selector: 'output' });
    expect(date).toHaveAttribute('aria-live', 'polite');
    await user.click(screen.getByRole('button', { name: 'Play' }));
    expect(date).toHaveAttribute('aria-live', 'off');
    await user.click(screen.getByRole('button', { name: 'Pause' }));
    expect(date).toHaveAttribute('aria-live', 'polite');
  });

  it('tells namesakes apart in the standings list', () => {
    renderWithProviders(<RaceView frames={FRAMES} metric="wins" mode="rolling_12" query={QUERY} />);
    expect(screen.getByText('Desmond #7')).toBeInTheDocument();
    expect(screen.getByText('Desmond #9')).toBeInTheDocument();
  });
});

describe('RaceView insight links', () => {
  it("opens on the linked Sunday and highlights the linked shooter's bar", () => {
    renderWithProviders(
      <RaceView frames={FRAMES} metric="wins" mode="rolling_12" query={QUERY} />,
      { route: '/race?race-bars.at=2026-01-04&race-bars.hl=s:7' },
    );
    expect(screen.getByText('Jan 4, 2026', { selector: 'output' })).toBeInTheDocument();
    const chip = screen.getByText('Showing what the insight points to.');
    expect(chip.closest('[data-marked]')).toHaveAttribute('data-marked', '1');
  });
});
