import { screen, waitFor } from '@testing-library/react';
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

  it('takes a bump back on a second tap, and sends the two taps in order', async () => {
    const calls: string[] = [];
    server.use(
      http.post('*/api/sheet/bumps', async () => {
        calls.push('POST');
        await delay(30);
        return HttpResponse.json({ bumps: 3, bumped: true });
      }),
      http.delete('*/api/sheet/bumps', async ({ request }) => {
        calls.push('DELETE');
        expect(await request.json()).toEqual({ post_key: KEY, device_id: DEVICE });
        return HttpResponse.json({ bumps: 2, bumped: false });
      }),
    );
    const queryClient = seeded({ [KEY]: { bumps: 2, bumped: false } });
    const { user } = renderWithProviders(<Harness />, { queryClient });
    await user.click(screen.getByRole('button', { name: 'Fist bump, 2 bumps' }));
    await user.click(screen.getByRole('button', { name: 'Fist bump, 3 bumps' }));
    expect(screen.getByRole('button', { name: 'Fist bump, 2 bumps' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
    await waitFor(() => expect(calls).toEqual(['POST', 'DELETE']));
    // The POST's answer (3) arrived while the DELETE was queued: it never showed.
    expect(screen.getByRole('button', { name: 'Fist bump, 2 bumps' })).toBeInTheDocument();
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
