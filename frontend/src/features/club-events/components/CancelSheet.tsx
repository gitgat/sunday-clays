import { useQueryClient } from '@tanstack/react-query';
import { useId, useState, type FormEvent } from 'react';
import { ApiError } from '../../../api/errors';
import { Button } from '../../../components/ui/Button';
import { Sheet } from '../../../components/ui/Sheet';
import { useIsDesktop } from '../../../lib/useMediaQuery';
import { FEATURES_QUERY_KEY } from '../../../lib/features';
import { clubEventKey, useCancelSignup } from '../api';
import { cancelOwnQuestion, SWITCHED_OFF } from '../format';
import { forgetSignup } from '../tokens';

export type CancelTarget =
  | { kind: 'own'; registrationId: number; token: string; guests: number }
  | { kind: 'other'; registrationId: number; name: string };

const INPUT =
  'min-h-11 w-full rounded-button border border-outline-variant bg-surface px-3 text-text';

/** D10: this device's own spot by its token, anyone else's by the email used to sign up. */
export function CancelSheet({
  eventId,
  target,
  onClose,
  onCancelled,
}: {
  eventId: number;
  target: CancelTarget | null;
  onClose: () => void;
  /** Called once the spot is cancelled, before the sheet closes, with the words to announce. */
  onCancelled?: (announcement: string) => void;
}) {
  const isDesktop = useIsDesktop();
  const cancel = useCancelSignup(eventId);
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [switchedOff, setSwitchedOff] = useState(false);
  const qc = useQueryClient();
  const emailId = useId();
  if (target === null) return null;

  const close = () => {
    if (switchedOff) void qc.invalidateQueries({ queryKey: FEATURES_QUERY_KEY });
    setSwitchedOff(false);
    setEmail('');
    setError(null);
    cancel.reset();
    onClose();
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    const input =
      target.kind === 'own'
        ? { registrationId: target.registrationId, token: target.token }
        : { registrationId: target.registrationId, email };
    cancel.mutate(input, {
      onSuccess: () => {
        forgetSignup(target.registrationId);
        onCancelled?.(
          target.kind === 'own'
            ? 'Your spot was cancelled.'
            : `${target.name}'s spot was cancelled.`,
        );
        close();
      },
      onError: (err) => {
        if (err instanceof ApiError && err.status === 404 && err.code === 'http_404') {
          // The switches are refetched on close, so the message can be read first (see SignUpSheet).
          setError(SWITCHED_OFF);
          setSwitchedOff(true);
        } else {
          if (
            err instanceof ApiError &&
            (err.code === 'registration_not_found' || err.code === 'event_started')
          ) {
            void qc.invalidateQueries({ queryKey: clubEventKey(eventId) });
          }
          setError(err instanceof ApiError ? err.message : 'Something went wrong. Try again.');
        }
      },
    });
  };

  return (
    <Sheet
      open
      onClose={close}
      title={target.kind === 'own' ? 'Cancel my spot' : `Cancel ${target.name}'s spot`}
      placement={isDesktop ? 'center' : 'bottom'}
    >
      <form onSubmit={submit} noValidate className="flex max-w-md flex-col gap-3">
        {target.kind === 'own' ? (
          <p>{cancelOwnQuestion(target.guests)}</p>
        ) : (
          <label htmlFor={emailId} className="flex flex-col gap-1 text-sm">
            Type the email used for this sign-up.
            <input
              id={emailId}
              type="email"
              inputMode="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={INPUT}
            />
          </label>
        )}
        {error !== null && (
          <p role="alert" className="text-sm text-error">
            {error}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant="danger" loading={cancel.isPending}>
            {target.kind === 'own' ? 'Cancel my spot' : 'Cancel spot'}
          </Button>
          <Button type="button" variant="ghost" onClick={close}>
            Keep it
          </Button>
        </div>
      </form>
    </Sheet>
  );
}
