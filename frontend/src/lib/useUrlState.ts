import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router';

/** Converts one query-string value; parse returns null for anything invalid. */
export interface Codec<T> {
  parse: (raw: string) => T | null;
  serialize: (value: T) => string;
}

/**
 * State stored in the query string under `key`. Missing or invalid values read as `defaultValue`;
 * writing the default removes the key. Updates replace the history entry. The parsed value keeps
 * its identity while the key's raw value is unchanged; `codec` and `defaultValue` should be
 * referentially stable (module constants) so list/range values do too. One setter call per event:
 * React Router applies each setSearchParams against the current URL, so a second call in the same
 * event would overwrite the first.
 */
export function useUrlState<T>(
  key: string,
  codec: Codec<T>,
  defaultValue: T,
): [T, (next: T) => void] {
  const [params, setParams] = useSearchParams();
  const raw = params.get(key);
  const parsed = useMemo(() => (raw === null ? null : codec.parse(raw)), [raw, codec]);
  const value = parsed ?? defaultValue;
  const setValue = useCallback(
    (next: T) => {
      setParams(
        (prev) => {
          const out = new URLSearchParams(prev);
          const serialized = codec.serialize(next);
          if (serialized === codec.serialize(defaultValue)) out.delete(key);
          else out.set(key, serialized);
          return out;
        },
        { replace: true },
      );
    },
    [setParams, key, codec, defaultValue],
  );
  return [value, setValue];
}

export const stringCodec: Codec<string> = { parse: (raw) => raw, serialize: (v) => v };

export const intCodec: Codec<number> = {
  parse: (raw) => (/^-?\d+$/.test(raw) ? Number(raw) : null),
  serialize: (v) => String(v),
};

export const numberCodec: Codec<number> = {
  parse: (raw) => {
    const n = Number(raw);
    return raw.trim() !== '' && Number.isFinite(n) ? n : null;
  },
  serialize: (v) => String(v),
};

export const boolCodec: Codec<boolean> = {
  parse: (raw) => (raw === '1' ? true : raw === '0' ? false : null),
  serialize: (v) => (v ? '1' : '0'),
};

export function enumCodec<T extends string>(values: readonly T[]): Codec<T> {
  return { parse: (raw) => values.find((v) => v === raw) ?? null, serialize: (v) => v };
}

/** Comma-separated list; invalid and duplicate items are dropped. */
export function listCodec<T>(item: Codec<T>): Codec<T[]> {
  return {
    parse: (raw) => {
      const items = raw === '' ? [] : raw.split(',').map((part) => item.parse(part));
      const kept: T[] = [];
      for (const v of items) if (v !== null && !kept.includes(v)) kept.push(v);
      return kept;
    },
    serialize: (values) => values.map((v) => item.serialize(v)).join(','),
  };
}

/** `lo..hi` with finite numbers and lo <= hi. */
export const rangeCodec: Codec<[number, number]> = {
  parse: (raw) => {
    const parts = raw.split('..');
    if (parts.length !== 2) return null;
    const [lo, hi] = parts.map((part) => numberCodec.parse(part));
    return typeof lo === 'number' && typeof hi === 'number' && lo <= hi ? [lo, hi] : null;
  },
  serialize: ([lo, hi]) => `${lo}..${hi}`,
};

/** A real calendar date written as YYYY-MM-DD. */
export const isoDateCodec: Codec<string> = {
  parse: (raw) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return null;
    const d = new Date(`${raw}T00:00:00Z`);
    return !Number.isNaN(d.getTime()) && d.toISOString().startsWith(raw) ? raw : null;
  },
  serialize: (v) => v,
};

/**
 * One atomic write of several query keys: a string sets a key, `null` deletes it, and every other
 * key stays. Use it when one event changes more than one key, because two useUrlState setters
 * called in the same event overwrite each other. Replaces the history entry, like useUrlState.
 */
export function useSetUrlParams(): (updates: Readonly<Record<string, string | null>>) => void {
  const [, setParams] = useSearchParams();
  return useCallback(
    (updates) => {
      setParams(
        (prev) => {
          const out = new URLSearchParams(prev);
          for (const [key, value] of Object.entries(updates)) {
            if (value === null) out.delete(key);
            else out.set(key, value);
          }
          return out;
        },
        { replace: true },
      );
    },
    [setParams],
  );
}

/** A date that may be absent: an invalid or missing value reads as null, and null is never written. */
export const optionalIsoDateCodec: Codec<string | null> = {
  parse: (raw) => isoDateCodec.parse(raw),
  serialize: (v) => v ?? '',
};
