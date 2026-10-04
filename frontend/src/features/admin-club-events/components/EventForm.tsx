import { useId, useState, type FormEvent } from 'react';
import { Button } from '../../../components/ui/Button';
import { Toggle } from '../../../components/ui/Toggle';
import { AdminError } from '../../admin/components/AdminError';
import { useCreateEvent, useUpdateEvent, type AdminEvent } from '../api';
import {
  defaultDeadline,
  shiftDate,
  fromEvent,
  notesCounter,
  NOTES_MAX,
  toBody,
  type FormValues,
} from '../form';

const INPUT =
  'min-h-11 w-full min-w-0 rounded-button border border-outline-variant bg-elevated px-3 text-text';

function Field({
  label,
  type = 'text',
  value,
  onChange,
  help,
}: {
  label: string;
  type?: 'text' | 'date' | 'time' | 'number';
  value: string;
  onChange: (value: string) => void;
  help?: string;
}) {
  const id = useId();
  const helpId = useId();
  return (
    <div className="flex min-w-0 flex-col gap-1 text-sm">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type={type}
        value={value}
        aria-describedby={help === undefined ? undefined : helpId}
        onChange={(e) => onChange(e.target.value)}
        className={INPUT}
      />
      {help !== undefined && (
        <p id={helpId} className="text-text-muted">
          {help}
        </p>
      )}
    </div>
  );
}

/** Create (event null) or edit an event in club time; the deadline follows the start date
 * (20:00 the day before) until it is edited by hand (§5.7.5). */
export function EventForm({
  event,
  onSaved,
}: {
  event: AdminEvent | null;
  onSaved: (id: number) => void;
}) {
  const [values, setValues] = useState<FormValues>(() => fromEvent(event));
  const [deadlineEdited, setDeadlineEdited] = useState(false);
  const create = useCreateEvent();
  const update = useUpdateEvent(event?.id ?? 0);
  const mutation = event === null ? create : update;
  const notesId = useId();

  const set = (patch: Partial<FormValues>) => setValues((v) => ({ ...v, ...patch }));
  const setDate = (date: string) => {
    if (deadlineEdited || date === '') return set({ date });
    if (event === null) {
      const deadline = defaultDeadline(date);
      return set({ date, deadlineDate: deadline.date, deadlineTime: deadline.time });
    }
    // Keep the saved deadline's offset from the start by shifting it the same number of days.
    return set({
      date,
      deadlineDate: shiftDate(event.deadline_local_date, event.local_date, date),
    });
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    mutation.mutate(toBody(values), { onSuccess: (saved) => onSaved(saved.id) });
  };

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-3">
      <Field label="Title" value={values.title} onChange={(title) => set({ title })} />
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Date" type="date" value={values.date} onChange={setDate} />
        <Field
          label="Start time"
          type="time"
          value={values.time}
          onChange={(time) => set({ time })}
        />
        <Field
          label="Sign-up deadline date"
          type="date"
          value={values.deadlineDate}
          onChange={(deadlineDate) => {
            setDeadlineEdited(true);
            set({ deadlineDate });
          }}
        />
        <Field
          label="Deadline time"
          type="time"
          value={values.deadlineTime}
          onChange={(deadlineTime) => {
            setDeadlineEdited(true);
            set({ deadlineTime });
          }}
        />
      </div>
      <div className="flex flex-col gap-1 text-sm">
        <label htmlFor={notesId}>Notes</label>
        <textarea
          id={notesId}
          rows={5}
          maxLength={NOTES_MAX}
          value={values.notes}
          onChange={(e) => set({ notes: e.target.value })}
          className={`${INPUT} py-2`}
        />
        <p className="self-end text-text-muted">{notesCounter(values.notes.length)}</p>
      </div>
      <Field
        label="Capacity"
        type="number"
        value={values.capacity}
        onChange={(capacity) => set({ capacity })}
        help="Leave empty for no limit"
      />
      <Toggle
        label="Guests allowed"
        checked={values.allowGuests}
        onChange={(allowGuests) => set({ allowGuests })}
      />
      {values.allowGuests && (
        <Field
          label="Most guests each"
          type="number"
          value={values.maxGuests}
          onChange={(maxGuests) => set({ maxGuests })}
        />
      )}
      {mutation.isError && <AdminError error={mutation.error} />}
      <Button type="submit" loading={mutation.isPending} className="self-start">
        {event === null ? 'Create event' : 'Save changes'}
      </Button>
    </form>
  );
}
