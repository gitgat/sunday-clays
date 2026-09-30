import { act, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../test/render';
import {
  boolCodec,
  enumCodec,
  intCodec,
  isoDateCodec,
  listCodec,
  numberCodec,
  optionalIsoDateCodec,
  rangeCodec,
  stringCodec,
  useSetUrlParams,
  useUrlState,
} from './useUrlState';

const METRICS = ['score', 'adjusted', 'rounds'] as const;
const metricCodec = enumCodec(METRICS);

function Probe({ onSet }: { onSet: (set: (v: (typeof METRICS)[number]) => void) => void }) {
  const [metric, setMetric] = useUrlState('m', metricCodec, 'score');
  onSet(setMetric);
  return <p>metric:{metric}</p>;
}

function setup(route: string) {
  let setter: (v: (typeof METRICS)[number]) => void = () => undefined;
  const view = renderWithProviders(<Probe onSet={(s) => (setter = s)} />, { route });
  return { ...view, set: (v: (typeof METRICS)[number]) => act(() => setter(v)) };
}

describe('useUrlState', () => {
  it('reads the default when the key is missing', () => {
    setup('/explorer');
    expect(screen.getByText('metric:score')).toBeInTheDocument();
  });

  it('reads a valid value and ignores an invalid one', () => {
    setup('/explorer?m=rounds');
    expect(screen.getByText('metric:rounds')).toBeInTheDocument();
    setup('/explorer?m=bogus');
    expect(screen.getByText('metric:score')).toBeInTheDocument();
  });

  it('writes to the query string, keeps other keys and replaces history', async () => {
    const { set, router } = setup('/explorer?g=year');
    await set('adjusted');
    expect(router.state.location.search).toBe('?g=year&m=adjusted');
    expect(router.state.historyAction).toBe('REPLACE');
    expect(screen.getByText('metric:adjusted')).toBeInTheDocument();
  });

  it('removes the key when set back to the default', async () => {
    const { set, router } = setup('/explorer?m=rounds&g=year');
    await set('score');
    expect(router.state.location.search).toBe('?g=year');
  });
});

describe('codecs', () => {
  const metricList = listCodec(metricCodec);
  it.each<[string, (raw: string) => unknown, string, unknown]>([
    ['string', stringCodec.parse, 'abc', 'abc'],
    ['int', intCodec.parse, '-12', -12],
    ['int rejects decimals', intCodec.parse, '1.5', null],
    ['number', numberCodec.parse, '1.5', 1.5],
    ['number rejects blank', numberCodec.parse, ' ', null],
    ['number rejects text', numberCodec.parse, 'x', null],
    ['bool true', boolCodec.parse, '1', true],
    ['bool false', boolCodec.parse, '0', false],
    ['bool rejects other', boolCodec.parse, 'yes', null],
    ['enum', metricCodec.parse, 'rounds', 'rounds'],
    ['enum rejects', metricCodec.parse, 'x', null],
    [
      'list drops invalid and duplicate items',
      metricList.parse,
      'rounds,x,rounds,score',
      ['rounds', 'score'],
    ],
    ['list empty', metricList.parse, '', []],
    ['range', rangeCodec.parse, '-5..40.5', [-5, 40.5]],
    ['range rejects reversed', rangeCodec.parse, '40..5', null],
    ['range rejects junk', rangeCodec.parse, '1..2..3', null],
    ['range rejects text', rangeCodec.parse, 'a..2', null],
    ['date', isoDateCodec.parse, '2026-09-13', '2026-09-13'],
    ['date rejects impossible day', isoDateCodec.parse, '2026-02-30', null],
    ['date rejects format', isoDateCodec.parse, '9/13/2026', null],
    ['optional date', optionalIsoDateCodec.parse, '2026-09-13', '2026-09-13'],
    ['optional date rejects impossible day', optionalIsoDateCodec.parse, '2026-02-30', null],
  ])('%s', (_name, parse, raw, expected) => {
    expect(parse(raw)).toEqual(expected);
  });

  it('serializes lists, ranges and booleans', () => {
    expect(listCodec(metricCodec).serialize(['score', 'rounds'])).toBe('score,rounds');
    expect(rangeCodec.serialize([0, 12.5])).toBe('0..12.5');
    expect(boolCodec.serialize(true)).toBe('1');
    expect(boolCodec.serialize(false)).toBe('0');
    expect(intCodec.serialize(7)).toBe('7');
  });

  it('serializes numbers, strings, enums and dates as written', () => {
    expect(numberCodec.serialize(-0.25)).toBe('-0.25');
    expect(stringCodec.serialize('a b')).toBe('a b');
    expect(metricCodec.serialize('adjusted')).toBe('adjusted');
    expect(isoDateCodec.serialize('2026-09-13')).toBe('2026-09-13');
    expect(optionalIsoDateCodec.serialize('2026-09-13')).toBe('2026-09-13');
    expect(optionalIsoDateCodec.serialize(null)).toBe('');
  });
});

describe('useSetUrlParams', () => {
  function Setter({ updates }: { updates: Record<string, string | null> }) {
    const set = useSetUrlParams();
    return (
      <button type="button" onClick={() => set(updates)}>
        go
      </button>
    );
  }

  it('sets several keys in one write, deletes null keys and keeps the rest', async () => {
    const { user, router } = renderWithProviders(
      <Setter updates={{ period: 'custom', since: '2026-01-01', gauge: null }} />,
      { route: '/x?rt=sporting&gauge=12&keep=1' },
    );
    await user.click(screen.getByRole('button', { name: 'go' }));
    const params = new URLSearchParams(router.state.location.search);
    expect(params.get('period')).toBe('custom');
    expect(params.get('since')).toBe('2026-01-01');
    expect(params.has('gauge')).toBe(false);
    expect(params.get('rt')).toBe('sporting');
    expect(params.get('keep')).toBe('1');
  });

  it('replaces the history entry instead of pushing one', async () => {
    const { user, router } = renderWithProviders(<Setter updates={{ a: '1', b: '2' }} />, {
      route: '/x',
    });
    const before = router.state.historyAction;
    await user.click(screen.getByRole('button', { name: 'go' }));
    expect(router.state.location.search).toBe('?a=1&b=2');
    expect(before).toBe('POP');
    expect(router.state.historyAction).toBe('REPLACE');
  });
});
