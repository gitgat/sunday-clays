import { useEffect } from 'react';
import { useSearchParams } from 'react-router';

/** Query keys to set (a string) or delete (`null`). */
export type ParamUpdates = Readonly<Record<string, string | null>>;

/** What a page's URL converter says: nothing to do (null), wait for data ('wait'), or the writes. */
export type Conversion = ParamUpdates | 'wait' | null;

/**
 * Converts old query parameters into the current ones once, on load: `convert` reads the URL and
 * returns the writes (applied in one history-replacing update, so the old keys leave the URL) or
 * 'wait' when it needs data that has not loaded. Returns true until the URL is clean, so a page can
 * hold its first request back instead of asking for the wrong window. `convert` must be pure.
 */
export function useLegacyParams(convert: (params: URLSearchParams) => Conversion): boolean {
  const [params, setParams] = useSearchParams();
  const conversion = convert(params);
  const key =
    conversion === null || conversion === 'wait' ? conversion : JSON.stringify(conversion);
  useEffect(() => {
    if (conversion === null || conversion === 'wait') return;
    setParams(
      (prev) => {
        const out = new URLSearchParams(prev);
        for (const [name, value] of Object.entries(conversion)) {
          if (value === null) out.delete(name);
          else out.set(name, value);
        }
        return out;
      },
      { replace: true },
    );
    // `key` stands for `conversion`: a new object with the same writes must not run this twice.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, setParams]);
  return conversion !== null;
}
