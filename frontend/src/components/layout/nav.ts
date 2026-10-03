import type { NavItem } from '../../app/registry';
import type { FeatureKey } from '../../lib/features';

/**
 * Items the current role may see, in C10 `order`. An item naming a launch switch (`feature`) shows
 * only when `featureVisible(feature)` is true; without the check every gated item is hidden.
 */
export function visibleNav(
  items: readonly NavItem[],
  isAdmin: boolean,
  featureVisible: (key: FeatureKey) => boolean = () => false,
): NavItem[] {
  return items
    .filter((item) => isAdmin || item.adminOnly !== true)
    .filter((item) => item.feature === undefined || featureVisible(item.feature))
    .sort((a, b) => a.order - b.order);
}

/** Mobile: the (at most 4) `mobileTab` items become bottom tabs; everything else goes to "More". */
export function splitMobileNav(items: readonly NavItem[]): { tabs: NavItem[]; more: NavItem[] } {
  const tabs = items.filter((item) => item.mobileTab === true).slice(0, 4);
  return { tabs, more: items.filter((item) => !tabs.includes(item)) };
}
