import { matchPath } from 'react-router';
import type { NavItem } from '../../app/registry';

/** Items the current role may see, in C10 `order`. */
export function visibleNav(items: readonly NavItem[], isAdmin: boolean): NavItem[] {
  return items
    .filter((item) => isAdmin || item.adminOnly !== true)
    .sort((a, b) => a.order - b.order);
}

/** Mobile: the (at most 4) `mobileTab` items become bottom tabs; everything else goes to "More". */
export function splitMobileNav(items: readonly NavItem[]): { tabs: NavItem[]; more: NavItem[] } {
  const tabs = items.filter((item) => item.mobileTab === true).slice(0, 4);
  return { tabs, more: items.filter((item) => !tabs.includes(item)) };
}

/** True when `pathname` is the item's page (`/` only exactly) or one of its `alsoActive` pages. */
export function isNavActive(item: NavItem, pathname: string): boolean {
  return [item.path, ...(item.alsoActive ?? [])].some(
    (path) => matchPath({ path, end: path === '/' }, pathname) !== null,
  );
}
