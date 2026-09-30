import { act, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../test/render';
import {
  useRoundTypeHref,
  useRoundTypeLink,
  useRoundTypes,
  withRoundTypes,
  type RoundTypeValue,
} from './roundTypes';
import { stringCodec, useUrlState } from './useUrlState';

function Probe({ onSet }: { onSet: (s: (v: RoundTypeValue[]) => void) => void }) {
  const [rt, setRt] = useRoundTypes();
  onSet(setRt);
  return <p>rt:{rt.join('|') || 'all'}</p>;
}

/** Re-renders when another query key changes, reporting the rt value it saw each time. */
function Watch({
  onRender,
}: {
  onRender: (rt: RoundTypeValue[], setQuery: (v: string) => void) => void;
}) {
  const [rt] = useRoundTypes();
  const [, setQuery] = useUrlState('q', stringCodec, '');
  onRender(rt, setQuery);
  return null;
}

function LinkProbe({ path }: { path: string }) {
  return <p>{JSON.stringify(useRoundTypeLink(path))}</p>;
}

function HrefProbe({ href }: { href: string }) {
  return <p>{useRoundTypeHref()(href)}</p>;
}

describe('useRoundTypes', () => {
  it('reads every round type selected as no filter', () => {
    renderWithProviders(<Probe onSet={() => undefined} />, {
      route: '/?rt=sporting,super_sporting',
    });
    expect(screen.getByText('rt:all')).toBeInTheDocument();
  });

  it('binds the rt query parameter and drops unknown values', () => {
    renderWithProviders(<Probe onSet={() => undefined} />, { route: '/?rt=sporting,bogus' });
    expect(screen.getByText('rt:sporting')).toBeInTheDocument();
  });

  it('writes rt and clears it for no filter', async () => {
    let set: (v: RoundTypeValue[]) => void = () => undefined;
    const { router } = renderWithProviders(<Probe onSet={(s) => (set = s)} />);
    expect(screen.getByText('rt:all')).toBeInTheDocument();
    await act(() => set(['super_sporting', 'sporting']));
    expect(router.state.location.search).toBe('?rt=super_sporting%2Csporting');
    await act(() => set([]));
    expect(router.state.location.search).toBe('');
  });

  it('keeps the same array while rt is unchanged', async () => {
    const seen: RoundTypeValue[][] = [];
    let setQuery: (v: string) => void = () => undefined;
    const { router } = renderWithProviders(
      <Watch
        onRender={(rt, set) => {
          seen.push(rt);
          setQuery = set;
        }}
      />,
      { route: '/?rt=sporting' },
    );
    await act(() => setQuery('x'));
    expect(router.state.location.search).toBe('?rt=sporting&q=x');
    expect(seen.length).toBeGreaterThan(1);
    expect(seen.at(-1)).toBe(seen[0]);
  });
});

describe('useRoundTypeLink', () => {
  it('links to the bare path while no round type is selected', () => {
    renderWithProviders(<LinkProbe path="/events" />);
    expect(screen.getByText('{"pathname":"/events","search":""}')).toBeInTheDocument();
  });

  it('carries the round-type filter along, encoded as the filter writes it', () => {
    renderWithProviders(<LinkProbe path="/events" />, {
      route: '/explorer?rt=sporting&m=x',
    });
    expect(screen.getByText('{"pathname":"/events","search":"?rt=sporting"}')).toBeInTheDocument();
  });

  it('drops a filter that selects every round type', () => {
    renderWithProviders(<LinkProbe path="/" />, { route: '/?rt=super_sporting,sporting' });
    expect(screen.getByText('{"pathname":"/","search":""}')).toBeInTheDocument();
  });
});

describe('withRoundTypes', () => {
  it('leaves an href alone while no round type is selected', () => {
    expect(withRoundTypes('/shooters/7?y=1#top', [])).toBe('/shooters/7?y=1#top');
  });

  it('adds rt to a bare path, after an existing query and before a hash', () => {
    expect(withRoundTypes('/shooters/7', ['sporting'])).toBe('/shooters/7?rt=sporting');
    expect(withRoundTypes('/events?c=a b', ['sporting', 'super_sporting'])).toBe(
      '/events?c=a b&rt=sporting%2Csuper_sporting',
    );
    expect(withRoundTypes('/events/2026-09-06#r3', ['super_sporting'])).toBe(
      '/events/2026-09-06?rt=super_sporting#r3',
    );
    expect(withRoundTypes('/x?#top', ['super_sporting'])).toBe('/x?rt=super_sporting#top');
  });

  it('keeps a round type the href names itself', () => {
    expect(withRoundTypes('/events?rt=super_sporting', ['sporting'])).toBe(
      '/events?rt=super_sporting',
    );
  });
});

describe('useRoundTypeHref', () => {
  it('adds the current filter, encoded as the filter writes it', () => {
    renderWithProviders(<HrefProbe href="/shooters/7?y=1" />, {
      route: '/?rt=super_sporting',
    });
    expect(screen.getByText('/shooters/7?y=1&rt=super_sporting')).toBeInTheDocument();
  });

  it('adds nothing for a filter that selects every round type', () => {
    renderWithProviders(<HrefProbe href="/shooters/7" />, {
      route: '/?rt=super_sporting,sporting',
    });
    expect(screen.getByText('/shooters/7')).toBeInTheDocument();
  });
});

describe('the time window `w` travels with the round-type filter', () => {
  it('links carry a non-default window, after rt', () => {
    renderWithProviders(<LinkProbe path="/events" />, { route: '/?w=6m&rt=sporting' });
    expect(
      screen.getByText('{"pathname":"/events","search":"?rt=sporting&w=6m"}'),
    ).toBeInTheDocument();
  });

  it('links carry a window the URL names, 8W included, and none when it names none', () => {
    const { unmount } = renderWithProviders(<LinkProbe path="/events" />, { route: '/?w=all' });
    expect(screen.getByText('{"pathname":"/events","search":"?w=all"}')).toBeInTheDocument();
    unmount();
    const explicit = renderWithProviders(<LinkProbe path="/events" />, { route: '/?w=8w' });
    expect(screen.getByText('{"pathname":"/events","search":"?w=8w"}')).toBeInTheDocument();
    explicit.unmount();
    renderWithProviders(<LinkProbe path="/events" />, { route: '/' });
    expect(screen.getByText('{"pathname":"/events","search":""}')).toBeInTheDocument();
  });

  it('withRoundTypes adds w after rt and existing query, before a hash', () => {
    expect(withRoundTypes('/shooters/7', [], '12m')).toBe('/shooters/7?w=12m');
    expect(withRoundTypes('/e?y=1#top', ['sporting'], 'ytd')).toBe('/e?y=1&rt=sporting&w=ytd#top');
    expect(withRoundTypes('/e', ['sporting'], '8w')).toBe('/e?rt=sporting&w=8w');
    expect(withRoundTypes('/e', ['sporting'], null)).toBe('/e?rt=sporting');
  });

  it('withRoundTypes keeps a key the href names itself and still adds the other', () => {
    expect(withRoundTypes('/e?w=all', ['sporting'], '6m')).toBe('/e?w=all&rt=sporting');
    expect(withRoundTypes('/e?rt=super_sporting&w=all', ['sporting'], '6m')).toBe(
      '/e?rt=super_sporting&w=all',
    );
  });

  it('useRoundTypeHref adds the current window', () => {
    renderWithProviders(<HrefProbe href="/shooters/7" />, { route: '/?w=6m' });
    expect(screen.getByText('/shooters/7?w=6m')).toBeInTheDocument();
  });
});
