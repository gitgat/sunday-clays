import { screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { server } from '../../test/msw/server';
import { renderWithProviders } from '../../test/render';
import { BumpsProvider, InsightBump } from './BumpsProvider';

function asking() {
  const asked: URLSearchParams[] = [];
  server.use(
    http.get('*/api/bumps', ({ request }) => {
      asked.push(new URL(request.url).searchParams);
      return HttpResponse.json({ a: { bumps: 3, bumped: false }, b: { bumps: 1, bumped: true } });
    }),
  );
  return asked;
}

describe('BumpsProvider', () => {
  it('asks once for every key inside and hands each button its count', async () => {
    const asked = asking();
    renderWithProviders(
      <BumpsProvider keys={['b', 'a', 'b']}>
        <section aria-label="a">
          <InsightBump insightKey="a" />
        </section>
        <section aria-label="b">
          <InsightBump insightKey="b" />
        </section>
      </BumpsProvider>,
    );
    expect(await screen.findByRole('button', { name: 'Fist bump, 3 bumps' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Fist bump, 1 bump' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(asked).toHaveLength(1);
    expect(asked[0]?.get('keys')).toBe('a,b');
    expect(asked[0]?.get('device_id')).toBe(localStorage.getItem('sc.device'));
  });

  it('renders no button outside a provider', () => {
    renderWithProviders(<InsightBump insightKey="a" />);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('turns the buttons off and says why once when storage is blocked', async () => {
    const asked = asking();
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    renderWithProviders(
      <BumpsProvider keys={['a', 'b']}>
        <InsightBump insightKey="a" />
        <InsightBump insightKey="b" />
      </BumpsProvider>,
    );
    expect(screen.getAllByText('Bumps need this browser to remember you')).toHaveLength(1);
    const button = await screen.findByRole('button', { name: 'Fist bump, 3 bumps' });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription('Bumps need this browser to remember you');
    await waitFor(() => expect(asked).toHaveLength(1));
    expect(asked[0]?.has('device_id')).toBe(false);
  });
});
