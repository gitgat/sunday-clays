import { useQuery } from '@tanstack/react-query';
import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { QueryChart } from './QueryChart';

function Harness({ id, load }: { id: string; load: () => Promise<number[]> }) {
  const controls = <button type="button">Pick</button>;
  const query = useQuery({ queryKey: ['harness', id], queryFn: load });
  return (
    <QueryChart
      title="Rating"
      query={query}
      isEmpty={(d) => d.length === 0}
      emptyText="No rating yet"
      controls={controls}
    >
      {(points) => <p>{points.length} points</p>}
    </QueryChart>
  );
}

describe('QueryChart', () => {
  it('shows the titled card while loading, then the chart', async () => {
    renderWithProviders(<Harness id="ok" load={() => Promise.resolve([1, 2])} />);
    expect(screen.getByText('Rating')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Pick' })).toBeInTheDocument();
    expect(await screen.findByText('2 points')).toBeInTheDocument();
  });

  it('shows the empty text when the data is empty', async () => {
    renderWithProviders(<Harness id="empty" load={() => Promise.resolve([])} />);
    expect(await screen.findByText('No rating yet')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Pick' })).toBeInTheDocument();
  });

  it('shows a load failure with the error message', async () => {
    renderWithProviders(<Harness id="err" load={() => Promise.reject(new Error('boom'))} />);
    expect(await screen.findByText("Couldn't load rating")).toBeInTheDocument();
    expect(screen.getByText('boom')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Pick' })).toBeInTheDocument();
  });
});
