import { http, HttpResponse } from 'msw';
import type { FeatureSwitch } from './api';

/** The six switches as the API lists them (labels and descriptions as in domain/features.py). */
export const featureSwitches: FeatureSwitch[] = [
  {
    key: 'link_previews',
    label: 'Link previews',
    description:
      "Links shared in chat apps show the Sunday's date, how many shot and the round type. While off, every link shows the plain club preview.",
    enabled: true,
    updated_at: '2026-10-02T18:04:11+00:00',
    updated_on: '2026-10-02',
  },
  {
    key: 'tour_glossary',
    label: 'Welcome tour and glossary',
    description:
      'A 5-step tour on a first visit to Home, the Glossary page, and "Words used here" links in chart explainers.',
    enabled: false,
    updated_at: null,
    updated_on: null,
  },
  {
    key: 'weekly_recap',
    label: 'Weekly recap',
    description: 'Admin tool: paste-ready text and an image of a Sunday for the club email.',
    enabled: false,
    updated_at: null,
    updated_on: null,
  },
  {
    key: 'pwa',
    label: 'Add to Home Screen',
    description: 'Lets phones install the app, and shows a small install tip on Home.',
    enabled: false,
    updated_at: null,
    updated_on: null,
  },
  {
    key: 'club_milestones',
    label: 'Club milestones',
    description:
      'Club totals such as clays thrown and Sundays held, dated at the Sunday each round number was passed. Home card and Club page.',
    enabled: false,
    updated_at: null,
    updated_on: null,
  },
  {
    key: 'summary_card',
    label: 'Summary card',
    description: 'A shareable card on every profile for the chosen time window.',
    enabled: false,
    updated_at: null,
    updated_on: null,
  },
];

/**
 * The switches every test sees unless it overrides them with server.use. The tour and the PWA are
 * off by default: on, the tour would open over every Home test and the PWA would try to register a
 * service worker. Their own tests turn them on.
 */
export const DEFAULT_ON = ['link_previews', 'weekly_recap', 'club_milestones', 'summary_card'];

export const handlers = [
  http.get('*/api/features', () =>
    HttpResponse.json({ switches: Object.fromEntries(DEFAULT_ON.map((key) => [key, true])) }),
  ),
  http.get('*/api/admin/features', () => HttpResponse.json(featureSwitches)),
  http.put('*/api/admin/features/:key', async ({ params, request }) => {
    const row = featureSwitches.find((s) => s.key === params.key);
    if (row === undefined) {
      return HttpResponse.json(
        { error: { code: 'feature_not_found', message: 'No such switch' } },
        { status: 404 },
      );
    }
    const { enabled } = (await request.json()) as { enabled: boolean };
    return HttpResponse.json({
      ...row,
      enabled,
      updated_at: '2026-10-03T05:30:00+00:00',
      updated_on: '2026-10-02',
    });
  }),
];
