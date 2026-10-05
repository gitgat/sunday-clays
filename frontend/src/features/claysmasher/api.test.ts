import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { ApiError } from '../../api/errors';
import { server } from '../../test/msw/server';
import { fetchScoresExport, filenameFrom } from './api';

const URL_PATTERN = '*/api/shooters/:id/claysmasher-export';

describe('filenameFrom', () => {
  it('reads the quoted filename of a Content-Disposition attachment', () => {
    expect(filenameFrom('attachment; filename="claysmasher-doe-jane-scores.zip"', 3)).toBe(
      'claysmasher-doe-jane-scores.zip',
    );
  });

  it('falls back to a name built from the shooter id', () => {
    expect(filenameFrom(null, 3)).toBe('claysmasher-shooter-3-scores.zip');
    expect(filenameFrom('attachment', 3)).toBe('claysmasher-shooter-3-scores.zip');
  });
});

describe('fetchScoresExport', () => {
  it('returns the zip and its filename', async () => {
    let asked = '';
    server.use(
      http.get(URL_PATTERN, ({ params }) => {
        asked = String(params.id);
        return new HttpResponse(new Uint8Array([0x50, 0x4b, 3, 4]), {
          headers: {
            'Content-Type': 'application/zip',
            'Content-Disposition': 'attachment; filename="claysmasher-doe-jane-scores.zip"',
          },
        });
      }),
    );

    const { blob, filename } = await fetchScoresExport(7);

    expect(asked).toBe('7');
    expect(filename).toBe('claysmasher-doe-jane-scores.zip');
    expect([...new Uint8Array(await blob.arrayBuffer())]).toEqual([0x50, 0x4b, 3, 4]);
  });

  it('throws the server error code', async () => {
    server.use(
      http.get(URL_PATTERN, () =>
        HttpResponse.json(
          { error: { code: 'no_exportable_rounds', message: 'none' } },
          { status: 404 },
        ),
      ),
    );

    const error: unknown = await fetchScoresExport(7).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, code: 'no_exportable_rounds' });
  });
});
