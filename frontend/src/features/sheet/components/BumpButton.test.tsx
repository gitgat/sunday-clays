import { screen, waitFor, within } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { createTestQueryClient, renderWithProviders } from '../../../test/render';
import { bumpsKey, useBumps, type BumpCounts } from '../api';
import { BumpButton } from './BumpButton';

const DATE = '2026-09-27';
const DEVICE = '00000000-0000-4000-8000-00000000000a';
const KEY = 'k-pb-3';

/** The button wired to the bumps query, as the feed renders it. */
function Harness({ deviceId = DEVICE }: { deviceId?: string | null }) {
  const bumps = useBumps(DATE, deviceId);
  return (
    <>
      <p id="note">Bumps need this browser to remember you</p>
      <BumpButton
        date={DATE}
        postKey={KEY}
        deviceId={deviceId}
        state={bumps.data?.[KEY]}
        noteId="note"
      />
    </>
  );
}

function seeded(counts: BumpCounts) {
  const queryClient = createTestQueryClient();
  queryClient.setQueryData(bumpsKey(DATE, DEVICE), counts);
  server.use(http.get('*/api/sheet/:date/bumps', () => HttpResponse.json(counts)));
  return queryClient;
}

describe('BumpButton', () => {
  it('counts the tap at once, before the server answers, then keeps the server count', async () => {
    let release: () => void = () => undefined;
    const answered = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.post('*/api/sheet/bumps', async () => {
        await answered;
        return HttpResponse.json({ bumps: 7, bumped: true });
      }),
    );
    const queryClient = seeded({ [KEY]: { bumps: 2, bumped: false } });
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
      http.post('*/api/sheet/bumps', () =>
        HttpResponse.json({ error: { code: 'rate_limited', message: 'x' } }, { status: 429 }),
      ),
    );
    const queryClient = seeded({ [KEY]: { bumps: 2, bumped: false } });
    const { user } = renderWithProviders(<Harness />, { queryClient });
    await user.click(screen.getByRole('button', { name: 'Fist bump, 2 bumps' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t send that bump');
    expect(screen.getByRole('button', { name: 'Fist bump, 2 bumps' })).toHaveAttribute(
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
      http.post('*/api/sheet/bumps', async () => {
        calls.push('POST');
        await post.opened;
        return HttpResponse.json({ bumps: 3, bumped: true });
      }),
      http.delete('*/api/sheet/bumps', async ({ request }) => {
        calls.push('DELETE');
        expect(await request.json()).toEqual({ post_key: KEY, device_id: DEVICE });
        await del.opened;
        return HttpResponse.json({ bumps: 2, bumped: false });
      }),
    );
    const queryClient = seeded({ [KEY]: { bumps: 2, bumped: false } });
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

  it('rolls back only the post that failed, keeping a bump that succeeded meanwhile', async () => {
    const A = 'k-a';
    const B = 'k-b';
    let failA: () => void = () => undefined;
    const aHeld = new Promise<void>((resolve) => {
      failA = resolve;
    });
    server.use(
      http.post('*/api/sheet/bumps', async ({ request }) => {
        const body = (await request.json()) as { post_key: string };
        if (body.post_key === A) {
          await aHeld;
          return HttpResponse.json({ error: { code: 'not_found', message: 'x' } }, { status: 404 });
        }
        return HttpResponse.json({ bumps: 1, bumped: true });
      }),
    );
    const counts = { [A]: { bumps: 0, bumped: false }, [B]: { bumps: 0, bumped: false } };
    const queryClient = seeded(counts);
    function Two() {
      const bumps = useBumps(DATE, DEVICE);
      return (
        <>
          <p id="note">off</p>
          {[A, B].map((k) => (
            <section key={k} aria-label={k}>
              <BumpButton
                date={DATE}
                postKey={k}
                deviceId={DEVICE}
                state={bumps.data?.[k]}
                noteId="note"
              />
            </section>
          ))}
        </>
      );
    }
    const { user } = renderWithProviders(<Two />, { queryClient });
    await user.click(within(screen.getByRole('region', { name: A })).getByRole('button'));
    await user.click(within(screen.getByRole('region', { name: B })).getByRole('button'));
    await waitFor(() =>
      expect(
        within(screen.getByRole('region', { name: B })).getByRole('button'),
      ).toHaveAccessibleName('Fist bump, 1 bump'),
    );
    failA();
    expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t send that bump');
    const a = within(screen.getByRole('region', { name: A })).getByRole('button');
    const b = within(screen.getByRole('region', { name: B })).getByRole('button');
    expect(a).toHaveAttribute('aria-pressed', 'false');
    expect(b).toHaveAttribute('aria-pressed', 'true');
  });

  it('puts the button back when the bump fails before the counts ever loaded', async () => {
    server.use(
      http.get('*/api/sheet/:date/bumps', async () => {
        await delay('infinite');
        return HttpResponse.json({});
      }),
      http.post('*/api/sheet/bumps', () =>
        HttpResponse.json({ error: { code: 'rate_limited', message: 'x' } }, { status: 429 }),
      ),
    );
    const { user } = renderWithProviders(<Harness />, { queryClient: createTestQueryClient() });
    await user.click(screen.getByRole('button', { name: 'Fist bump, 0 bumps' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t send that bump');
    expect(screen.getByRole('button', { name: 'Fist bump, 0 bumps' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('refetches the counts when a bump was tapped before they first loaded', async () => {
    const A = 'k-a';
    const B = 'k-b';
    let gets = 0;
    let release: () => void = () => undefined;
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get('*/api/sheet/:date/bumps', async () => {
        gets += 1;
        if (gets === 1) await held;
        return HttpResponse.json({
          [A]: { bumps: 6, bumped: true },
          [B]: { bumps: 4, bumped: false },
        });
      }),
      http.post('*/api/sheet/bumps', () => HttpResponse.json({ bumps: 6, bumped: true })),
    );
    function Two() {
      const bumps = useBumps(DATE, DEVICE);
      return (
        <>
          <p id="note">off</p>
          {[A, B].map((k) => (
            <section key={k} aria-label={k}>
              <BumpButton
                date={DATE}
                postKey={k}
                deviceId={DEVICE}
                state={bumps.data?.[k]}
                noteId="note"
              />
            </section>
          ))}
        </>
      );
    }
    const { user } = renderWithProviders(<Two />, { queryClient: createTestQueryClient() });
    await user.click(within(screen.getByRole('region', { name: A })).getByRole('button'));
    release();
    await waitFor(() => expect(gets).toBeGreaterThanOrEqual(2));
    expect(
      await within(screen.getByRole('region', { name: B })).findByRole('button', {
        name: 'Fist bump, 4 bumps',
      }),
    ).toBeInTheDocument();
  });

  it('lets the first counts land while a bump is still being sent', async () => {
    const A = 'k-a';
    const B = 'k-b';
    let releaseGet: () => void = () => undefined;
    const getHeld = new Promise<void>((resolve) => {
      releaseGet = resolve;
    });
    let releasePost: () => void = () => undefined;
    const postHeld = new Promise<void>((resolve) => {
      releasePost = resolve;
    });
    server.use(
      http.get('*/api/sheet/:date/bumps', async () => {
        await getHeld;
        return HttpResponse.json({
          [A]: { bumps: 5, bumped: false },
          [B]: { bumps: 4, bumped: false },
        });
      }),
      http.post('*/api/sheet/bumps', async () => {
        await postHeld;
        return HttpResponse.json({ bumps: 6, bumped: true });
      }),
    );
    function Two() {
      const bumps = useBumps(DATE, DEVICE);
      return (
        <>
          <p id="note">off</p>
          {[A, B].map((k) => (
            <section key={k} aria-label={k}>
              <BumpButton
                date={DATE}
                postKey={k}
                deviceId={DEVICE}
                state={bumps.data?.[k]}
                noteId="note"
              />
            </section>
          ))}
        </>
      );
    }
    const { user } = renderWithProviders(<Two />, { queryClient: createTestQueryClient() });
    await user.click(within(screen.getByRole('region', { name: A })).getByRole('button'));
    releaseGet();
    // A's POST is still pending: the load must not have been cancelled, so B has its count.
    expect(
      await within(screen.getByRole('region', { name: B })).findByRole('button', {
        name: 'Fist bump, 4 bumps',
      }),
    ).toBeInTheDocument();
    releasePost();
  });

  it('shows the count but is off when this browser cannot keep a device id', () => {
    const queryClient = createTestQueryClient();
    queryClient.setQueryData(bumpsKey(DATE, null), { [KEY]: { bumps: 4, bumped: false } });
    renderWithProviders(<Harness deviceId={null} />, { queryClient });
    const button = screen.getByRole('button', { name: 'Fist bump, 4 bumps' });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription('Bumps need this browser to remember you');
  });
});
