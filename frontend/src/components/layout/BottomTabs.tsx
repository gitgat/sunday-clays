import { Ellipsis } from 'lucide-react';
import { Link, useLocation } from 'react-router';
import type { NavItem } from '../../app/registry';
import { useRoundTypeLink } from '../../lib/roundTypes';
import { cx } from '../ui/cx';
import { isNavActive } from './nav';

const TAB = 'flex min-h-14 min-w-11 flex-1 flex-col items-center justify-center gap-0.5 text-xs';

/**
 * Active tab: the 12px label stays in the text color (accent is only 3.6:1 on elevated) and the
 * accent goes on the icon's stroke, a graphic that needs 3:1.
 */
const tabTone = (active: boolean) => cx(TAB, active ? 'font-medium text-text' : 'text-text-muted');
const iconTone = (active: boolean) => cx('size-5', active && 'stroke-accent');

function TabLink({ item }: { item: NavItem }) {
  const { path, label, icon: Icon } = item;
  const to = useRoundTypeLink(path);
  const active = isNavActive(item, useLocation().pathname);
  return (
    <Link to={to} aria-current={active ? 'page' : undefined} className={tabTone(active)}>
      <Icon aria-hidden="true" className={iconTone(active)} />
      {label}
    </Link>
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
  const moreActive = more.some((item) => isNavActive(item, pathname));
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
