import { act, screen, within } from '@testing-library/react';
import { CalendarDays, Compass, House, Settings, Trophy, Users } from 'lucide-react';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { NavItem } from '../../app/registry';
import { BOTH_FILTERS, NO_FILTERS, ROUND_TYPE_ONLY } from '../../lib/pageFilters';
import { FEATURES_QUERY_KEY } from '../../lib/features';
import { createTestQueryClient, renderRoutes, type RenderOptions } from '../../test/render';
import { stubViewport } from '../../test/viewport';
import { AppShell, type AppShellProps } from './AppShell';

const ITEMS: NavItem[] = [
  { label: 'Home', path: '/', icon: House, order: 10, mobileTab: true },
  { label: 'Events', path: '/events', icon: CalendarDays, order: 20, mobileTab: true },
  { label: 'Leaderboards', path: '/leaderboards', icon: Trophy, order: 30, mobileTab: true },
  { label: 'Shooters', path: '/shooters', icon: Users, order: 40, mobileTab: true },
  { label: 'Explorer', path: '/explorer', icon: Compass, order: 60 },
  { label: 'Imports', path: '/admin/imports', icon: Settings, order: 900, adminOnly: true },
];

function renderShell(
  route: string,
  props: AppShellProps & Pick<RenderOptions, 'queryClient' | 'role'> = {},
) {
  const { queryClient, role, ...shellProps } = props;
  return renderRoutes(
    [
      {
        path: '/',
        element: <AppShell items={ITEMS} {...shellProps} />,
        children: [
          { index: true, element: <p>home page</p>, handle: { filters: BOTH_FILTERS } },
          { path: 'explorer', element: <p>explorer page</p>, handle: { filters: BOTH_FILTERS } },
          { path: 'events', element: <p>events page</p>, handle: { filters: BOTH_FILTERS } },
          {
            path: 'leaderboards',
            element: <p>board page</p>,
            handle: { filters: ROUND_TYPE_ONLY },
          },
          { path: 'trophies', element: <p>trophies page</p>, handle: { filters: NO_FILTERS } },
          { path: 'undeclared', element: <p>undeclared page</p> },
        ],
      },
    ],
    { route, queryClient, role },
  );
}

/**
 * A matchMedia stub whose width can cross 1024px mid-test: `resize` flips the answer and notifies
 * subscribers the way a real window resize (or a rotated tablet) does.
 */
function resizableViewport(initial: 'desktop' | 'mobile') {
  let kind = initial;
  const listeners = new Set<() => void>();
  vi.spyOn(window, 'matchMedia').mockImplementation(
    (query: string) =>
      ({
        get matches() {
          return query === '(min-width: 1024px)' && kind === 'desktop';
        },
        media: query,
        onchange: null,
        addEventListener: (_type: string, listener: () => void) => {
          listeners.add(listener);
        },
        removeEventListener: (_type: string, listener: () => void) => {
          listeners.delete(listener);
        },
        addListener: () => undefined,
        removeListener: () => undefined,
        dispatchEvent: () => false,
      }) as unknown as MediaQueryList,
  );
  return function resize(next: 'desktop' | 'mobile') {
    act(() => {
      kind = next;
      for (const listener of listeners) listener();
    });
  };
}

function Counter() {
  const [count, setCount] = useState(0);
  return (
    <button type="button" onClick={() => setCount((c) => c + 1)}>
      count {count}
    </button>
  );
}

/** C10: every shell control is at least 44px tall (min-h-11 / size-11, or the 56px tabs). */
const TAP_TARGET = /(?:^|\s)(?:min-h-11|min-h-14|size-11)(?:\s|$)/;

function expectTapTargets() {
  const controls = document.body.querySelectorAll<HTMLElement>('a[href], button');
  expect(controls.length).toBeGreaterThan(5);
  for (const el of controls) {
    // The skip link is visually hidden until keyboard focus; it is not a pointer target.
    if (el.classList.contains('sr-only')) continue;
    const name = el.getAttribute('aria-label') ?? el.textContent;
    expect(el.className, `${el.tagName} ${name}`).toMatch(TAP_TARGET);
  }
  for (const box of document.body.querySelectorAll('input[type="checkbox"]')) {
    expect(box.closest('label')?.className, 'checkbox label').toMatch(TAP_TARGET);
  }
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('AppShell on desktop', () => {
  it('renders the side nav with every visible item and the page in main', () => {
    stubViewport('desktop');
    renderShell('/explorer', { account: <button type="button">Log out</button> });
    const nav = screen.getByRole('navigation', { name: 'Main' });
    expect(
      within(nav)
        .getAllByRole('link')
        .map((a) => a.textContent),
    ).toEqual(['Home', 'Events', 'Leaderboards', 'Shooters', 'Explorer']);
    expect(within(nav).getByRole('link', { name: 'Explorer' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(screen.getByRole('main')).toHaveTextContent('explorer page');
    expect(screen.getByRole('main')).toHaveAttribute('tabindex', '-1');
    expect(screen.getByRole('button', { name: 'Log out' })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Tabs' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Round type' })).toBeInTheDocument();
  });

  it('shows admin-only items only to admins', () => {
    stubViewport('desktop');
    renderShell('/', { isAdmin: true });
    expect(screen.getByRole('link', { name: 'Imports' })).toBeInTheDocument();
  });
});

describe('AppShell filter placement', () => {
  it('keeps the filters out of the desktop side nav and puts them in the content header', () => {
    stubViewport('desktop');
    renderShell('/', { account: <button type="button">Log out</button> });
    const side = screen.getByRole('complementary');
    expect(within(side).queryByRole('button', { name: 'Round type' })).toBeNull();
    expect(within(side).queryByRole('group', { name: 'Time window' })).toBeNull();
    expect(within(side).getByRole('link', { name: 'Sunday Clays' })).toBeInTheDocument();
    const bar = screen.getByRole('group', { name: 'Page filters' });
    expect(within(bar).getByRole('button', { name: 'Round type' })).toBeInTheDocument();
    expect(within(bar).getByRole('group', { name: 'Time window' })).toBeInTheDocument();
    // Inside <main>, above the routed page, and sticky so the filters stay reachable.
    const main = screen.getByRole('main');
    expect(main).toContainElement(bar);
    expect(bar).toHaveClass('sticky', 'top-0');
    expect(bar.compareDocumentPosition(screen.getByText('home page'))).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  });

  it('keeps the phone filters in the top bar and renders no content header', () => {
    stubViewport('mobile');
    renderShell('/');
    expect(screen.queryByRole('group', { name: 'Page filters' })).toBeNull();
    const top = screen.getByRole('banner');
    expect(within(top).getByRole('button', { name: 'Round type' })).toBeInTheDocument();
    expect(within(top).getByRole('combobox', { name: 'Time window' })).toBeInTheDocument();
    expect(screen.getByRole('main')).not.toContainElement(
      screen.queryByRole('button', { name: 'Round type' }),
    );
  });

  it('shows the Filtered chip in the content header on desktop', () => {
    stubViewport('desktop');
    renderShell('/?rt=sporting');
    const bar = screen.getByRole('group', { name: 'Page filters' });
    expect(within(bar).getByText('Filtered: Sporting')).toBeInTheDocument();
  });
});

describe('AppShell shows only the filters a page honours', () => {
  it.each([
    ['desktop', '/', ['Round type', 'Time window']],
    ['desktop', '/leaderboards', ['Round type']],
    ['desktop', '/trophies', []],
    ['desktop', '/undeclared', []],
    ['mobile', '/', ['Round type', 'Time window']],
    ['mobile', '/leaderboards', ['Round type']],
    ['mobile', '/trophies', []],
    ['mobile', '/undeclared', []],
  ] as const)('%s at %s shows exactly %j', (viewport, route, shown) => {
    stubViewport(viewport);
    renderShell(route);
    const scope =
      viewport === 'desktop'
        ? screen.queryByRole('group', { name: 'Page filters' })
        : screen.getByRole('banner');
    const has = (name: string) =>
      scope !== null &&
      (within(scope).queryByRole('button', { name }) ??
        within(scope).queryByRole('group', { name }) ??
        within(scope).queryByRole('combobox', { name })) !== null;
    expect(has('Round type')).toBe(shown.includes('Round type' as never));
    expect(has('Time window')).toBe(shown.includes('Time window' as never));
    if (viewport === 'desktop' && shown.length === 0) expect(scope).toBeNull();
  });

  it('keeps the phone brand link on a page with no filters, and renders no empty desktop bar', () => {
    stubViewport('mobile');
    const phone = renderShell('/trophies');
    expect(
      within(screen.getByRole('banner')).getByRole('link', { name: 'Sunday Clays' }),
    ).toBeInTheDocument();
    phone.unmount();
    vi.restoreAllMocks();
    stubViewport('desktop');
    renderShell('/trophies');
    expect(screen.queryByRole('group', { name: 'Page filters' })).toBeNull();
  });

  it('keeps the hidden filters in the URL, so coming back to a page that honours them restores them', async () => {
    stubViewport('desktop');
    const { router, user } = renderShell('/leaderboards?rt=sporting&w=6m');
    expect(screen.queryByRole('group', { name: 'Time window' })).toBeNull();
    expect(router.state.location.search).toBe('?rt=sporting&w=6m');
    await user.click(screen.getByRole('link', { name: 'Home' }));
    expect(router.state.location.search).toBe('?rt=sporting&w=6m');
    expect(screen.getByRole('button', { name: '6M' })).toHaveAttribute('aria-pressed', 'true');
  });
});

describe('AppShell on mobile', () => {
  it('renders exactly the four mobile tabs plus More, and no side nav', () => {
    stubViewport('mobile');
    renderShell('/');
    const tabs = screen.getByRole('navigation', { name: 'Tabs' });
    expect(
      within(tabs)
        .getAllByRole('link')
        .map((a) => a.textContent),
    ).toEqual(['Home', 'Events', 'Leaderboards', 'Shooters']);
    expect(within(tabs).getByRole('button', { name: 'More' })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
    expect(screen.queryByRole('navigation', { name: 'Main' })).toBeNull();
    expect(screen.getByRole('main')).toHaveTextContent('home page');
    expect(screen.getByRole('main')).toHaveAttribute('tabindex', '-1');
  });

  it('shows the active tab label in the text color and only its icon in accent', () => {
    stubViewport('mobile');
    renderShell('/events');
    const tab = within(screen.getByRole('navigation', { name: 'Tabs' })).getByRole('link', {
      name: 'Events',
    });
    expect(tab).toHaveAttribute('aria-current', 'page');
    expect(tab).toHaveClass('text-text');
    expect(tab).not.toHaveClass('text-accent');
    expect(tab.querySelector('svg')).toHaveClass('stroke-accent');
    expect(screen.getByRole('button', { name: 'More' })).not.toHaveAttribute('aria-current');
  });

  it('marks More as current while a page that lives in More is open', () => {
    stubViewport('mobile');
    renderShell('/explorer');
    const tabs = screen.getByRole('navigation', { name: 'Tabs' });
    const more = within(tabs).getByRole('button', { name: 'More' });
    expect(more).toHaveAttribute('aria-current', 'true');
    expect(more).toHaveClass('text-text');
    expect(more.querySelector('svg')).toHaveClass('stroke-accent');
    for (const link of within(tabs).getAllByRole('link')) {
      expect(link).not.toHaveAttribute('aria-current');
    }
  });

  it.each(['desktop', 'mobile'] as const)(
    'offers the time window filter in the %s layout, and its choice reaches the nav links',
    async (viewport) => {
      stubViewport(viewport);
      const { user, router } = renderShell('/');
      if (viewport === 'desktop') {
        await user.click(screen.getByRole('button', { name: '12M' }));
      } else {
        await user.selectOptions(screen.getByRole('combobox', { name: 'Time window' }), '12m');
      }
      expect(router.state.location.search).toBe('?w=12m');
      const link = screen.getAllByRole('link', { name: 'Sunday Clays' })[0];
      expect(link).toHaveAttribute('href', '/?w=12m');
    },
  );

  it('opens the top-bar round-type panel leftwards so it stays on a phone screen', async () => {
    stubViewport('mobile');
    const { user } = renderShell('/');
    await user.click(screen.getByRole('button', { name: 'Round type' }));
    expect(screen.getByRole('group', { name: 'Round types' })).toHaveClass('right-0');
  });

  it('opens the More sheet with the remaining items and account, and closes it on navigation', async () => {
    stubViewport('mobile');
    const { user, router } = renderShell('/', { account: <button type="button">Log out</button> });
    await user.click(screen.getByRole('button', { name: 'More' }));
    const sheet = screen.getByRole('dialog', { name: 'More' });
    expect(
      within(sheet)
        .getAllByRole('link')
        .map((a) => a.textContent),
    ).toEqual(['Explorer']);
    expect(within(sheet).getByRole('button', { name: 'Log out' })).toBeInTheDocument();
    await user.click(within(sheet).getByRole('link', { name: 'Explorer' }));
    expect(router.state.location.pathname).toBe('/explorer');
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getByRole('main')).toHaveTextContent('explorer page');
  });

  it('shows admin-only items in More for admins', async () => {
    stubViewport('mobile');
    const { user } = renderShell('/', { isAdmin: true });
    await user.click(screen.getByRole('button', { name: 'More' }));
    expect(
      within(screen.getByRole('dialog', { name: 'More' })).getByRole('link', { name: 'Imports' }),
    ).toBeInTheDocument();
  });
});

describe('AppShell tap targets', () => {
  it('gives every desktop control a 44px tap target', async () => {
    stubViewport('desktop');
    const { user } = renderShell('/?rt=sporting');
    await user.click(screen.getByRole('button', { name: 'Round type' }));
    expectTapTargets();
  });

  it('gives every mobile control a 44px tap target', async () => {
    stubViewport('mobile');
    const { user } = renderShell('/?rt=sporting');
    await user.click(screen.getByRole('button', { name: 'Round type' }));
    expectTapTargets();
    await user.click(screen.getByRole('button', { name: 'More' }));
    expectTapTargets();
  });
});

describe('AppShell across the 1024px breakpoint', () => {
  it('keeps the routed page mounted, with its state, when the layout switches', async () => {
    const resize = resizableViewport('desktop');
    const { user } = renderRoutes([
      {
        path: '/',
        element: <AppShell items={ITEMS} />,
        children: [{ index: true, element: <Counter /> }],
      },
    ]);
    await user.click(screen.getByRole('button', { name: 'count 0' }));
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument();
    resize('mobile');
    expect(screen.getByRole('navigation', { name: 'Tabs' })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Main' })).toBeNull();
    expect(screen.getByRole('button', { name: 'count 1' })).toBeInTheDocument();
    resize('desktop');
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'count 1' })).toBeInTheDocument();
  });

  it('does not reopen the More sheet after a round trip through the desktop layout', async () => {
    const resize = resizableViewport('mobile');
    const { user } = renderShell('/');
    await user.click(screen.getByRole('button', { name: 'More' }));
    expect(screen.getByRole('dialog', { name: 'More' })).toBeInTheDocument();
    resize('desktop');
    expect(screen.queryByRole('dialog')).toBeNull();
    resize('mobile');
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getByRole('button', { name: 'More' })).toHaveAttribute('aria-expanded', 'false');
  });
});

describe('AppShell keeps the global round-type filter while navigating', () => {
  it('keeps ?rt= through the side nav and the brand link', async () => {
    stubViewport('desktop');
    const { user, router } = renderShell('/?rt=sporting');
    const nav = screen.getByRole('navigation', { name: 'Main' });
    await user.click(within(nav).getByRole('link', { name: 'Explorer' }));
    expect(router.state.location).toMatchObject({ pathname: '/explorer', search: '?rt=sporting' });
    expect(screen.getByText('Filtered: Sporting')).toBeInTheDocument();
    await user.click(screen.getByRole('link', { name: 'Sunday Clays' }));
    expect(router.state.location).toMatchObject({ pathname: '/', search: '?rt=sporting' });
  });

  it('keeps ?rt= through a bottom tab, a More item and the brand link', async () => {
    stubViewport('mobile');
    const { user, router } = renderShell('/?rt=sporting');
    const tabs = screen.getByRole('navigation', { name: 'Tabs' });
    await user.click(within(tabs).getByRole('link', { name: 'Events' }));
    expect(router.state.location).toMatchObject({ pathname: '/events', search: '?rt=sporting' });
    await user.click(screen.getByRole('button', { name: 'More' }));
    const sheet = screen.getByRole('dialog', { name: 'More' });
    await user.click(within(sheet).getByRole('link', { name: 'Explorer' }));
    expect(router.state.location).toMatchObject({ pathname: '/explorer', search: '?rt=sporting' });
    expect(screen.getByText('Filtered: Sporting')).toBeInTheDocument();
    await user.click(screen.getByRole('link', { name: 'Sunday Clays' }));
    expect(router.state.location).toMatchObject({ pathname: '/', search: '?rt=sporting' });
  });
});

describe('AppShell launch switches', () => {
  const GATED: NavItem[] = [
    ...ITEMS,
    { label: 'Glossary', path: '/glossary', icon: Compass, order: 135, feature: 'tour_glossary' },
  ];

  it('lists a gated nav item only when featureVisible says so', () => {
    stubViewport('desktop');
    const { unmount } = renderShell('/', { items: GATED });
    expect(screen.queryByRole('link', { name: 'Glossary' })).not.toBeInTheDocument();
    unmount();
    renderShell('/', { items: GATED, featureVisible: () => true });
    expect(screen.getByRole('link', { name: 'Glossary' })).toBeInTheDocument();
  });
});

describe('AppShell tour targets', () => {
  it('puts a nav item tourId on its link as data-tour', () => {
    stubViewport('desktop');
    renderShell('/', {
      items: [
        ...ITEMS,
        { label: 'Trophies', path: '/trophies', icon: Trophy, order: 70, tourId: 'trophies' },
      ],
    });
    expect(screen.getByRole('link', { name: 'Trophies' })).toHaveAttribute('data-tour', 'trophies');
    expect(screen.getByRole('link', { name: 'Explorer' })).not.toHaveAttribute('data-tour');
  });
});

describe('AppShell features-settled marker', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('marks its root once the features query has data', async () => {
    stubViewport('desktop');
    const queryClient = createTestQueryClient();
    queryClient.setQueryData(FEATURES_QUERY_KEY, { events: false });
    const { container } = renderShell('/', { queryClient });
    await screen.findByText('home page');
    expect(container.querySelector('[data-features-settled="true"]')).not.toBeNull();
  });

  it('leaves the marker off while the switches are unknown', async () => {
    stubViewport('desktop');
    const { container } = renderShell('/', { role: null });
    await screen.findByText('home page');
    expect(container.querySelector('[data-features-settled]')).toBeNull();
  });
});
