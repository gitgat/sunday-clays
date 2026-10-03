import { describe, expect, it } from 'vitest';
import { nav, routes } from './routes';

describe('glossary routes', () => {
  it('adds a gated Glossary nav item at 135 and no header filters', () => {
    expect(nav.map(({ label, path, order, feature }) => ({ label, path, order, feature }))).toEqual(
      [{ label: 'Glossary', path: '/glossary', order: 135, feature: 'tour_glossary' }],
    );
    expect(routes[0]?.handle).toEqual({ filters: { roundType: false, window: false } });
  });
});
