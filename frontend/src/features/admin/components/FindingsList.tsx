import { useId } from 'react';
import { Card } from '../../../components/ui/Card';
import type { Finding } from '../api';
import { formatDay } from '../format';

const STATION_CODES = new Set([
  'station_score_mismatch',
  'station_name_unmatched',
  'station_round_ambiguous',
]);

export type FindingGroup = { code: string; severity: string; items: Finding[] };

/** Errors are excluded rows; non-error station codes get their own heading; the rest group by code, warnings first. */
export function groupFindings(findings: Finding[]): {
  excluded: Finding[];
  station: Finding[];
  other: FindingGroup[];
} {
  const excluded = findings.filter((f) => f.severity === 'error');
  const station = findings.filter((f) => f.severity !== 'error' && STATION_CODES.has(f.code));
  const byCode = new Map<string, Finding[]>();
  for (const f of findings) {
    if (f.severity === 'error' || STATION_CODES.has(f.code)) continue;
    byCode.set(f.code, [...(byCode.get(f.code) ?? []), f]);
  }
  const rank = (severity: string) => (severity === 'warning' ? 0 : 1);
  const other = [...byCode.entries()]
    .map(([code, items]) => ({ code, severity: (items[0] as Finding).severity, items }))
    .sort((a, b) => rank(a.severity) - rank(b.severity) || a.code.localeCompare(b.code));
  return { excluded, station, other };
}

/** FindingOut's location fields default to None (Plan 03), so the generated type has them optional: read with `?? null`. */
export function findingLocation(f: Finding): string {
  const row = f.row ?? null;
  const eventDate = f.event_date ?? null;
  return [
    f.sheet ?? null,
    row === null ? null : `row ${row}`,
    eventDate === null ? null : formatDay(eventDate),
    f.name ?? null,
  ]
    .filter((part): part is string => part !== null)
    .join(' · ');
}

function FindingItem({ finding }: { finding: Finding }) {
  const location = findingLocation(finding);
  return (
    <li className="flex flex-col">
      <span>{finding.message}</span>
      {location && <span className="text-xs text-text-muted">{location}</span>}
    </li>
  );
}

function FindingSection({ title, hint, items }: { title: string; hint: string; items: Finding[] }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="flex flex-col gap-2">
      <h3 id={id} className="font-medium">
        {title}
      </h3>
      <p className="text-xs text-text-muted">{`${items.length} · ${hint}`}</p>
      <ul className="flex flex-col gap-1">
        {items.map((f, i) => (
          <FindingItem key={`${f.code}-${i}`} finding={f} />
        ))}
      </ul>
    </section>
  );
}

export function FindingsList({ findings }: { findings: Finding[] }) {
  const { excluded, station, other } = groupFindings(findings);
  return (
    <Card title="Findings">
      {findings.length === 0 ? (
        <p className="text-text-muted">No findings.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {excluded.length > 0 && (
            <FindingSection
              title="Will not be imported"
              hint="These rows or tabs are left out; the rest can still be committed."
              items={excluded}
            />
          )}
          {station.length > 0 && (
            <FindingSection
              title="Station vs score"
              hint="Station sheets that disagree with the scores; fix names with an alias under Data & ops."
              items={station}
            />
          )}
          {other.length > 0 && (
            <div className="flex flex-col gap-2">
              <h3 className="font-medium">Other findings</h3>
              {other.map((g) => (
                <details key={g.code}>
                  <summary className="min-h-11 cursor-pointer py-2.5">{`${g.code} (${g.items.length}) · ${g.severity}`}</summary>
                  <ul className="flex flex-col gap-1 pl-4">
                    {g.items.map((f, i) => (
                      <FindingItem key={`${g.code}-${i}`} finding={f} />
                    ))}
                  </ul>
                </details>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
