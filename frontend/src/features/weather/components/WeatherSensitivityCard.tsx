import type { Explainer } from '../../../components/charts/types';
import { AllRoundTypesTag } from '../../shooters/components/InlineExplainer';
import { useWeatherSensitivity, type WeatherShooter } from '../api';
import { explainers } from '../explainers';
import { SENSITIVITY_COVARIATES, formatEffect, type SensitivityCovariate } from '../format';
import { AboutThis } from './AboutThis';

const LABELS: Record<SensitivityCovariate, string> = {
  temp_f: 'Temperature',
  gust_mph: 'Wind gusts',
  precip_in: 'Rain',
};

const ABOUT = explainers['profile-sensitivity'] as Explainer;

function Effects({ shooter }: { shooter: WeatherShooter }) {
  return (
    <>
      <ul className="flex flex-col gap-1">
        {SENSITIVITY_COVARIATES.map((covariate) => {
          const term = shooter.terms.find((t) => t.covariate === covariate);
          const text =
            term === undefined || term.beta === null
              ? 'not enough variety to tell'
              : formatEffect(term.per_unit, covariate);
          return (
            <li key={covariate}>
              {LABELS[covariate]}: {text}
            </li>
          );
        })}
      </ul>
      <AboutThis label="About weather sensitivity" explainer={ABOUT} />
      <p className="text-sm text-text-muted">
        Based on {shooter.n_rounds} rounds with weather. Estimates are pulled toward the club
        average so a few odd days do not overreact.
      </p>
    </>
  );
}

/** Profile section: how this shooter's results move with weather (shrunk, C7). */
export function WeatherSensitivityCard({ shooterId }: { shooterId: number }) {
  const query = useWeatherSensitivity();
  const shooter = query.data?.shooters.find((s) => s.shooter_id === shooterId);
  return (
    <section aria-label="Weather effects on this shooter" className="flex flex-col gap-2">
      <div className="flex">
        <AllRoundTypesTag />
      </div>
      {query.isPending ? (
        <p role="status">Loading weather effects…</p>
      ) : query.isError ? (
        <p role="alert">Could not load weather effects.</p>
      ) : shooter === undefined ? (
        <p>Not enough rounds with weather yet. This needs 10 rounds with a weather record.</p>
      ) : (
        <Effects shooter={shooter} />
      )}
    </section>
  );
}
