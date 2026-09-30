import { http, HttpResponse } from 'msw';
import type { QueryResult, QuerySpec } from '../../components/charts/explore';

/**
 * Deterministic fake result shaped like the real one: a column per group-by dim (shooter also
 * gets shooter_id), then value and n. Two rows: first dim 'A' and 'B'; any second dim 'X'.
 */
export function fakeExploreResult(spec: QuerySpec): QueryResult {
  const [first, second] = spec.group_by;
  const columns: QueryResult['columns'] = [];
  for (const dim of spec.group_by) {
    if (dim === 'shooter') columns.push({ key: 'shooter_id', label: 'Shooter ID', type: 'int' });
    columns.push({ key: dim, label: dim, type: 'string' });
  }
  columns.push(
    { key: 'value', label: 'Value', type: 'number' },
    { key: 'n', label: 'n', type: 'int' },
  );
  const row = (dim: string, key: string, id: number, value: number, n: number) => ({
    [dim]: key,
    ...(first === 'shooter' || second === 'shooter' ? { shooter_id: id } : {}),
    ...(second === undefined ? {} : { [second]: 'X' }),
    value,
    n,
  });
  const rows =
    first === undefined
      ? [{ value: 35, n: 10 }]
      : [row(first, 'A', 3, 36, 6), row(first, 'B', 4, 34, 4)];
  return { columns, rows, n_rounds: 10, truncated: false };
}

export const handlers = [
  http.post('/api/explore', async ({ request }) =>
    HttpResponse.json(fakeExploreResult((await request.json()) as QuerySpec)),
  ),
];
