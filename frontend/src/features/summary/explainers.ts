import type { Explainer } from '../../components/charts/types';

export const explainers: Record<string, Explainer> = {
  'summary-card': {
    what: "A shareable snapshot of one shooter's Sundays in the chosen time window.",
    computed: [
      'Sundays shot counts every Sunday you came to, special shoots included.',
      'Rounds, average, best round and personal bests use regular rounds only, all round types.',
      'A personal best counts once there are at least 5 earlier rounds.',
      'Longest streak counts only Sundays inside the window.',
    ],
    scope: 'windowed',
    terms: ['special-shoot', 'personal-best', 'streak', 'round-types', 'time-window'],
  },
};
