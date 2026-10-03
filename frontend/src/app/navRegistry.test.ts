import { matchRoutes } from 'react-router';
import { describe, expect, it } from 'vitest';
import { featureRoutes, navItems, type FeatureModule } from './registry';

/** C10: fixed nav orders; any other feature takes an unused value >= 140. */
const FIXED_ORDER: Record<string, number> = {
  home: 10,
  events: 20,
  leaderboards: 30,
  shooters: 40,
  club: 50,
  explorer: 60,
  achievements: 70,
  stations: 80,
  weather: 90,
  compare: 100,
  yir: 110,
  records: 120,
  race: 130,
  glossary: 135,
  about: 140,
  admin: 900,
  'admin-identity': 910,
  'admin-ops': 920,
  'admin-analytics': 930,
  'admin-features': 940,
};
/** C10: exactly these features are mobile tabs. */
const MOBILE_TABS = new Set(['home', 'events', 'leaderboards', 'shooters']);

const modules = import.meta.glob<FeatureModule>('../features/*/routes.tsx', { eager: true });
const features = Object.entries(modules).map(([file, mod]) => ({
  name: /features\/([^/]+)\/routes\.tsx$/.exec(file)?.[1] ?? file,
  nav: mod.nav ?? [],
}));

describe('feature registry', () => {
  it('discovers at least the home feature', () => {
    expect(features.map((f) => f.name)).toContain('home');
  });

  it('uses the C10 nav order for listed features and an unused order >= 140 otherwise', () => {
    const used = new Map<number, string>();
    for (const { name, nav } of features) {
      for (const item of nav) {
        const fixed = FIXED_ORDER[name];
        if (fixed === undefined) {
          expect(item.order, `${name} order`).toBeGreaterThanOrEqual(140);
          expect(Object.values(FIXED_ORDER), `${name} order`).not.toContain(item.order);
        } else {
          expect(item.order, `${name} order`).toBe(fixed);
        }
        const owner = used.get(item.order);
        expect(
          owner === undefined || owner === name,
          `order ${item.order} shared by ${owner} and ${name}`,
        ).toBe(true);
        used.set(item.order, name);
      }
    }
  });

  it('lets only home, events, leaderboards and shooters be mobile tabs', () => {
    const tabFeatures = features
      .filter((f) => f.nav.some((i) => i.mobileTab === true))
      .map((f) => f.name);
    expect(tabFeatures.filter((name) => !MOBILE_TABS.has(name))).toEqual([]);
  });

  it('makes home, events, leaderboards and shooters mobile tabs whenever they are registered', () => {
    const present = features.filter((f) => MOBILE_TABS.has(f.name));
    expect(present.map((f) => f.name)).toContain('home');
    for (const { name, nav } of present) {
      expect(
        nav.some((i) => i.mobileTab === true),
        `${name} needs a nav item with mobileTab: true`,
      ).toBe(true);
    }
  });

  it('marks every admin feature nav item adminOnly', () => {
    for (const { name, nav } of features.filter((f) => f.name.startsWith('admin'))) {
      for (const item of nav) expect(item.adminOnly, `${name} ${item.label}`).toBe(true);
    }
  });

  it('points every nav item at a registered route', () => {
    const tree = [{ path: '/', children: featureRoutes }];
    for (const item of navItems) {
      expect(matchRoutes(tree, item.path), item.path).not.toBeNull();
    }
  });

  it('exposes nav items sorted by order', () => {
    const orders = navItems.map((i) => i.order);
    expect(orders).toEqual([...orders].sort((a, b) => a - b));
  });
});
