import { screen, waitFor, within } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { createTestQueryClient, renderWithProviders } from '../../test/render';
import { bumpsKey, useBumps, type BumpCounts } from './api';
import { BumpButton } from './BumpButton';

const DEVICE = '00000000-0000-4000-8000-00000000000a';
const KEY = 'k-pb-3';
const KEYS = [KEY];
const A = 'k-a';
const B = 'k-b';
const TWO = [A, B];

/** The button wired to the bumps query, as an insight list renders it. */
function Harness({ deviceId = DEVICE }: { deviceId?: string | null }) {
  const bumps = useBumps(KEYS, deviceId);
  return (
    <>
      <p id="note">Bumps need this browser to remember you</p>
      <BumpButton
        queryKey={bumpsKey(KEYS, deviceId)}
        insightKey={KEY}
        deviceId={deviceId}
        state={bumps.data?.[KEY]}
        noteId="note"
      />
    </>
  );
}

function Two() {
  const bumps = useBumps(TWO, DEVICE);
  return (
    <>
      <p id="note">off</p>
      {TWO.map((k) => (
        <section key={k} aria-label={k}>
          <BumpButton
            queryKey={bumpsKey(TWO, DEVICE)}
            insightKey={k}
            deviceId={DEVICE}
            state={bumps.data?.[k]}
            noteId="note"
          />
        </section>
      ))}
    </>
  );
}

const buttonIn = (name: string) => within(screen.getByRole('region', { name })).getByRole('button');

function seeded(keys: string[], counts: BumpCounts) {
  const queryClient = createTestQueryClient();
  queryClient.setQueryData(bumpsKey(keys, DEVICE), counts);
  server.use(http.get('*/api/bumps', () => HttpResponse.json(counts)));
  return queryClient;
}

describe('BumpButton', () => {
  it('counts the tap at once, before the server answers, then keeps the server count', async () => {
    let release: () => void = () => undefined;
    const answered = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.post('*/api/bumps', async () => {
        await answered;
        return HttpResponse.json({ bumps: 7, bumped: true });
      }),
    );
    const queryClient = seeded(KEYS, { [KEY]: { bumps: 2, bumped: false } });
    const { user } = renderWithProviders(<Harness />, { queryClient });
    const button = screen.getByRole('button', { name: 'Fist bump, 2 bumps' });
    expect(button).toHaveAttribute('aria-pressed', 'false');
    await user.click(button);
    expect(screen.getByRole('button', { name: 'Fist bump, 3 bumps' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    release();
    expect(await screen.findByRole('button', { name: 'Fist bump, 7 bumps' })).toBeInTheDocument();
  });

  it('rolls back and says so when the bump fails', async () => {
    server.use(
      http.post('*/api/bumps', () =>
        HttpResponse.json({ error: { code: 'rate_limited', message: 'x' } }, { status: 429 }),
      ),
    );
    const queryClient = seeded(KEYS, { [KEY]: { bumps: 2, bumped: false } });
    const { user } = renderWithProviders(<Harness />, { queryClient });
    await user.click(screen.getByRole('button', { name: 'Fist bump, 2 bumps' }));
    expect(await screen.findByText('Couldn’t send that bump')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Fist bump, 2 bumps' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('rolls back and says so when the insight is gone (404)', async () => {
    server.use(
      http.post('*/api/bumps', () =>
        HttpResponse.json({ error: { code: 'insight_not_found', message: 'x' } }, { status: 404 }),
      ),
    );
    const queryClient = seeded(KEYS, { [KEY]: { bumps: 1, bumped: false } });
    const { user } = renderWithProviders(<Harness />, { queryClient });
    await user.click(screen.getByRole('button', { name: 'Fist bump, 1 bump' }));
    expect(await screen.findByText('Couldn’t send that bump')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Fist bump, 1 bump' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('takes a bump back on a second tap, sends the taps in order and ignores the stale answer', async () => {
    const calls: string[] = [];
    const gate = () => {
      let open: () => void = () => undefined;
      const opened = new Promise<void>((resolve) => {
        open = resolve;
      });
      return { opened, open };
    };
    const post = gate();
    const del = gate();
    server.use(
      http.post('*/api/bumps', async () => {
        calls.push('POST');
        await post.opened;
        return HttpResponse.json({ bumps: 3, bumped: true });
      }),
      http.delete('*/api/bumps', async ({ request }) => {
        calls.push('DELETE');
        expect(await request.json()).toEqual({ key: KEY, device_id: DEVICE });
        await del.opened;
        return HttpResponse.json({ bumps: 2, bumped: false });
      }),
    );
    const queryClient = seeded(KEYS, { [KEY]: { bumps: 2, bumped: false } });
    const { user } = renderWithProviders(<Harness />, { queryClient });
    await user.click(screen.getByRole('button', { name: 'Fist bump, 2 bumps' }));
    await user.click(screen.getByRole('button', { name: 'Fist bump, 3 bumps' }));
    await waitFor(() => expect(calls).toEqual(['POST']));
    post.open();
    await waitFor(() => expect(calls).toEqual(['POST', 'DELETE']));
    // The POST's answer (3, bumped) arrived while the DELETE was queued: it must not show.
    const held = screen.getByRole('button', { name: 'Fist bump, 2 bumps' });
    expect(held).toHaveAttribute('aria-pressed', 'false');
    del.open();
    await waitFor(() => expect(queryClient.isMutating()).toBe(0));
    expect(screen.getByRole('button', { name: 'Fist bump, 2 bumps' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('rolls back only the insight that failed, keeping a bump that succeeded meanwhile', async () => {
    let failA: () => void = () => undefined;
    const aHeld = new Promise<void>((resolve) => {
      failA = resolve;
    });
    server.use(
      http.post('*/api/bumps', async ({ request }) => {
        const body = (await request.json()) as { key: string };
        if (body.key === A) {
          await aHeld;
          return HttpResponse.json({ error: { code: 'not_found', message: 'x' } }, { status: 404 });
        }
        return HttpResponse.json({ bumps: 1, bumped: true });
      }),
    );
    const queryClient = seeded(TWO, {
      [A]: { bumps: 0, bumped: false },
      [B]: { bumps: 0, bumped: false },
    });
    const { user } = renderWithProviders(<Two />, { queryClient });
    await user.click(buttonIn(A));
    await user.click(buttonIn(B));
    await waitFor(() => expect(buttonIn(B)).toHaveAccessibleName('Fist bump, 1 bump'));
    failA();
    expect(await screen.findByText('Couldn’t send that bump')).toBeInTheDocument();
    expect(buttonIn(A)).toHaveAttribute('aria-pressed', 'false');
    expect(buttonIn(B)).toHaveAttribute('aria-pressed', 'true');
  });

  it('puts the button back when the bump fails before the counts ever loaded', async () => {
    server.use(
      http.get('*/api/bumps', async () => {
        await delay('infinite');
        return HttpResponse.json({});
      }),
      http.post('*/api/bumps', () =>
        HttpResponse.json({ error: { code: 'rate_limited', message: 'x' } }, { status: 429 }),
      ),
    );
    const { user } = renderWithProviders(<Harness />, { queryClient: createTestQueryClient() });
    await user.click(screen.getByRole('button', { name: 'Fist bump, 0 bumps' }));
    expect(await screen.findByText('Couldn’t send that bump')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Fist bump, 0 bumps' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('refetches the counts when a bump was tapped before they first loaded', async () => {
    let gets = 0;
    let release: () => void = () => undefined;
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get('*/api/bumps', async () => {
        gets += 1;
        if (gets === 1) await held;
        return HttpResponse.json({
          [A]: { bumps: 6, bumped: true },
          [B]: { bumps: 4, bumped: false },
        });
      }),
      http.post('*/api/bumps', () => HttpResponse.json({ bumps: 6, bumped: true })),
    );
    const { user } = renderWithProviders(<Two />, { queryClient: createTestQueryClient() });
    await user.click(buttonIn(A));
    release();
    await waitFor(() => expect(gets).toBeGreaterThanOrEqual(2));
    expect(
      await within(screen.getByRole('region', { name: B })).findByRole('button', {
        name: 'Fist bump, 4 bumps',
      }),
    ).toBeInTheDocument();
  });

  it('lets the first counts land while a bump is still being sent', async () => {
    let releaseGet: () => void = () => undefined;
    const getHeld = new Promise<void>((resolve) => {
      releaseGet = resolve;
    });
    let releasePost: () => void = () => undefined;
    const postHeld = new Promise<void>((resolve) => {
      releasePost = resolve;
    });
    server.use(
      http.get('*/api/bumps', async () => {
        await getHeld;
        return HttpResponse.json({
          [A]: { bumps: 5, bumped: false },
          [B]: { bumps: 4, bumped: false },
        });
      }),
      http.post('*/api/bumps', async () => {
        await postHeld;
        return HttpResponse.json({ bumps: 6, bumped: true });
      }),
    );
    const { user } = renderWithProviders(<Two />, { queryClient: createTestQueryClient() });
    await user.click(buttonIn(A));
    releaseGet();
    // A's POST is still pending: the load must not have been cancelled, so B has its count.
    expect(
      await within(screen.getByRole('region', { name: B })).findByRole('button', {
        name: 'Fist bump, 4 bumps',
      }),
    ).toBeInTheDocument();
    releasePost();
  });

  it('clears the failure text when the next tap goes through', async () => {
    let posts = 0;
    server.use(
      http.post('*/api/bumps', () => {
        posts += 1;
        return posts === 1
          ? HttpResponse.json({ error: { code: 'rate_limited', message: 'x' } }, { status: 429 })
          : HttpResponse.json({ bumps: 3, bumped: true });
      }),
    );
    const queryClient = seeded(KEYS, { [KEY]: { bumps: 2, bumped: false } });
    const { user } = renderWithProviders(<Harness />, { queryClient });
    await user.click(screen.getByRole('button', { name: 'Fist bump, 2 bumps' }));
    expect(await screen.findByText('Couldn’t send that bump')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Fist bump, 2 bumps' }));
    expect(screen.queryByText('Couldn’t send that bump')).toBeNull();
    expect(await screen.findByRole('button', { name: 'Fist bump, 3 bumps' })).toBeInTheDocument();
  });

  it('drops a stale refetch that was in flight when the counts were already loaded', async () => {
    let gets = 0;
    let releaseStale: () => void = () => undefined;
    const staleHeld = new Promise<void>((resolve) => {
      releaseStale = resolve;
    });
    const queryClient = seeded(KEYS, { [KEY]: { bumps: 2, bumped: false } });
    server.use(
      http.get('*/api/bumps', async () => {
        gets += 1;
        await staleHeld;
        return HttpResponse.json({ [KEY]: { bumps: 2, bumped: false } });
      }),
      http.post('*/api/bumps', () => HttpResponse.json({ bumps: 3, bumped: true })),
    );
    const { user } = renderWithProviders(<Harness />, { queryClient });
    await waitFor(() => expect(gets).toBe(1));
    await user.click(screen.getByRole('button', { name: 'Fist bump, 2 bumps' }));
    await waitFor(() => expect(queryClient.isMutating()).toBe(0));
    releaseStale();
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(screen.getByRole('button', { name: 'Fist bump, 3 bumps' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('asks for the counts again once, after two quick taps before they ever loaded', async () => {
    let gets = 0;
    let releasePost: () => void = () => undefined;
    const postHeld = new Promise<void>((resolve) => {
      releasePost = resolve;
    });
    server.use(
      http.get('*/api/bumps', async () => {
        gets += 1;
        if (gets === 1) await delay('infinite');
        return HttpResponse.json({ [KEY]: { bumps: 1, bumped: false } });
      }),
      http.post('*/api/bumps', async () => {
        await postHeld;
        return HttpResponse.json({ bumps: 1, bumped: true });
      }),
      http.delete('*/api/bumps', () => HttpResponse.json({ bumps: 0, bumped: false })),
    );
    const queryClient = createTestQueryClient();
    const { user } = renderWithProviders(<Harness />, { queryClient });
    await waitFor(() => expect(gets).toBe(1));
    await user.click(screen.getByRole('button', { name: 'Fist bump, 0 bumps' }));
    await user.click(screen.getByRole('button', { name: 'Fist bump, 1 bump' }));
    // Both taps are queued behind the held POST: one ask after both settle, not one per tap.
    releasePost();
    await waitFor(() => expect(queryClient.isMutating()).toBe(0));
    await waitFor(() => expect(gets).toBe(2));
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(gets).toBe(2);
  });

  it('shows the count but is off when this browser cannot keep a device id', () => {
    const queryClient = createTestQueryClient();
    queryClient.setQueryData(bumpsKey(KEYS, null), { [KEY]: { bumps: 4, bumped: false } });
    renderWithProviders(<Harness deviceId={null} />, { queryClient });
    const button = screen.getByRole('button', { name: 'Fist bump, 4 bumps' });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription('Bumps need this browser to remember you');
  });
});
