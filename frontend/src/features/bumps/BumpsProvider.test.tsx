import { screen, waitFor, within } from '@testing-library/react';
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

  it('says once that counts are not available when the counts GET fails', async () => {
    server.use(
      http.get('*/api/bumps', () =>
        HttpResponse.json({ error: { code: 'internal', message: 'x' } }, { status: 500 }),
      ),
    );
    renderWithProviders(
      <BumpsProvider keys={['a', 'b']}>
        <InsightBump insightKey="a" />
        <InsightBump insightKey="b" />
      </BumpsProvider>,
    );
    const note = await screen.findByText('Bump counts aren’t available right now');
    expect(screen.getAllByText('Bump counts aren’t available right now')).toHaveLength(1);
    expect(note.closest('[role="status"],[role="alert"]')).toBeNull();
    expect(screen.getAllByRole('button', { name: /^Fist bump/ })).toHaveLength(2);
  });

  it('shows no unavailable note when the counts arrive', async () => {
    asking();
    renderWithProviders(
      <BumpsProvider keys={['a']}>
        <InsightBump insightKey="a" />
      </BumpsProvider>,
    );
    await screen.findByRole('button', { name: 'Fist bump, 3 bumps' });
    expect(screen.queryByText(/aren’t available/)).toBeNull();
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

  it('announces several failures once, in one polite live region that is always there', async () => {
    server.use(
      http.get('*/api/bumps', () =>
        HttpResponse.json({ a: { bumps: 0, bumped: false }, b: { bumps: 0, bumped: false } }),
      ),
      http.post('*/api/bumps', () =>
        HttpResponse.json({ error: { code: 'rate_limited', message: 'x' } }, { status: 429 }),
      ),
    );
    const { container, user } = renderWithProviders(
      <BumpsProvider keys={['a', 'b']}>
        <section aria-label="a">
          <InsightBump insightKey="a" />
        </section>
        <section aria-label="b">
          <InsightBump insightKey="b" />
        </section>
      </BumpsProvider>,
    );
    const live = container.querySelector('[aria-live="polite"]');
    expect(live).not.toBeNull();
    expect(live).toBeEmptyDOMElement();
    expect(live).not.toHaveAttribute('role');
    for (const name of ['a', 'b']) {
      await user.click(
        within(screen.getByRole('region', { name })).getByRole('button', { name: /^Fist bump/ }),
      );
    }
    await waitFor(() => expect(live).toHaveTextContent(/^Couldn’t send that bump$/));
    // Each failed button keeps its own visible text, but nothing is an alert or a status.
    expect(screen.getAllByText('Couldn’t send that bump')).toHaveLength(3);
    expect(screen.queryAllByRole('alert')).toHaveLength(0);
    expect(screen.queryAllByRole('status')).toHaveLength(0);
  });

  it('describes the button by its headline as well as the off note', async () => {
    asking();
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    renderWithProviders(
      <BumpsProvider keys={['a']}>
        <p id="head-a">Pat Kim shot 44</p>
        <InsightBump insightKey="a" describedBy="head-a" />
      </BumpsProvider>,
    );
    const button = await screen.findByRole('button', { name: 'Fist bump, 3 bumps' });
    expect(button).toHaveAccessibleDescription(
      'Bumps need this browser to remember you Pat Kim shot 44',
    );
  });
});
