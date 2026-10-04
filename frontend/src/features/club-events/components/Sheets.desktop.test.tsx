import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { stubViewport } from '../../../test/viewport';
import { fallFunShoot } from '../mocks';
import { CancelSheet } from './CancelSheet';
import { SignUpSheet } from './SignUpSheet';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('the sheets, desktop and unexpected failures', () => {
  it('centers both sheets on a desktop', () => {
    stubViewport('desktop');
    renderWithProviders(
      <SignUpSheet event={fallFunShoot} open onClose={vi.fn()} onSignedUp={vi.fn()} />,
    );
    expect(screen.getByRole('dialog', { name: 'Sign up' }).parentElement).toHaveClass(
      'justify-center',
    );
  });

  it('centers the cancel sheet on a desktop', () => {
    stubViewport('desktop');
    renderWithProviders(
      <CancelSheet
        eventId={1}
        target={{ kind: 'own', registrationId: 21, token: 't', guests: 0 }}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByText('Cancel your spot?')).toBeInTheDocument();
    expect(screen.getByRole('dialog').parentElement).toHaveClass('justify-center');
  });

  it('says to try again when the sign-up request itself fails', async () => {
    server.use(http.post('*/api/club-events/:id/registrations', () => HttpResponse.error()));
    const { user } = renderWithProviders(
      <SignUpSheet event={fallFunShoot} open onClose={vi.fn()} onSignedUp={vi.fn()} />,
    );
    const sheet = within(screen.getByRole('dialog'));
    await user.click(sheet.getByRole('button', { name: "I'm not listed" }));
    await user.type(sheet.getByLabelText('Your first and last name'), 'Dana Quill');
    await user.type(sheet.getByLabelText('Your email'), 'dana.quill@example.com');
    await user.click(sheet.getByRole('button', { name: 'Sign me up' }));
    expect(await sheet.findByRole('alert')).toHaveTextContent('Something went wrong. Try again.');
  });

  it('says to try again when the cancel request itself fails', async () => {
    server.use(
      http.post('*/api/club-events/1/registrations/21/cancel', () => HttpResponse.error()),
    );
    const { user } = renderWithProviders(
      <CancelSheet
        eventId={1}
        target={{ kind: 'own', registrationId: 21, token: 't', guests: 0 }}
        onClose={vi.fn()}
      />,
    );
    await user.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel my spot' }),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong. Try again.');
  });

  it('signs up a picked name with the email on file, sending no email', async () => {
    let body: unknown = null;
    server.use(
      http.get('*/api/club-events/:id/signup-check', () =>
        HttpResponse.json({ has_email: true, already_signed_up: false }),
      ),
      http.post('*/api/club-events/:id/registrations', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          {
            registration_id: 31,
            token: 't31',
            status: 'going',
            waitlist_position: null,
            email_used: 'on_file',
          },
          { status: 201 },
        );
      }),
    );
    const onSignedUp = vi.fn();
    const { user } = renderWithProviders(
      <SignUpSheet event={fallFunShoot} open onClose={vi.fn()} onSignedUp={onSignedUp} />,
    );
    const sheet = within(screen.getByRole('dialog'));
    await user.type(sheet.getByRole('searchbox', { name: 'Who are you?' }), 'hadley');
    await user.click(await sheet.findByRole('button', { name: 'Hadley, Ike' }));
    await sheet.findByText("We'll use the email we have for you.");
    await user.click(sheet.getByRole('button', { name: 'Sign me up' }));
    await vi.waitFor(() => expect(onSignedUp).toHaveBeenCalled());
    expect(body).toEqual({ shooter_id: 3, name: null, email: null, guests: 0 });
    expect(onSignedUp.mock.calls[0]?.[0]).toMatchObject({ name: 'Hadley, Ike', typedEmail: false });
  });
});
