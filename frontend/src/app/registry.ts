import type { LucideIcon } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { FeatureKey } from '../lib/features';

/** One navigation entry contributed by a feature's routes.tsx (C10). */
export interface NavItem {
  label: string;
  path: string;
  icon: LucideIcon;
  order: number;
  mobileTab?: boolean;
  adminOnly?: boolean;
  /** Plan 19 D21: hidden unless this launch switch's feature is visible to the viewer. */
  feature?: FeatureKey;
}

/** What every src/features/<name>/routes.tsx exports. */
export interface FeatureModule {
  routes: RouteObject[];
  nav?: NavItem[];
}

/**
 * Flattens feature modules in path order; nav items are sorted by `order`.
 * Throws a TypeError naming any module without an array `routes` export.
 */
export function collectFeatures(modules: Record<string, FeatureModule>): {
  routes: RouteObject[];
  nav: NavItem[];
} {
  const features = Object.keys(modules)
    .sort()
    .map((key) => {
      const feature = modules[key] as FeatureModule;
      if (!Array.isArray(feature.routes)) {
        throw new TypeError(`${key} must export routes`);
      }
      return feature;
    });
  return {
    routes: features.flatMap((feature) => feature.routes),
    nav: features.flatMap((feature) => feature.nav ?? []).sort((a, b) => a.order - b.order),
  };
}

const featureModules = import.meta.glob<FeatureModule>('../features/*/routes.tsx', {
  eager: true,
});

const collected = collectFeatures(featureModules);

/** Every feature's routes; children of the root route in router.tsx. */
export const featureRoutes: RouteObject[] = collected.routes;
/** Every feature's nav items, sorted by `order`. */
export const navItems: NavItem[] = collected.nav;
