import { useId, useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { Sheet } from '../../../components/ui/Sheet';
import { useIsDesktop } from '../../../lib/useMediaQuery';
import type { ShooterOption } from '../../admin/api';
import { AdminError } from '../../admin/components/AdminError';
import { ShooterPicker } from '../../admin/components/ShooterPicker';
import {
  useLinkRegistration,
  useRemoveRegistration,
  useResetCancelLimit,
  useSetGuests,
  type AdminRosterRow,
} from '../api';
import { sourceLabel, statusLabel } from '../form';
import { ConfirmSheet } from './ConfirmSheet';

type Action =
  | { kind: 'remove'; row: AdminRosterRow }
  | { kind: 'guests'; row: AdminRosterRow }
  | { kind: 'link'; row: AdminRosterRow; shooter: ShooterOption | null; hasEmail: boolean | null };

function linkWarning(name: string, hasEmail: boolean | null): string {
  return hasEmail === true
    ? `${name} already has an email on file. The email typed at sign-up will be deleted.`
    : `If ${name} already has an email on file, the email typed at sign-up will be deleted.`;
}

/** The organizer's roster (§5.7.5): a table on a desktop, stacked rows on a phone. */
export function RosterTable({
  eventId,
  rows,
}: {
  eventId: number;
  rows: readonly AdminRosterRow[];
}) {
  const isDesktop = useIsDesktop();
  const isDesktopSheet = isDesktop ? 'center' : 'bottom';
  const [action, setAction] = useState<Action | null>(null);
  const [guests, setGuests] = useState('0');
  const [result, setResult] = useState<string | null>(null);
  const remove = useRemoveRegistration(eventId);
  const setGuestsMutation = useSetGuests(eventId);
  const link = useLinkRegistration(eventId);
  const reset = useResetCancelLimit(eventId);
  const guestsId = useId();
  const close = () => {
    setAction(null);
    remove.reset();
    setGuestsMutation.reset();
    link.reset();
  };

  const actions = (row: AdminRosterRow) => {
    const active = row.status === 'going' || row.status === 'waitlist';
    if (!active) return null;
    return (
      <div className="flex flex-wrap gap-1">
        <Button
          variant="ghost"
          aria-label={`Remove ${row.name}`}
          onClick={() => setAction({ kind: 'remove', row })}
        >
          Remove
        </Button>
        <Button
          variant="ghost"
          aria-label={`Guests for ${row.name}`}
          onClick={() => {
            setGuests(String(row.guests));
            setAction({ kind: 'guests', row });
          }}
        >
          Guests
        </Button>
        {row.shooter_id === null && (
          <Button
            variant="ghost"
            aria-label={`Link ${row.name}`}
            onClick={() => setAction({ kind: 'link', row, shooter: null, hasEmail: null })}
          >
            Link
          </Button>
        )}
        {row.cancel_fail_count >= 5 && (
          <Button
            variant="ghost"
            aria-label={`Reset cancel limit for ${row.name}`}
            onClick={() => reset.mutate(row.id)}
          >
            Reset cancel limit
          </Button>
        )}
      </div>
    );
  };
  const hint = (row: AdminRosterRow) => {
    const s = row.suggested_shooter;
    if (row.shooter_id !== null || s === null) return null;
    return (
      <Button
        variant="ghost"
        onClick={() =>
          setAction({
            kind: 'link',
            row,
            shooter: { shooter_id: s.id, display_name: s.name },
            hasEmail: s.has_email,
          })
        }
      >
        {`Looks like ${s.name}? Link`}
      </Button>
    );
  };

  const submitLink = (registrationId: number, shooterId: number) =>
    link.mutate(
      { registrationId, shooterId },
      {
        onSuccess: (done) => {
          setResult(
            done.email_discarded
              ? 'Linked. The email typed at sign-up was deleted; the email on file stays.'
              : done.email_moved
                ? 'Linked. The email typed at sign-up is now on file for this shooter.'
                : 'Linked.',
          );
          close();
        },
      },
    );
  const linkButton = (act: Extract<Action, { kind: 'link' }>) => {
    const picked = act.shooter;
    return (
      <Button
        disabled={picked === null}
        loading={link.isPending}
        className="self-start"
        onClick={picked === null ? undefined : () => submitLink(act.row.id, picked.shooter_id)}
      >
        Link
      </Button>
    );
  };

  return (
    <div className="flex flex-col gap-2">
      {result !== null && <p role="note">{result}</p>}
      {isDesktop ? (
        <table className="w-full text-left text-sm">
          <thead>
            <tr>
              {['Name', 'Email', 'Guests', 'Status', 'Signed up', 'Source', 'Actions'].map((h) => (
                <th key={h} scope="col" className="py-2 pr-3 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t border-outline-variant align-top">
                <td className="break-words py-2 pr-3">
                  {row.name}
                  {hint(row)}
                </td>
                <td className="break-all py-2 pr-3">{row.email ?? '—'}</td>
                <td className="py-2 pr-3">{row.guests}</td>
                <td className="py-2 pr-3">{statusLabel(row)}</td>
                <td className="py-2 pr-3">{row.signed_up_local}</td>
                <td className="py-2 pr-3">{sourceLabel(row)}</td>
                <td className="py-2">{actions(row)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <ul aria-label="Sign-ups" className="flex flex-col">
          {rows.map((row) => (
            <li
              key={row.id}
              className="flex flex-col gap-1 border-t border-outline-variant py-2 text-sm"
            >
              <span className="break-words font-medium">{row.name}</span>
              {hint(row)}
              <span className="break-all">{row.email ?? '—'}</span>
              <span>{`${statusLabel(row)} · ${row.guests} guests · ${sourceLabel(row)} · ${row.signed_up_local}`}</span>
              {actions(row)}
            </li>
          ))}
        </ul>
      )}

      <ConfirmSheet
        open={action?.kind === 'remove'}
        title="Remove from the list"
        confirm="Remove"
        busy={remove.isPending}
        onClose={close}
        onConfirm={() => action !== null && remove.mutate(action.row.id, { onSuccess: close })}
      >
        <p>{action?.kind === 'remove' ? `Remove ${action.row.name} from the list?` : ''}</p>
        {remove.isError && <AdminError error={remove.error} />}
      </ConfirmSheet>

      <Sheet
        open={action?.kind === 'guests'}
        onClose={close}
        title={action?.kind === 'guests' ? `Guests for ${action.row.name}` : 'Guests'}
        placement={isDesktopSheet}
      >
        {action?.kind === 'guests' && (
          <form
            className="flex max-w-xs flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              setGuestsMutation.mutate(
                { registrationId: action.row.id, guests: Number(guests) },
                { onSuccess: close },
              );
            }}
          >
            <label htmlFor={guestsId} className="flex flex-col gap-1 text-sm">
              Guests
              <input
                id={guestsId}
                type="number"
                min={0}
                max={10}
                value={guests}
                onChange={(e) => setGuests(e.target.value)}
                className="min-h-11 rounded-button border border-outline-variant bg-elevated px-3"
              />
            </label>
            {setGuestsMutation.isError && <AdminError error={setGuestsMutation.error} />}
            <Button type="submit" loading={setGuestsMutation.isPending} className="self-start">
              Save
            </Button>
          </form>
        )}
      </Sheet>

      <Sheet
        open={action?.kind === 'link'}
        onClose={close}
        title={action?.kind === 'link' ? `Link ${action.row.name} to a shooter` : 'Link'}
        placement={isDesktopSheet}
      >
        {action?.kind === 'link' && (
          <div className="flex max-w-md flex-col gap-3">
            <ShooterPicker
              label="Shooter"
              value={action.shooter}
              onChange={(shooter) => setAction({ ...action, shooter, hasEmail: null })}
            />
            {action.shooter !== null && action.row.email !== null && (
              <p>{linkWarning(action.shooter.display_name, action.hasEmail)}</p>
            )}
            {link.isError && <AdminError error={link.error} />}
            {linkButton(action)}
          </div>
        )}
      </Sheet>
    </div>
  );
}
