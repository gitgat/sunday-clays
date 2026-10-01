import { Newspaper } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { NavItem } from '../../app/registry';
import { ROUND_TYPE_ONLY } from '../../lib/pageFilters';

const page = async () => ({ Component: (await import('./pages/SheetPage')).SheetPage });

/** The Sunday Sheet (Plan 14): the latest issue at `/`, any held Sunday's at `/sheet/:date`. */
export const routes: RouteObject[] = [
  { index: true, handle: { filters: ROUND_TYPE_ONLY }, lazy: page },
  { path: '/sheet/:date', handle: { filters: ROUND_TYPE_ONLY }, lazy: page },
];

export const nav: NavItem[] = [
  { label: 'Sheet', path: '/', icon: Newspaper, order: 10, mobileTab: true },
];
