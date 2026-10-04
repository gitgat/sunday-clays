import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { ApiError } from '../../../api/errors';
import { Button } from '../../../components/ui/Button';
import { Sheet } from '../../../components/ui/Sheet';
import { FEATURES_QUERY_KEY } from '../../../lib/features';
import { getMe } from '../../../lib/me';
import { useIsDesktop } from '../../../lib/useMediaQuery';
import { useShooters } from '../../shooters/api';
import {
  clubEventKey,
  useSignUp,
  useSignupCheck,
  type ClubEventDetail,
  type SignupResult,
} from '../api';
import { EMAIL_HELP, EMAIL_ON_FILE, SWITCHED_OFF, WAITLIST_WARNING } from '../format';
import { pickable, searchShooters } from '../picker';
import { wouldWaitlist } from '../spots';
import { saveSignup } from '../tokens';

export interface SignedUp {
  result: SignupResult;
  name: string;
  /** An email was typed in the sheet (so `email_used: 'on_file'` means a race was lost). */
  typedEmail: boolean;
}

type Picked = { id: number; name: string };
const CLOSING = new Set(['signups_closed', 'event_cancelled', 'signups_full']);
const INPUT =
  'min-h-11 w-full rounded-button border border-outline-variant bg-surface px-3 text-text';

/** §5.7.3: pick a name (or "I'm not listed"), give an email when asked, guests, "Sign me up". */
export function SignUpSheet({
  event,
  open,
  onClose,
  onSignedUp,
}: {
  event: ClubEventDetail;
  open: boolean;
  onClose: () => void;
  onSignedUp: (done: SignedUp) => void;
}) {
  const isDesktop = useIsDesktop();
  const qc = useQueryClient();
  const directory = useShooters('', false, { enabled: open });
  const [query, setQuery] = useState('');
  // undefined: nothing chosen yet, so "Which one are you?" pre-picks when the picker lists it
  const [choice, setChoice] = useState<Picked | null | undefined>(undefined);
  const [notListed, setNotListed] = useState(false);
  const [typedName, setTypedName] = useState('');
  const [email, setEmail] = useState('');
  const [guests, setGuests] = useState(0);
  const [blocked, setBlocked] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ids = { search: useId(), name: useId(), email: useId(), help: useId() };

  const live = directory.data ? pickable(directory.data) : [];
  const me = getMe();
  const auto = live.find((s) => s.shooter_id === me);
  const picked: Picked | null =
    choice !== undefined ? choice : auto ? { id: auto.shooter_id, name: auto.display_name } : null;
  const pickedId = picked?.id ?? null;
  const pickedName = picked?.name ?? '';
  const check = useSignupCheck(event.id, notListed ? null : pickedId, open);
  const signUp = useSignUp(event.id);

  const asksEmail = notListed || (picked !== null && check.data?.has_email === false);
  const already = !notListed && check.data?.already_signed_up === true;
  const emailOk = !asksEmail || email.trim() !== '';
  const ready =
    emailOk &&
    (notListed ? typedName.trim() !== '' : picked !== null && check.isSuccess && !already);
  const checkError = check.isError
    ? check.error instanceof ApiError
      ? check.error.message
      : 'Something went wrong. Try again.'
    : null;

  // Focus follows the step: the new field after "I'm not listed", Change after a pick, the
  // search again on the way back, and the closed message when it replaces the button.
  const formRef = useRef<HTMLFormElement>(null);
  const blockedRef = useRef<HTMLParagraphElement>(null);
  const moved = useRef(false);
  useEffect(() => {
    if (!moved.current) return;
    const form = formRef.current;
    if (notListed) form?.querySelector<HTMLElement>(`[id="${ids.name}"]`)?.focus();
    else if (picked !== null) form?.querySelector<HTMLElement>('[data-change]')?.focus();
    else form?.querySelector<HTMLElement>(`[id="${ids.search}"]`)?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notListed, pickedId]);
  useEffect(() => {
    blockedRef.current?.focus();
  }, [blocked]);

  const choose = (next: Picked | null) => {
    moved.current = true;
    setChoice(next);
    setNotListed(false);
    setQuery('');
    setError(null);
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const body = notListed
      ? { shooter_id: null, name: typedName, email, guests }
      : { shooter_id: pickedId, name: null, email: asksEmail ? email : null, guests };
    signUp.mutate(body, {
      onSuccess: (result) => {
        saveSignup(result.registration_id, {
          eventId: event.id,
          token: result.token,
          status: result.status,
        });
        onSignedUp({
          result,
          name: notListed ? typedName.trim() : pickedName,
          typedEmail: asksEmail,
        });
      },
      onError: (err) => {
        if (err instanceof ApiError && err.status === 404 && err.code === 'http_404') {
          // The switches are refetched when the sheet closes (`close`), not now: the page's
          // not-found view would replace this sheet before the message could be read.
          setBlocked(SWITCHED_OFF);
        } else if (err instanceof ApiError && CLOSING.has(err.code)) {
          setBlocked(err.message);
          void qc.invalidateQueries({ queryKey: clubEventKey(event.id) });
        } else {
          setError(err instanceof ApiError ? err.message : 'Something went wrong. Try again.');
        }
      },
    });
  };

  const close = () => {
    if (blocked === SWITCHED_OFF) void qc.invalidateQueries({ queryKey: FEATURES_QUERY_KEY });
    onClose();
  };

  return (
    <Sheet open={open} onClose={close} title="Sign up" placement={isDesktop ? 'center' : 'bottom'}>
      <form ref={formRef} onSubmit={submit} noValidate className="flex max-w-md flex-col gap-4">
        {!notListed && picked === null && (
          <div className="flex flex-col gap-2">
            <label htmlFor={ids.search} className="text-sm font-medium">
              Who are you?
            </label>
            <input
              id={ids.search}
              type="search"
              placeholder="Search your name"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className={INPUT}
            />
            <ul className="flex flex-col">
              {searchShooters(live, query).map((s) => (
                <li key={s.shooter_id}>
                  <button
                    type="button"
                    onClick={() => choose({ id: s.shooter_id, name: s.display_name })}
                    className="min-h-11 w-full px-2 text-left hover:bg-surface"
                  >
                    {s.display_name}
                  </button>
                </li>
              ))}
              <li>
                <button
                  type="button"
                  onClick={() => {
                    moved.current = true;
                    setNotListed(true);
                    setChoice(null);
                  }}
                  className="min-h-11 w-full px-2 text-left text-accent hover:bg-surface"
                >
                  I'm not listed
                </button>
              </li>
            </ul>
          </div>
        )}

        {!notListed && picked !== null && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{picked.name}</span>
            <Button variant="ghost" data-change="" onClick={() => choose(null)}>
              Change
            </Button>
          </div>
        )}
        <div aria-live="polite" className="flex flex-col gap-1">
          {already && picked !== null && (
            <p className="text-sm">{picked.name} is already on the list.</p>
          )}
          {!notListed && check.data?.has_email === true && !already && (
            <p className="text-sm text-text-muted">{EMAIL_ON_FILE}</p>
          )}
        </div>
        {checkError !== null && (
          <p role="alert" className="text-sm text-error">
            {checkError}
          </p>
        )}

        {notListed && (
          <Button variant="ghost" className="self-start" onClick={() => choose(null)}>
            Pick from the list
          </Button>
        )}
        {notListed && (
          <label htmlFor={ids.name} className="flex flex-col gap-1 text-sm">
            Your first and last name
            <input
              id={ids.name}
              autoComplete="name"
              value={typedName}
              onChange={(e) => setTypedName(e.target.value)}
              className={INPUT}
            />
          </label>
        )}

        {asksEmail && (
          <div className="flex flex-col gap-1 text-sm">
            <label htmlFor={ids.email}>Your email</label>
            <input
              id={ids.email}
              type="email"
              inputMode="email"
              autoComplete="email"
              aria-describedby={ids.help}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={INPUT}
            />
            <p id={ids.help} className="text-text-muted">
              {EMAIL_HELP}
            </p>
          </div>
        )}

        {event.allow_guests && (
          <fieldset className="flex flex-wrap items-center gap-2 text-sm">
            <legend className="mb-1">Bringing guests?</legend>
            <Button
              variant="tonal"
              aria-label="Fewer guests"
              disabled={guests === 0}
              onClick={() => setGuests((n) => Math.max(0, n - 1))}
            >
              −
            </Button>
            <span aria-live="polite" data-guests="" className="min-w-6 text-center">
              {guests}
            </span>
            <Button
              variant="tonal"
              aria-label="More guests"
              disabled={guests >= event.max_guests}
              onClick={() => setGuests((n) => Math.min(event.max_guests, n + 1))}
            >
              +
            </Button>
          </fieldset>
        )}

        <p aria-live="polite" className="text-sm">
          {wouldWaitlist(event, 1 + guests) ? WAITLIST_WARNING : null}
        </p>
        {error !== null && (
          <p role="alert" className="text-sm text-error">
            {error}
          </p>
        )}
        {blocked !== null ? (
          <p ref={blockedRef} role="status" tabIndex={-1} className="font-medium outline-none">
            {blocked}
          </p>
        ) : (
          <Button type="submit" disabled={!ready} loading={signUp.isPending} className="w-full">
            Sign me up
          </Button>
        )}
      </form>
    </Sheet>
  );
}
