import { useState } from 'react';
import { Link } from 'react-router';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { Skeleton } from '../../../components/ui/Skeleton';
import { AdminError } from '../../admin/components/AdminError';
import {
  downloadRosterCsv,
  fetchEmails,
  useAdminRoster,
  useCancelEvent,
  useDeleteEvent,
  useRestoreEvent,
  type AdminEvent,
} from '../api';
import { headHint } from '../form';
import { ConfirmSheet } from './ConfirmSheet';
import { EventForm } from './EventForm';
import { RosterTable } from './RosterTable';

/** One event: its form, its actions and its roster with emails (§5.7.5). */
export function EventEditor({ event, onDeleted }: { event: AdminEvent; onDeleted: () => void }) {
  const roster = useAdminRoster(event.id);
  const cancel = useCancelEvent(event.id);
  const restore = useRestoreEvent(event.id);
  const remove = useDeleteEvent(event.id);
  const [confirm, setConfirm] = useState<'cancel' | 'restore' | 'delete' | null>(null);
  const [message, setMessage] = useState<{ notice: string | null; failure: Error | null }>({
    notice: null,
    failure: null,
  });
  const setNotice = (notice: string) => setMessage({ notice, failure: null });
  const setFailure = (failure: Error) => setMessage({ notice: null, failure });
  const closeConfirm = () => {
    setConfirm(null);
    cancel.reset();
    restore.reset();
    remove.reset();
  };
  const hint = roster.data ? headHint(roster.data, event.capacity) : null;

  const copyEmails = async () => {
    let emails: string[];
    try {
      emails = await fetchEmails(event.id, 'going');
    } catch (error) {
      setFailure(error instanceof Error ? error : new Error('Could not read the emails.'));
      return;
    }
    if (emails.length === 0) {
      setNotice('No emails to copy');
      return;
    }
    try {
      await navigator.clipboard.writeText(emails.join(', '));
      setNotice(`Copied ${emails.length} email${emails.length === 1 ? '' : 's'}`);
    } catch {
      setFailure(new Error('Could not copy the emails.'));
    }
  };
  const exportCsv = async () => {
    try {
      await downloadRosterCsv(event);
    } catch (error) {
      setFailure(error instanceof Error ? error : new Error('Could not export the CSV.'));
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Card title={event.title}>
        <EventForm key={event.id} event={event} onSaved={() => setNotice('Saved')} />
      </Card>
      <Card title="Sign-ups">
        <div className="mb-3 flex flex-wrap gap-2">
          <Button variant="tonal" onClick={() => void exportCsv()}>
            Export CSV
          </Button>
          <Button variant="tonal" onClick={() => void copyEmails()}>
            Copy emails
          </Button>
          {event.state === 'cancelled' ? (
            <Button variant="tonal" onClick={() => setConfirm('restore')}>
              Restore
            </Button>
          ) : (
            <Button variant="tonal" onClick={() => setConfirm('cancel')}>
              Cancel event
            </Button>
          )}
          <Link
            to={`/club-events/${event.id}`}
            className="inline-flex min-h-11 items-center rounded-button px-3 text-sm text-accent underline"
          >
            Open member page
          </Link>
          <Button variant="danger" onClick={() => setConfirm('delete')}>
            Delete
          </Button>
        </div>
        <p aria-live="polite" className="text-sm text-text-muted">
          {message.notice ?? ''}
        </p>
        {message.failure !== null && <AdminError error={message.failure} />}
        {hint !== null && <p className="text-sm">{hint}</p>}
        {roster.isError ? (
          <AdminError error={roster.error} />
        ) : roster.data === undefined ? (
          <Skeleton label="Loading sign-ups" />
        ) : (
          <RosterTable eventId={event.id} rows={roster.data} />
        )}
      </Card>
      <ConfirmSheet
        open={confirm === 'cancel'}
        title="Cancel this club event"
        confirm="Cancel event"
        busy={cancel.isPending}
        onClose={closeConfirm}
        onConfirm={() =>
          cancel.mutate(undefined, {
            onSuccess: () => {
              closeConfirm();
              setNotice('Club event cancelled');
            },
          })
        }
      >
        <p>Cancel this club event? Everyone signed up will see it was cancelled.</p>
        {cancel.isError && <AdminError error={cancel.error} />}
      </ConfirmSheet>
      <ConfirmSheet
        open={confirm === 'restore'}
        title="Restore this club event"
        confirm="Restore"
        variant="primary"
        busy={restore.isPending}
        onClose={closeConfirm}
        onConfirm={() =>
          restore.mutate(undefined, {
            onSuccess: () => {
              closeConfirm();
              setNotice('Club event restored');
            },
          })
        }
      >
        <p>Restore this club event?</p>
        {restore.isError && <AdminError error={restore.error} />}
      </ConfirmSheet>
      <ConfirmSheet
        open={confirm === 'delete'}
        title="Delete this club event"
        confirm="Delete"
        busy={remove.isPending}
        onClose={closeConfirm}
        onConfirm={() => remove.mutate(undefined, { onSuccess: onDeleted })}
      >
        <p>{`Delete ${event.title} and its sign-up list? This can't be undone.`}</p>
        {remove.isError && <AdminError error={remove.error} />}
      </ConfirmSheet>
    </div>
  );
}
