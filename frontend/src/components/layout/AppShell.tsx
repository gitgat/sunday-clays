import { useState, type ReactNode } from 'react';
import { Outlet } from 'react-router';
import { navItems, type NavItem } from '../../app/registry';
import type { FeatureKey } from '../../lib/features';
import { useIsDesktop } from '../../lib/useMediaQuery';
import { cx } from '../ui/cx';
import { Sheet } from '../ui/Sheet';
import { BottomTabs } from './BottomTabs';
import { ContentHeader } from './ContentHeader';
import { NavList } from './NavList';
import { SideNav } from './SideNav';
import { TopBar } from './TopBar';
import { splitMobileNav, visibleNav } from './nav';

export interface AppShellProps {
  /** Shows `adminOnly` nav items. */
  isAdmin?: boolean;
  /** Account controls (e.g. log out), shown in the side nav and in the "More" sheet. */
  account?: ReactNode;
  /** Defaults to the feature registry's nav items. */
  items?: readonly NavItem[];
  /** Whether a launch-switched nav item's feature is visible (Plan 19 D21); default: never. */
  featureVisible?: (key: FeatureKey) => boolean;
}

const SKIP_LINK =
  'sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-button focus:bg-primary focus:px-4 focus:py-2';

/**
 * Layout route (C10): side nav (app name + pages) and a content-header filter bar at ≥1024px;
 * top bar + bottom tabs + "More" sheet below.
 * Both layouts share one tree in which only the chrome around `<main>` changes, so crossing
 * 1024px (a resized window, a rotated tablet) never remounts the routed page or loses its state.
 */
export function AppShell({
  isAdmin = false,
  account,
  items = navItems,
  featureVisible,
}: AppShellProps) {
  const isDesktop = useIsDesktop();
  const [moreOpen, setMoreOpen] = useState(false);
  // The More sheet belongs to the mobile layout: reaching desktop closes it for good, so it never
  // springs back open on the way back to mobile.
  if (isDesktop && moreOpen) setMoreOpen(false);
  const visible = visibleNav(items, isAdmin, featureVisible);
  const { tabs, more } = splitMobileNav(visible);
  const close = () => setMoreOpen(false);

  return (
    <div className="min-h-dvh">
      <a href="#main" className={SKIP_LINK}>
        Skip to content
      </a>
      {isDesktop ? <SideNav items={visible} account={account} /> : <TopBar />}
      <main
        id="main"
        tabIndex={-1}
        className={cx('min-w-0 focus:outline-none', isDesktop ? 'pl-64' : 'px-4 pb-24 pt-4')}
      >
        {isDesktop && <ContentHeader />}
        <div className={isDesktop ? 'mx-auto max-w-7xl p-6' : undefined}>
          <Outlet />
        </div>
      </main>
      {!isDesktop && (
        <BottomTabs tabs={tabs} more={more} moreOpen={moreOpen} onMore={() => setMoreOpen(true)} />
      )}
      <Sheet open={moreOpen} onClose={close} title="More">
        <nav aria-label="More">
          <NavList items={more} onNavigate={close} />
        </nav>
        {account !== undefined && (
          <div className="mt-4 border-t border-outline-variant pt-4">{account}</div>
        )}
      </Sheet>
    </div>
  );
}
