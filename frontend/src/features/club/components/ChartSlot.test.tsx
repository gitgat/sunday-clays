import { useQuery } from '@tanstack/react-query';
import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { ChartSlot } from './ChartSlot';

function Harness({ id, load }: { id: string; load: () => Promise<string[]> }) {
  const query = useQuery({ queryKey: ['slot', id], queryFn: load });
  return (
    <ChartSlot
      title="Parity"
      query={query}
      isEmpty={(d) => d.length === 0}
      emptyText="No winners yet"
    >
      {(rows) => <p>{rows.join(',')}</p>}
    </ChartSlot>
  );
}

describe('ChartSlot', () => {
  it('shows the titled card while loading, then the chart', async () => {
    renderWithProviders(<Harness id="ok" load={() => Promise.resolve(['a', 'b'])} />);
    expect(screen.getByText('Parity')).toBeInTheDocument();
    expect(await screen.findByText('a,b')).toBeInTheDocument();
  });

  it('shows the empty text', async () => {
    renderWithProviders(<Harness id="empty" load={() => Promise.resolve([])} />);
    expect(await screen.findByText('No winners yet')).toBeInTheDocument();
  });

  it('shows a load failure with the error message', async () => {
    renderWithProviders(<Harness id="err" load={() => Promise.reject(new Error('boom'))} />);
    expect(await screen.findByText("Couldn't load parity")).toBeInTheDocument();
    expect(screen.getByText('boom')).toBeInTheDocument();
  });
});
