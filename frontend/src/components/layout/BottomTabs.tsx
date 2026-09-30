import { Ellipsis } from 'lucide-react';
import { matchPath, NavLink, useLocation } from 'react-router';
import type { NavItem } from '../../app/registry';
import { useRoundTypeLink } from '../../lib/roundTypes';
import { cx } from '../ui/cx';

const TAB = 'flex min-h-14 min-w-11 flex-1 flex-col items-center justify-center gap-0.5 text-xs';

/**
 * Active tab: the 12px label stays in the text color (accent is only 3.6:1 on elevated) and the
 * accent goes on the icon's stroke, a graphic that needs 3:1.
 */
const tabTone = (active: boolean) => cx(TAB, active ? 'font-medium text-text' : 'text-text-muted');
const iconTone = (active: boolean) => cx('size-5', active && 'stroke-accent');

function TabLink({ item: { path, label, icon: Icon } }: { item: NavItem }) {
  const to = useRoundTypeLink(path);
  return (
    <NavLink to={to} end={path === '/'} className={({ isActive }) => tabTone(isActive)}>
      {({ isActive }) => (
        <>
          <Icon aria-hidden="true" className={iconTone(isActive)} />
          {label}
        </>
      )}
    </NavLink>
  );
}

/** Mobile bottom tab bar: the C10 mobile tabs, then "More" (current while a `more` page is open). */
export function BottomTabs({
  tabs,
  more,
  moreOpen,
  onMore,
}: {
  tabs: readonly NavItem[];
  more: readonly NavItem[];
  moreOpen: boolean;
  onMore: () => void;
}) {
  const { pathname } = useLocation();
  const moreActive = more.some(
    (item) => matchPath({ path: item.path, end: item.path === '/' }, pathname) !== null,
  );
  return (
    <nav
      aria-label="Tabs"
      className="fixed inset-x-0 bottom-0 z-30 flex border-t border-outline-variant bg-elevated pb-[env(safe-area-inset-bottom)]"
    >
      {tabs.map((item) => (
        <TabLink key={item.path} item={item} />
      ))}
      <button
        type="button"
        aria-haspopup="dialog"
        aria-expanded={moreOpen}
        aria-current={moreActive ? 'true' : undefined}
        onClick={onMore}
        className={tabTone(moreActive)}
      >
        <Ellipsis aria-hidden="true" className={iconTone(moreActive)} />
        More
      </button>
    </nav>
  );
}
