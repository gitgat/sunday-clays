import { afterEach, describe, expect, it, vi } from 'vitest';
import { downloadCsv, toCsv } from './csv';

const COLUMNS = [
  { key: 'shooter', label: 'Shooter' },
  { key: 'value', label: 'Avg score' },
];

afterEach(() => {
  vi.restoreAllMocks();
});

describe('toCsv', () => {
  it('writes a header of labels and one CRLF line per row', () => {
    expect(
      toCsv(COLUMNS, [
        { shooter: 'Able, Ann', value: 35.5 },
        { shooter: 'Baker', value: null },
      ]),
    ).toBe('Shooter,Avg score\r\n"Able, Ann",35.5\r\nBaker,\r\n');
  });

  it('quotes embedded quotes and newlines', () => {
    expect(toCsv([{ key: 'n', label: 'Name' }], [{ n: 'Barrett "Raymond\'s Dad"\nX' }])).toBe(
      'Name\r\n"Barrett ""Raymond\'s Dad""\nX"\r\n',
    );
  });

  it('neutralises text that a spreadsheet would run as a formula, but not numbers', () => {
    const csv = toCsv(
      [
        { key: 'n', label: 'Name' },
        { key: 'v', label: 'Delta' },
      ],
      [
        { n: '=HYPERLINK("x")', v: -3 },
        { n: '@SUM(A1)', v: Number.NaN },
        { n: '+1', v: undefined },
      ],
    );
    expect(csv).toBe('Name,Delta\r\n"\'=HYPERLINK(""x"")",-3\r\n\'@SUM(A1),\r\n\'+1,\r\n');
  });
});

describe('downloadCsv', () => {
  it('downloads a UTF-8 CSV with a BOM under the given name', async () => {
    const clicked: { download: string; href: string }[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicked.push({ download: this.download, href: this.href });
    });
    const createUrl = vi.spyOn(URL, 'createObjectURL');
    downloadCsv('scores-by-year', COLUMNS, [{ shooter: 'Slocum', value: 40 }]);
    expect(clicked).toEqual([
      {
        download: 'scores-by-year.csv',
        href: expect.stringMatching(/^blob:/) as unknown as string,
      },
    ]);
    const blob = createUrl.mock.calls[0]?.[0] as Blob;
    expect(blob.type).toBe('text/csv;charset=utf-8');
    const bytes = new Uint8Array(await blob.arrayBuffer());
    expect([...bytes.slice(0, 3)]).toEqual([0xef, 0xbb, 0xbf]);
    expect(new TextDecoder().decode(bytes.slice(3))).toBe('Shooter,Avg score\r\nSlocum,40\r\n');
    expect(document.querySelector('a[download]')).toBeNull();
  });

  it('keeps an existing .csv extension', () => {
    const names: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      names.push(this.download);
    });
    downloadCsv('rounds.csv', COLUMNS, []);
    expect(names).toEqual(['rounds.csv']);
  });
});
