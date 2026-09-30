import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { LazyChart } from './LazyChart';

describe('LazyChart', () => {
  it('holds its place with a titled loading card, then shows the chart', async () => {
    renderWithProviders(
      <LazyChart title="Parity" load={async () => ({ default: () => <p>chart</p> })} />,
    );
    expect(screen.getByRole('region', { name: 'Parity' })).toHaveTextContent('Loading');
    expect(await screen.findByText('chart')).toBeInTheDocument();
  });

  it('contains a chunk that fails to load and loads it afresh on Retry', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const load = vi
      .fn<() => Promise<{ default: () => React.JSX.Element }>>()
      .mockRejectedValueOnce(new Error('chunk 404'))
      .mockResolvedValue({ default: () => <p>chart</p> });
    const { user } = renderWithProviders(
      <>
        <h1>Club</h1>
        <LazyChart title="Parity" load={load} />
      </>,
    );
    expect(await screen.findByText("Couldn't load parity")).toBeInTheDocument();
    // Only this chart fails: the rest of the page stays.
    expect(screen.getByRole('heading', { level: 1, name: 'Club' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('chart')).toBeInTheDocument();
    expect(load).toHaveBeenCalledTimes(2);
  });
});
