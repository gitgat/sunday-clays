import { useId, useState, type FormEvent } from 'react';
import { ApiError } from '../../../api/errors';
import { Button } from '../../../components/ui/Button';
import { Sheet } from '../../../components/ui/Sheet';
import { useIsDesktop } from '../../../lib/useMediaQuery';
import { useCancelSignup } from '../api';
import { cancelOwnQuestion } from '../format';
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
}: {
  eventId: number;
  target: CancelTarget | null;
  onClose: () => void;
}) {
  const isDesktop = useIsDesktop();
  const cancel = useCancelSignup(eventId);
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const emailId = useId();
  if (target === null) return null;

  const close = () => {
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
        close();
      },
      onError: (err) => {
        setError(err instanceof ApiError ? err.message : 'Something went wrong. Try again.');
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
