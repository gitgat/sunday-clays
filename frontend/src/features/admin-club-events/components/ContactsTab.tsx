import { useId, useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { Sheet } from '../../../components/ui/Sheet';
import { Skeleton } from '../../../components/ui/Skeleton';
import { formatDate } from '../../../lib/format';
import { useIsDesktop } from '../../../lib/useMediaQuery';
import type { ShooterOption } from '../../admin/api';
import { AdminError } from '../../admin/components/AdminError';
import { ShooterPicker } from '../../admin/components/ShooterPicker';
import { useContacts, useDeleteContact, useSetContact, type Contact } from '../api';
import { CONTACT_SOURCES } from '../form';
import { ConfirmSheet } from './ConfirmSheet';

type Editing =
  | { fixed: true; shooter: ShooterOption; email: string }
  | { fixed: false; shooter: ShooterOption | null; email: string };

/** Shooters' emails on file (§5.7.5): edit, remove, or add one for a shooter. */
export function ContactsTab() {
  const contacts = useContacts();
  const isDesktop = useIsDesktop();
  const save = useSetContact();
  const remove = useDeleteContact();
  const [editing, setEditing] = useState<Editing | null>(null);
  const [removing, setRemoving] = useState<Contact | null>(null);
  const emailId = useId();
  const close = () => {
    setEditing(null);
    save.reset();
  };
  if (contacts.data === undefined) return <Skeleton label="Loading emails on file" />;
  const source = (c: Contact) => CONTACT_SOURCES[c.source] ?? c.source;
  const lastUsed = (c: Contact) => (c.last_used_on === null ? '—' : formatDate(c.last_used_on));
  const actions = (c: Contact) => (
    <div className="flex flex-wrap gap-1">
      <Button
        variant="ghost"
        aria-label={`Edit email for ${c.name}`}
        onClick={() =>
          setEditing({
            shooter: { shooter_id: c.shooter_id, display_name: c.name },
            email: c.email,
            fixed: true,
          })
        }
      >
        Edit
      </Button>
      <Button
        variant="ghost"
        aria-label={`Remove email for ${c.name}`}
        onClick={() => setRemoving(c)}
      >
        Remove
      </Button>
    </div>
  );
  return (
    <div className="flex flex-col gap-3">
      <Button
        className="self-start"
        onClick={() => setEditing({ shooter: null, email: '', fixed: false })}
      >
        Add email
      </Button>
      {/* A table on a desktop, stacked rows on a phone, like the roster: never a sideways scroll. */}
      {isDesktop ? (
        <table className="w-full text-left text-sm">
          <thead>
            <tr>
              {['Name', 'Email', 'Source', 'Last used', 'Actions'].map((h) => (
                <th key={h} scope="col" className="py-2 pr-3 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {contacts.data.map((c) => (
              <tr key={c.shooter_id} className="border-t border-outline-variant align-top">
                <td className="break-words py-2 pr-3">{c.name}</td>
                <td className="break-all py-2 pr-3">{c.email}</td>
                <td className="py-2 pr-3">{source(c)}</td>
                <td className="py-2 pr-3">{lastUsed(c)}</td>
                <td className="py-2">{actions(c)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <ul aria-label="Emails on file" className="flex flex-col">
          {contacts.data.map((c) => (
            <li
              key={c.shooter_id}
              className="flex flex-col gap-1 border-t border-outline-variant py-2 text-sm"
            >
              <span className="break-words font-medium">{c.name}</span>
              <span className="break-all">{c.email}</span>
              <span>{`${source(c)} · last used ${lastUsed(c)}`}</span>
              {actions(c)}
            </li>
          ))}
        </ul>
      )}

      <Sheet
        open={editing !== null}
        onClose={close}
        title={editing?.fixed ? `Email for ${editing.shooter.display_name}` : 'Add email'}
        placement={isDesktop ? 'center' : 'bottom'}
      >
        {editing !== null && (
          <form
            noValidate
            className="flex max-w-md flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (editing.shooter === null) return;
              save.mutate(
                { shooterId: editing.shooter.shooter_id, email: editing.email },
                { onSuccess: close },
              );
            }}
          >
            {!editing.fixed && (
              <ShooterPicker
                label="Shooter"
                value={editing.shooter}
                onChange={(shooter) => setEditing({ ...editing, shooter })}
              />
            )}
            <label htmlFor={emailId} className="flex flex-col gap-1 text-sm">
              Email
              <input
                id={emailId}
                type="email"
                value={editing.email}
                onChange={(e) => setEditing({ ...editing, email: e.target.value })}
                className="min-h-11 rounded-button border border-outline-variant bg-elevated px-3"
              />
            </label>
            {save.isError && <AdminError error={save.error} />}
            <Button
              type="submit"
              disabled={editing.shooter === null}
              loading={save.isPending}
              className="self-start"
            >
              Save
            </Button>
          </form>
        )}
      </Sheet>

      <ConfirmSheet
        open={removing !== null}
        title="Remove an email"
        confirm="Remove"
        busy={remove.isPending}
        onClose={() => setRemoving(null)}
        onConfirm={() =>
          removing !== null &&
          remove.mutate(removing.shooter_id, { onSuccess: () => setRemoving(null) })
        }
      >
        <p>{removing === null ? '' : `Remove the email on file for ${removing.name}?`}</p>
        {remove.isError && <AdminError error={remove.error} />}
      </ConfirmSheet>
    </div>
  );
}
