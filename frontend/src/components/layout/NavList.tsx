import { NavLink } from 'react-router';
import type { NavItem } from '../../app/registry';
import { useRoundTypeLink } from '../../lib/roundTypes';
import { cx } from '../ui/cx';

function NavListLink({
  item: { path, label, icon: Icon },
  onNavigate,
}: {
  item: NavItem;
  onNavigate?: () => void;
}) {
  const to = useRoundTypeLink(path);
  return (
    <NavLink
      to={to}
      end={path === '/'}
      onClick={onNavigate}
      className={({ isActive }) =>
        cx(
          'flex min-h-11 items-center gap-3 rounded-button px-4 text-sm',
          isActive ? 'bg-primary text-text' : 'text-text-muted hover:bg-surface hover:text-text',
        )
      }
    >
      <Icon aria-hidden="true" className="size-5" />
      {label}
    </NavLink>
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
