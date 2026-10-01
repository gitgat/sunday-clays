import { Link, useLocation } from 'react-router';
import type { NavItem } from '../../app/registry';
import { useRoundTypeLink } from '../../lib/roundTypes';
import { cx } from '../ui/cx';
import { isNavActive } from './nav';

function NavListLink({ item, onNavigate }: { item: NavItem; onNavigate?: () => void }) {
  const { path, label, icon: Icon } = item;
  const to = useRoundTypeLink(path);
  const active = isNavActive(item, useLocation().pathname);
  return (
    <Link
      to={to}
      onClick={onNavigate}
      aria-current={active ? 'page' : undefined}
      className={cx(
        'flex min-h-11 items-center gap-3 rounded-button px-4 text-sm',
        active ? 'bg-primary text-text' : 'text-text-muted hover:bg-surface hover:text-text',
      )}
    >
      <Icon aria-hidden="true" className="size-5" />
      {label}
    </Link>
  );
}

/** Vertical list of nav links (side nav and the "More" sheet); links keep the `?rt=` filter. */
export function NavList({
  items,
  onNavigate,
}: {
  items: readonly NavItem[];
  onNavigate?: () => void;
}) {
  return (
    <ul className="flex flex-col gap-1">
      {items.map((item) => (
        <li key={item.path}>
          <NavListLink item={item} onNavigate={onNavigate} />
        </li>
      ))}
    </ul>
  );
}
