import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { AdminError } from '../../admin/components/AdminError';
import { JobProgress } from '../../admin/components/JobProgress';
import { ShooterPicker } from '../../admin/components/ShooterPicker';
import { useCreateRule } from '../api';
import { buildRulePayload, EMPTY_FIELDS, RULE_LABELS, RULE_TYPES } from '../rules';
import type { RuleFields, RuleType } from '../rules';
import { ROUND_TYPE_OPTIONS, SelectField, STATUS_OPTIONS, TextField } from './Fields';
import { RoundPicker } from './RoundPicker';

type SetField = <K extends keyof RuleFields>(key: K, value: RuleFields[K]) => void;

/** One typed form per C5 rule type; no raw-JSON editor (Plan 08 T5b). */
function TypeFields({ type, f, set }: { type: RuleType; f: RuleFields; set: SetField }) {
  switch (type) {
    case 'merge_shooter':
      return (
        <>
          <ShooterPicker
            label="Merge this shooter"
            value={f.source}
            onChange={(v) => set('source', v)}
          />
          <ShooterPicker
            label="Into this shooter"
            value={f.target}
            onChange={(v) => set('target', v)}
          />
        </>
      );
    case 'rename_shooter':
      return (
        <>
          <ShooterPicker label="Shooter" value={f.shooter} onChange={(v) => set('shooter', v)} />
          <TextField
            label="New display name"
            value={f.displayName}
            onChange={(v) => set('displayName', v)}
          />
        </>
      );
    case 'score_override':
      return (
        <>
          <RoundPicker value={f.round} onChange={(v) => set('round', v)} />
          <TextField
            label="Corrected score"
            type="number"
            value={f.score}
            onChange={(v) => set('score', v)}
          />
        </>
      );
    case 'hide_round':
      return <RoundPicker value={f.round} onChange={(v) => set('round', v)} />;
    case 'round_type_override':
      return (
        <>
          <TextField
            label="Event date"
            type="date"
            value={f.eventDate}
            onChange={(v) => set('eventDate', v)}
          />
          <SelectField
            label="Round type"
            value={f.roundType}
            onChange={(v) => set('roundType', v)}
            options={ROUND_TYPE_OPTIONS}
          />
        </>
      );
    case 'set_status':
      return (
        <>
          <ShooterPicker label="Shooter" value={f.shooter} onChange={(v) => set('shooter', v)} />
          <SelectField
            label="Status"
            value={f.status}
            onChange={(v) => set('status', v)}
            options={STATUS_OPTIONS}
          />
        </>
      );
    case 'station_reset':
      return (
        <>
          <TextField
            label="Station (like 7 or 7A)"
            value={f.stationNo}
            onChange={(v) => set('stationNo', v.toUpperCase())}
          />
          <TextField
            label="Effective date"
            type="date"
            value={f.effectiveDate}
            onChange={(v) => set('effectiveDate', v)}
          />
          <TextField
            label="What changed"
            value={f.resetNote}
            onChange={(v) => set('resetNote', v)}
          />
        </>
      );
    case 'alias_name':
      return (
        <>
          <TextField label="Name key" value={f.nameKey} onChange={(v) => set('nameKey', v)} />
          <p className="text-xs text-text-muted">
            The normalized name from the data issue, e.g. “hadley dik”.
          </p>
          <ShooterPicker label="Belongs to" value={f.shooter} onChange={(v) => set('shooter', v)} />
        </>
      );
  }
}

export function RuleCreateForm() {
  const [type, setType] = useState<RuleType>('merge_shooter');
  const [fields, setFields] = useState<RuleFields>(EMPTY_FIELDS);
  const [note, setNote] = useState('');
  const create = useCreateRule();
  const qc = useQueryClient();
  const payload = buildRulePayload(type, fields);
  const set: SetField = (key, value) => setFields((prev) => ({ ...prev, [key]: value }));
  const refresh = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ['/api/admin/rules'] });
  }, [qc]);

  return (
    <div className="flex flex-col gap-3">
      <SelectField
        label="Rule type"
        value={type}
        onChange={(v) => {
          setType(v as RuleType);
          setFields(EMPTY_FIELDS);
          setNote('');
          create.reset();
        }}
        options={RULE_TYPES.map((t) => ({ value: t, label: RULE_LABELS[t] }))}
      />
      <TypeFields key={type} type={type} f={fields} set={set} />
      <TextField label="Note (optional)" value={note} onChange={setNote} />
      <Button
        disabled={payload === null || create.isPending}
        onClick={() =>
          payload &&
          create.mutate(
            { rule_type: type, payload, note: note.trim() || null },
            {
              // Reset so a second click cannot create the same rule twice.
              onSuccess: () => {
                setFields(EMPTY_FIELDS);
                setNote('');
              },
            },
          )
        }
      >
        Create rule
      </Button>
      {create.isError && <AdminError error={create.error} />}
      {create.isSuccess && (
        <JobProgress
          jobId={create.data.job_id}
          label={`Rule #${create.data.rule_id}`}
          onSettled={refresh}
        />
      )}
    </div>
  );
}
