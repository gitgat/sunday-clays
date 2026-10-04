import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { useFeatures } from '../../../lib/features';
import { useClubEvent } from '../api';
import { fallFunShoot } from '../mocks';
import { allSignups, saveSignup } from '../tokens';
import { CancelSheet } from './CancelSheet';

function Watcher() {
  useClubEvent(1);
  return null;
}

function FeaturesWatcher() {
  useFeatures();
  return null;
}

describe('CancelSheet', () => {
  it("cancels this device's own spot with its token and forgets it", async () => {
    let body: unknown = null;
    server.use(
      http.post('*/api/club-events/1/registrations/21/cancel', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ status: 'cancelled', promoted: 0 });
      }),
    );
    saveSignup(21, { eventId: 1, token: 'tok-21', status: 'going' });
    const onClose = vi.fn();
    const { user } = renderWithProviders(
      <CancelSheet
        eventId={1}
        target={{ kind: 'own', registrationId: 21, token: 'tok-21', guests: 2 }}
        onClose={onClose}
      />,
    );
    expect(screen.getByText('Cancel your spot and 2 guests?')).toBeInTheDocument();
    await user.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel my spot' }),
    );
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(body).toEqual({ token: 'tok-21' });
    expect(allSignups()).toEqual([]);
  });

  it('cancels another name by email and shows the generic mismatch', async () => {
    server.use(
      http.post('*/api/club-events/1/registrations/13/cancel', () =>
        HttpResponse.json(
          {
            error: {
              code: 'cancel_not_matched',
              message: "That email doesn't match this sign-up. Check it and try again.",
            },
          },
          { status: 403 },
        ),
      ),
    );
    const { user } = renderWithProviders(
      <CancelSheet
        eventId={1}
        target={{ kind: 'other', registrationId: 13, name: 'Pat Kim' }}
        onClose={vi.fn()}
      />,
    );
    const sheet = within(screen.getByRole('dialog', { name: "Cancel Pat Kim's spot" }));
    await user.type(
      sheet.getByLabelText('Type the email used for this sign-up.'),
      'wrong@example.com',
    );
    await user.click(sheet.getByRole('button', { name: 'Cancel spot' }));
    expect(await sheet.findByRole('alert')).toHaveTextContent(
      "That email doesn't match this sign-up. Check it and try again.",
    );
  });

  it.each(['registration_not_found', 'event_started'])(
    'refetches the event when the server says %s',
    async (code) => {
      let reads = 0;
      server.use(
        http.get('*/api/club-events/1', () => {
          reads += 1;
          return HttpResponse.json(fallFunShoot);
        }),
        http.post('*/api/club-events/1/registrations/13/cancel', () =>
          HttpResponse.json({ error: { code, message: 'Already gone.' } }, { status: 409 }),
        ),
      );
      const { user } = renderWithProviders(
        <>
          <Watcher />
          <CancelSheet
            eventId={1}
            target={{ kind: 'other', registrationId: 13, name: 'Pat Kim' }}
            onClose={vi.fn()}
          />
        </>,
      );
      await waitFor(() => expect(reads).toBe(1));
      const sheet = within(screen.getByRole('dialog'));
      await user.type(
        sheet.getByLabelText('Type the email used for this sign-up.'),
        'p@example.com',
      );
      await user.click(sheet.getByRole('button', { name: 'Cancel spot' }));
      expect(await sheet.findByRole('alert')).toHaveTextContent('Already gone.');
      await waitFor(() => expect(reads).toBe(2));
    },
  );

  it("shows the switched-off message on the gate's 404 and refetches the switches on close", async () => {
    let switchReads = 0;
    server.use(
      http.get('*/api/features', () => {
        switchReads += 1;
        return HttpResponse.json({ switches: { events: true } });
      }),
      http.post('*/api/club-events/1/registrations/13/cancel', () =>
        HttpResponse.json({ detail: 'Not Found' }, { status: 404 }),
      ),
    );
    const onClose = vi.fn();
    const { user } = renderWithProviders(
      <>
        <FeaturesWatcher />
        <CancelSheet
          eventId={1}
          target={{ kind: 'other', registrationId: 13, name: 'Pat Kim' }}
          onClose={onClose}
        />
      </>,
    );
    await waitFor(() => expect(switchReads).toBe(1));
    const sheet = within(screen.getByRole('dialog'));
    await user.type(sheet.getByLabelText('Type the email used for this sign-up.'), 'p@example.com');
    await user.click(sheet.getByRole('button', { name: 'Cancel spot' }));
    expect(await sheet.findByRole('alert')).toHaveTextContent(
      "Club events aren't available right now. Nothing was saved.",
    );
    expect(switchReads).toBe(1); // not yet: the message must stay readable
    await user.click(screen.getByRole('button', { name: 'Close' }));
    await waitFor(() => expect(switchReads).toBe(2));
    expect(onClose).toHaveBeenCalled();
  });

  it('shows the rate message on 429', async () => {
    server.use(
      http.post('*/api/club-events/1/registrations/13/cancel', () =>
        HttpResponse.json(
          {
            error: {
              code: 'rate_limited',
              message: 'Too many tries from here. Wait a bit and try again.',
            },
          },
          { status: 429 },
        ),
      ),
    );
    const { user } = renderWithProviders(
      <CancelSheet
        eventId={1}
        target={{ kind: 'other', registrationId: 13, name: 'Pat Kim' }}
        onClose={vi.fn()}
      />,
    );
    const sheet = within(screen.getByRole('dialog'));
    await user.type(
      sheet.getByLabelText('Type the email used for this sign-up.'),
      'pat@example.com',
    );
    await user.click(sheet.getByRole('button', { name: 'Cancel spot' }));
    expect(await sheet.findByRole('alert')).toHaveTextContent('Too many tries from here.');
  });
});
