import { useMemo } from 'react';
import { ThinWindowNudge } from '../../components/ThinWindowNudge';
import { ChartFrame } from '../../components/charts/ChartFrame';
import { AboutBlock } from '../../components/ui/AboutBlock';
import type { ChartFull, TabularData } from '../../components/charts/types';
import { formatShortDate } from '../../lib/format';
import { useRoundTypes } from '../../lib/roundTypes';
import { enumCodec, useUrlState } from '../../lib/useUrlState';
import { useShooterStations, type EraSel } from './api';
import { ScopeLine, ShooterCoverageNote } from './CoverageNote';
import { deltaBarOption } from './chartOptions';
import { AllSetupsButton, EraToggle } from './EraToggle';
import { explainers } from './explainers';
import { pct, percentValue, signedPoints } from './format';
import { StackedTable } from './StackedTable';
import { inPeriod, useStationWindow } from './window';

const DELTA_COLUMNS: TabularData['columns'] = [
  { key: 'station', label: 'Station', type: 'string' },
  { key: 'hit_pct', label: 'Hit %', type: 'number' },
  { key: 'field_pct', label: 'Field hit %', type: 'number' },
  { key: 'delta', label: 'Versus field (pts)', type: 'number' },
  { key: 'rounds', label: 'Rounds', type: 'int' },
];

const ERA_CODEC = enumCodec<EraSel>(['current', 'all']);

export function StationBreakdown({ shooterId }: { shooterId: number }) {
  // The same `?era=` switch as the Stations page.
  const [era, setEra] = useUrlState<EraSel>('era', ERA_CODEC, 'current');
  const { data, isPending, isError } = useShooterStations(shooterId, era);
  const tw = useStationWindow();
  const when = inPeriod(tw.window);
  const [roundTypes] = useRoundTypes();
  const stations = data?.stations;
  // Fullscreen and the CSV: every station, the versus-field number blank until it has two rounds.
  const full = useMemo<ChartFull>(
    () => ({
      rows: (stations ?? []).map((s) => ({
        station: s.label,
        hit_pct: percentValue(s.hit_pct),
        field_pct: percentValue(s.field_pct),
        delta: s.n_rounds >= 2 ? percentValue(s.delta) : null,
        rounds: s.n_rounds,
      })),
      note: 'Every station. Versus field is blank until a station has been shot twice.',
    }),
    [stations],
  );
  if (isPending) return <p role="status">Loading station breakdown…</p>;
  if (isError || tw.failed) return <p role="alert">Could not load the station breakdown.</p>;
  const shown = data.stations.filter((s) => s.n_rounds >= 2);
  return (
    <section
      aria-label="Station breakdown for this shooter"
      className="flex min-w-0 flex-col gap-3"
    >
      <EraToggle era={era} onChange={setEra} resetDate={data.last_reset_date} />
      <ScopeLine era={era} />
      {data.stations.length === 0 ? (
        data.coverage.latest_date === null ? (
          <p className="text-text-muted">No station sheets for this shooter yet.</p>
        ) : data.coverage.n_sundays > 0 ? (
          <ThinWindowNudge
            sundays={0}
            label="Show every setup"
            message={`No station sheets for this shooter since the last reset ${when}.`}
            action={<AllSetupsButton onClick={() => setEra('all')} />}
          />
        ) : (
          <ThinWindowNudge
            sundays={0}
            label="Widen the time window"
            message={`No station sheets for this shooter ${when} (latest: ${formatShortDate(data.coverage.latest_date)}).`}
          />
        )
      ) : (
        <>
          <ShooterCoverageNote coverage={data.coverage} filtered={roundTypes.length > 0} />
          {shown.length === 0 ? (
            <ThinWindowNudge
              sundays={0}
              label="Widen the time window"
              message={`Deltas appear once a station has been shot at least twice ${when}.`}
            />
          ) : (
            <ChartFrame
              title="Where you lose targets"
              subtitle="Your hit % minus everyone’s on the same Sundays, in points (evened out for small samples)"
              option={deltaBarOption(shown.map((s) => ({ station: s.label, delta: s.delta })))}
              columns={DELTA_COLUMNS}
              rows={shown.map((s) => ({
                station: s.label,
                hit_pct: percentValue(s.hit_pct),
                field_pct: percentValue(s.field_pct),
                delta: percentValue(s.delta),
                rounds: s.n_rounds,
              }))}
              full={full}
              csvName={`shooter-${data.shooter_id}-stations`}
              ariaLabel="Bar chart of station hit % versus the field"
              urlKey="stdelta"
              zoom="none"
              explainer={explainers.stdelta}
            />
          )}
          <AboutBlock explainer={explainers['stdelta-table']} />
          <StackedTable
            caption="Station hit % for this shooter"
            headers={['Station', 'Hit %', 'Field', 'Versus field', 'Rounds']}
            rows={data.stations.map((s) => ({
              key: s.label,
              header: `Station ${s.label}`,
              cells: [
                pct(s.hit_pct),
                pct(s.field_pct),
                s.n_rounds >= 2 ? signedPoints(s.delta) : '—',
                s.n_rounds,
              ],
            }))}
          />
        </>
      )}
    </section>
  );
}
