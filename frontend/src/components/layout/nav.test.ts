import { Building2, CalendarDays, Compass, House, Settings, Trophy, Users } from 'lucide-react';
import { describe, expect, it } from 'vitest';
import type { NavItem } from '../../app/registry';
import { splitMobileNav, visibleNav } from './nav';

const ITEMS: NavItem[] = [
  { label: 'Explorer', path: '/explorer', icon: Compass, order: 60 },
  { label: 'Home', path: '/', icon: House, order: 10, mobileTab: true },
  { label: 'Imports', path: '/admin/imports', icon: Settings, order: 900, adminOnly: true },
  { label: 'Leaderboards', path: '/leaderboards', icon: Trophy, order: 30, mobileTab: true },
  { label: 'Shooters', path: '/shooters', icon: Users, order: 40, mobileTab: true },
  { label: 'Events', path: '/events', icon: CalendarDays, order: 20, mobileTab: true },
  { label: 'Club', path: '/club', icon: Building2, order: 50 },
];

describe('visibleNav', () => {
  it('hides admin-only items from viewers and sorts by order', () => {
    expect(visibleNav(ITEMS, false).map((i) => i.label)).toEqual([
      'Home',
      'Events',
      'Leaderboards',
      'Shooters',
      'Club',
      'Explorer',
    ]);
  });

  it('shows admin-only items to admins', () => {
    expect(visibleNav(ITEMS, true).map((i) => i.label)).toContain('Imports');
  });
});

describe('splitMobileNav', () => {
  it('puts the mobile tabs in the tab bar and the rest in More', () => {
    const { tabs, more } = splitMobileNav(visibleNav(ITEMS, true));
    expect(tabs.map((i) => i.label)).toEqual(['Home', 'Events', 'Leaderboards', 'Shooters']);
    expect(more.map((i) => i.label)).toEqual(['Club', 'Explorer', 'Imports']);
  });

  it('never shows more than four tabs', () => {
    const extra = { label: 'Extra', path: '/extra', icon: Compass, order: 150, mobileTab: true };
    const { tabs, more } = splitMobileNav(visibleNav([...ITEMS, extra], false));
    expect(tabs).toHaveLength(4);
    expect(more.map((i) => i.label)).toContain('Extra');
  });
});
