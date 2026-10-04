import { useState } from 'react';
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
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [failure, setFailure] = useState<Error | null>(null);
  const hint = roster.data ? headHint(roster.data, event.capacity) : null;

  const copyEmails = async () => {
    try {
      const emails = await fetchEmails(event.id, 'going');
      if (emails.length === 0) {
        setNotice('No emails to copy');
        return;
      }
      await navigator.clipboard.writeText(emails.join(', '));
      setNotice(`Copied ${emails.length} email${emails.length === 1 ? '' : 's'}`);
    } catch (error) {
      setFailure(error instanceof Error ? error : new Error('Could not copy the emails.'));
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
            <Button variant="tonal" loading={restore.isPending} onClick={() => restore.mutate()}>
              Restore
            </Button>
          ) : (
            <Button variant="tonal" loading={cancel.isPending} onClick={() => cancel.mutate()}>
              Cancel event
            </Button>
          )}
          <Button variant="danger" onClick={() => setConfirmDelete(true)}>
            Delete
          </Button>
        </div>
        {notice !== null && (
          <p aria-live="polite" className="text-sm text-text-muted">
            {notice}
          </p>
        )}
        {failure !== null && <AdminError error={failure} />}
        {cancel.isError && <AdminError error={cancel.error} />}
        {restore.isError && <AdminError error={restore.error} />}
        {hint !== null && <p className="text-sm">{hint}</p>}
        {roster.data === undefined ? (
          <Skeleton label="Loading sign-ups" />
        ) : (
          <RosterTable eventId={event.id} rows={roster.data} />
        )}
      </Card>
      <ConfirmSheet
        open={confirmDelete}
        title="Delete this club event"
        confirm="Delete"
        busy={remove.isPending}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => remove.mutate(undefined, { onSuccess: onDeleted })}
      >
        <p>{`Delete ${event.title} and its sign-up list? This can't be undone.`}</p>
        {remove.isError && <AdminError error={remove.error} />}
      </ConfirmSheet>
    </div>
  );
}
