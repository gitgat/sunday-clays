import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { resetMeForTests, setMe } from '../../../lib/me';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { clubEventKey } from '../api';
import { fallFunShoot, signedUp } from '../mocks';
import { allSignups } from '../tokens';
import { SignUpSheet } from './SignUpSheet';

afterEach(() => {
  resetMeForTests();
});

function renderSheet(event = fallFunShoot) {
  const onSignedUp = vi.fn();
  const onClose = vi.fn();
  const view = renderWithProviders(
    <SignUpSheet event={event} open onClose={onClose} onSignedUp={onSignedUp} />,
  );
  return { ...view, onSignedUp, onClose };
}

function dialog() {
  return within(screen.getByRole('dialog'));
}

describe('SignUpSheet', () => {
  it('finds a name in any order and always offers "I\'m not listed"', async () => {
    const { user } = renderSheet();
    expect(dialog().getByRole('button', { name: "I'm not listed" })).toBeInTheDocument();
    await user.type(dialog().getByRole('searchbox', { name: 'Who are you?' }), 'ike had');
    expect(await dialog().findByRole('button', { name: 'Hadley, Ike' })).toBeInTheDocument();
    await user.clear(dialog().getByRole('searchbox', { name: 'Who are you?' }));
    await user.type(dialog().getByRole('searchbox', { name: 'Who are you?' }), 'gilchrist');
    expect(dialog().queryByRole('button', { name: 'Gilchrist, Melvin' })).not.toBeInTheDocument();
  });

  it('uses the email on file when there is one', async () => {
    server.use(
      http.get('*/api/club-events/:id/signup-check', () =>
        HttpResponse.json({ has_email: true, already_signed_up: false }),
      ),
    );
    const { user } = renderSheet();
    await user.type(dialog().getByRole('searchbox', { name: 'Who are you?' }), 'hadley');
    await user.click(await dialog().findByRole('button', { name: 'Hadley, Ike' }));
    expect(await dialog().findByText("We'll use the email we have for you.")).toBeInTheDocument();
    expect(dialog().queryByLabelText('Your email')).not.toBeInTheDocument();
  });

  it('asks for an email when none is on file, and disables a second sign-up', async () => {
    const { user } = renderSheet();
    await user.type(dialog().getByRole('searchbox', { name: 'Who are you?' }), 'hadley');
    await user.click(await dialog().findByRole('button', { name: 'Hadley, Ike' }));
    expect(await dialog().findByLabelText('Your email')).toBeInTheDocument();
    expect(
      dialog().getByText('Only organizers see it. This site never sends email.'),
    ).toBeInTheDocument();
    server.use(
      http.get('*/api/club-events/:id/signup-check', () =>
        HttpResponse.json({ has_email: false, already_signed_up: true }),
      ),
    );
    await user.click(dialog().getByRole('button', { name: 'Change' }));
    await user.type(dialog().getByRole('searchbox', { name: 'Who are you?' }), 'abernathy');
    await user.click(await dialog().findByRole('button', { name: 'Abernathy, Preston' }));
    expect(
      await dialog().findByText('Abernathy, Preston is already on the list.'),
    ).toBeInTheDocument();
    expect(dialog().getByRole('button', { name: 'Sign me up' })).toBeDisabled();
  });

  it('pre-picks "Which one are you?" when the picker lists that shooter', async () => {
    setMe(3);
    renderSheet();
    expect(await dialog().findByText('Hadley, Ike')).toBeInTheDocument();
    expect(dialog().getByRole('button', { name: 'Change' })).toBeInTheDocument();
  });

  it('does not pre-pick a shooter the picker does not list', async () => {
    setMe(41); // deceased in the directory mock
    const { user } = renderSheet();
    const search = await dialog().findByRole('searchbox', { name: 'Who are you?' });
    // wait for the directory to load before asserting nothing was pre-picked
    await user.type(search, 'ike');
    expect(await dialog().findByRole('button', { name: 'Hadley, Ike' })).toBeInTheDocument();
    expect(dialog().queryByRole('button', { name: 'Change' })).not.toBeInTheDocument();
    expect(dialog().queryByRole('button', { name: 'Gilchrist, Melvin' })).not.toBeInTheDocument();
  });

  it('signs up a typed name with guests and saves the token on this device', async () => {
    let body: unknown = null;
    server.use(
      http.post('*/api/club-events/:id/registrations', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(signedUp, { status: 201 });
      }),
    );
    const { user, onSignedUp } = renderSheet();
    await user.click(dialog().getByRole('button', { name: "I'm not listed" }));
    await user.type(dialog().getByLabelText('Your first and last name'), 'Dana Quill');
    await user.type(dialog().getByLabelText('Your email'), 'dana.quill@example.com');
    await user.click(dialog().getByRole('button', { name: 'More guests' }));
    await user.click(dialog().getByRole('button', { name: 'More guests' }));
    await user.click(dialog().getByRole('button', { name: 'More guests' })); // capped at 2
    expect(dialog().getByText('2', { selector: '[data-guests]' })).toBeInTheDocument();
    await user.click(dialog().getByRole('button', { name: 'Sign me up' }));
    await waitFor(() => expect(onSignedUp).toHaveBeenCalled());
    expect(body).toEqual({
      shooter_id: null,
      name: 'Dana Quill',
      email: 'dana.quill@example.com',
      guests: 2,
    });
    expect(allSignups()).toEqual([
      { registrationId: 21, eventId: 1, token: 'tok-21', status: 'going' },
    ]);
    expect(onSignedUp.mock.calls[0]?.[0]).toMatchObject({ name: 'Dana Quill', typedEmail: true });
  });

  it('warns exactly when the server would waitlist', async () => {
    const { user } = renderSheet({ ...fallFunShoot, waitlist_count: 0, spots_taken: 2 });
    await user.click(dialog().getByRole('button', { name: "I'm not listed" }));
    expect(dialog().queryByText('This will put you on the waitlist.')).not.toBeInTheDocument();
    await user.click(dialog().getByRole('button', { name: 'More guests' }));
    expect(dialog().queryByText('This will put you on the waitlist.')).not.toBeInTheDocument();
    await user.click(dialog().getByRole('button', { name: 'More guests' }));
    expect(dialog().getByText('This will put you on the waitlist.')).toBeInTheDocument();
  });

  it('shows the closed message in place of the button, keeps what was typed and refetches', async () => {
    server.use(
      http.post('*/api/club-events/:id/registrations', () =>
        HttpResponse.json(
          { error: { code: 'signups_closed', message: 'Sign-ups for this event have closed.' } },
          { status: 409 },
        ),
      ),
    );
    const { user, queryClient } = renderSheet();
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
    await user.click(dialog().getByRole('button', { name: "I'm not listed" }));
    await user.type(dialog().getByLabelText('Your first and last name'), 'Dana Quill');
    await user.type(dialog().getByLabelText('Your email'), 'dana.quill@example.com');
    await user.click(dialog().getByRole('button', { name: 'Sign me up' }));
    expect(await dialog().findByText('Sign-ups for this event have closed.')).toBeInTheDocument();
    expect(dialog().queryByRole('button', { name: 'Sign me up' })).not.toBeInTheDocument();
    expect(dialog().getByLabelText('Your first and last name')).toHaveValue('Dana Quill');
    expect(invalidate).toHaveBeenCalledWith({ queryKey: clubEventKey(1) });
  });

  it('says nothing was saved when the switch went off mid-sign-up', async () => {
    server.use(
      http.post('*/api/club-events/:id/registrations', () =>
        HttpResponse.json({ detail: 'Not Found' }, { status: 404 }),
      ),
    );
    const { user, queryClient } = renderSheet();
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
    await user.click(dialog().getByRole('button', { name: "I'm not listed" }));
    await user.type(dialog().getByLabelText('Your first and last name'), 'Dana Quill');
    await user.type(dialog().getByLabelText('Your email'), 'dana.quill@example.com');
    await user.click(dialog().getByRole('button', { name: 'Sign me up' }));
    expect(
      await dialog().findByText("Club events aren't available right now. Nothing was saved."),
    ).toBeInTheDocument();
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['/api/features'] });
    expect(allSignups()).toEqual([]);
  });

  it('shows a refusal message and keeps the button for other errors', async () => {
    server.use(
      http.post('*/api/club-events/:id/registrations', () =>
        HttpResponse.json(
          {
            error: {
              code: 'name_on_list',
              message: 'That name is already on the shooter list. Pick it from the list instead.',
            },
          },
          { status: 409 },
        ),
      ),
    );
    const { user } = renderSheet();
    await user.click(dialog().getByRole('button', { name: "I'm not listed" }));
    await user.type(dialog().getByLabelText('Your first and last name'), 'Ike Hadley');
    await user.type(dialog().getByLabelText('Your email'), 'x@example.com');
    await user.click(dialog().getByRole('button', { name: 'Sign me up' }));
    expect(await dialog().findByRole('alert')).toHaveTextContent(
      'That name is already on the shooter list. Pick it from the list instead.',
    );
    expect(dialog().getByRole('button', { name: 'Sign me up' })).toBeEnabled();
  });

  it('goes back to the list from "I\'m not listed", and focuses the search', async () => {
    const { user } = renderSheet();
    await user.click(dialog().getByRole('button', { name: "I'm not listed" }));
    expect(dialog().getByLabelText('Your first and last name')).toHaveFocus();
    await user.click(dialog().getByRole('button', { name: 'Pick from the list' }));
    expect(dialog().getByRole('searchbox', { name: 'Who are you?' })).toHaveFocus();
    expect(dialog().queryByLabelText('Your first and last name')).not.toBeInTheDocument();
  });

  it('moves focus to Change after picking a name', async () => {
    const { user } = renderSheet();
    await user.type(dialog().getByRole('searchbox', { name: 'Who are you?' }), 'hadley');
    await user.click(await dialog().findByRole('button', { name: 'Hadley, Ike' }));
    expect(dialog().getByRole('button', { name: 'Change' })).toHaveFocus();
  });

  it('shows an alert, not a dead button, when the sign-up check fails', async () => {
    server.use(
      http.get('*/api/club-events/:id/signup-check', () =>
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
    const { user } = renderSheet();
    await user.type(dialog().getByRole('searchbox', { name: 'Who are you?' }), 'hadley');
    await user.click(await dialog().findByRole('button', { name: 'Hadley, Ike' }));
    expect(await dialog().findByRole('alert')).toHaveTextContent('Too many tries from here.');
  });

  it('says to try again when the sign-up check cannot be reached', async () => {
    server.use(http.get('*/api/club-events/:id/signup-check', () => HttpResponse.error()));
    const { user } = renderSheet();
    await user.type(dialog().getByRole('searchbox', { name: 'Who are you?' }), 'hadley');
    await user.click(await dialog().findByRole('button', { name: 'Hadley, Ike' }));
    expect(await dialog().findByRole('alert')).toHaveTextContent(
      'Something went wrong. Try again.',
    );
  });

  it('focuses the closed message when it replaces the button', async () => {
    server.use(
      http.post('*/api/club-events/:id/registrations', () =>
        HttpResponse.json(
          { error: { code: 'signups_closed', message: 'Sign-ups for this event have closed.' } },
          { status: 409 },
        ),
      ),
    );
    const { user } = renderSheet();
    await user.click(dialog().getByRole('button', { name: "I'm not listed" }));
    await user.type(dialog().getByLabelText('Your first and last name'), 'Dana Quill');
    await user.type(dialog().getByLabelText('Your email'), 'dana.quill@example.com');
    await user.click(dialog().getByRole('button', { name: 'Sign me up' }));
    const status = await dialog().findByRole('status');
    expect(status).toHaveTextContent('Sign-ups for this event have closed.');
    expect(status).toHaveAttribute('tabindex', '-1');
    expect(status).toHaveFocus();
  });

  it('needs a non-blank email when one is asked for', async () => {
    const { user } = renderSheet();
    await user.click(dialog().getByRole('button', { name: "I'm not listed" }));
    await user.type(dialog().getByLabelText('Your first and last name'), 'Dana Quill');
    await user.type(dialog().getByLabelText('Your email'), '   ');
    expect(dialog().getByRole('button', { name: 'Sign me up' })).toBeDisabled();
  });

  it('announces the already-on-the-list line in a polite live region', async () => {
    server.use(
      http.get('*/api/club-events/:id/signup-check', () =>
        HttpResponse.json({ has_email: true, already_signed_up: true }),
      ),
    );
    const { user } = renderSheet();
    await user.type(dialog().getByRole('searchbox', { name: 'Who are you?' }), 'hadley');
    await user.click(await dialog().findByRole('button', { name: 'Hadley, Ike' }));
    const line = await dialog().findByText('Hadley, Ike is already on the list.');
    expect(line.closest('[aria-live="polite"]')).not.toBeNull();
  });
});
