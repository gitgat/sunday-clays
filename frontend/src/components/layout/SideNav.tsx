import type { ReactNode } from 'react';
import { Link } from 'react-router';
import type { NavItem } from '../../app/registry';
import { useRoundTypeLink } from '../../lib/roundTypes';
import { NavList } from './NavList';

/** Desktop (≥1024px) fixed left navigation: the app name and the pages only (filters live in ContentHeader). */
export function SideNav({ items, account }: { items: readonly NavItem[]; account?: ReactNode }) {
  const home = useRoundTypeLink('/');
  return (
    <aside className="fixed inset-y-0 left-0 flex w-64 flex-col gap-4 border-r border-outline-variant bg-elevated p-4">
      <Link
        to={home}
        className="inline-flex min-h-11 items-center px-2 text-lg font-bold text-text"
      >
        Sunday Clays
      </Link>
      <nav aria-label="Main" className="min-h-0 flex-1 overflow-y-auto">
        <NavList items={items} />
      </nav>
      {account !== undefined && (
        <div className="border-t border-outline-variant pt-3">{account}</div>
      )}
    </aside>
  );
}
