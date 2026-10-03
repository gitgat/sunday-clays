export type TourTarget = 'sunday' | 'you' | 'insights' | 'trophies' | 'window';

export interface TourStep {
  target: TourTarget;
  title: string;
  body: string;
}

export const TOUR_STEPS: readonly TourStep[] = [
  {
    target: 'sunday',
    title: 'The latest Sunday',
    body: 'Every Sunday’s results land here once the scores are uploaded. Tap "Full results" for the whole sheet.',
  },
  {
    target: 'you',
    title: 'Which one are you?',
    body: 'Pick your name once and Home shows your own numbers, your next trophy and a link to your page. It is saved on this device only.',
  },
  {
    target: 'insights',
    title: 'Insights and fist bumps',
    body: 'Short, true things the numbers say about the club and its shooters. Tap the fist to give a bump. Bumps are anonymous.',
  },
  {
    target: 'trophies',
    title: 'Trophies',
    body: 'Trophies are earned by showing up and shooting. Your next one, and how close you are, shows on Home once you pick your name.',
  },
  {
    target: 'window',
    title: 'Time window',
    body: 'Charts and stats follow this window. 8W is the last 8 weeks. Pick 3M, 6M, 12M, YTD, All, or your own dates.',
  },
];
