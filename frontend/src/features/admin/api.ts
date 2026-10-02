import { useMutation, useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';

export type JsonOf<Op> = Op extends {
  responses: { 200: { content: { 'application/json': infer R } } };
}
  ? R
  : never;

export type ImportSummary = JsonOf<paths['/api/admin/imports']['get']>[number];
/**
 * openapi-fetch's `Readable<>` maps every array type, tuples included, to `E[]`, so its response data types
 * `ScoresDiff.possible_duplicates` (`[string, string][]` here) as `string[][]`. The JSON is this shape (the server
 * model is `list[tuple[str, str]]`), so the hooks that return a preview re-type it as `ImportPreview`.
 */
export type ImportPreview = JsonOf<paths['/api/admin/imports/{id}']['get']>;
export type Finding = ImportPreview['findings'][number];
export type ScoresDiff = Extract<ImportPreview['diff'], { rows_added: number }>;
export type StationsDiff = Extract<ImportPreview['diff'], { events_replaced: string[] }>;
export type SpecialDiff = Extract<ImportPreview['diff'], { target_total: number }>;
export type Job = JsonOf<paths['/api/admin/jobs/{id}']['get']>;
export type ShooterMatch = JsonOf<paths['/api/shooters']['get']>[number];
export type ShooterOption = { shooter_id: number; display_name: string };

export const JOB_POLL_MS = 1000;
/** After this many failed lookups in total (TanStack's errorUpdateCount is cumulative), useJob stops polling. */
export const JOB_MAX_ERRORS = 5;

/** ms until the next poll, or false to stop (job settled, or JOB_MAX_ERRORS lookups failed in total). */
export function jobPollDelay(status: string | undefined, errors: number): number | false {
  if (status === 'done' || status === 'failed' || errors >= JOB_MAX_ERRORS) return false;
  return JOB_POLL_MS * 2 ** errors;
}

/**
 * Polls every JOB_POLL_MS until the job is done or failed. Lookup errors back off (2 s, 4 s, 8 s, ...) so a blip
 * recovers, and after JOB_MAX_ERRORS failed lookups in total polling stops.
 */
export function useJob(id: number) {
  return useQuery({
    queryKey: ['/api/admin/jobs/{id}', id],
    queryFn: () => unwrap(api.GET('/api/admin/jobs/{id}', { params: { path: { id } } })),
    refetchInterval: (query) =>
      jobPollDelay(
        query.state.data?.status,
        query.state.status === 'error' ? query.state.errorUpdateCount : 0,
      ),
  });
}

/** Viewer shooter search for admin pickers; waits for 2+ characters. Key shape matches features/shooters. */
export function useShooterSearch(q: string) {
  return useQuery({
    queryKey: ['/api/shooters', { q, active: false }],
    queryFn: () => unwrap(api.GET('/api/shooters', { params: { query: { q } } })),
    enabled: q.length >= 2,
  });
}

export function useCommitImport() {
  return useMutation({
    mutationFn: ({ id, confirmRemovals }: { id: number; confirmRemovals: boolean }) =>
      unwrap(
        api.POST('/api/admin/imports/{id}/commit', {
          params: { path: { id } },
          body: { confirm_removals: confirmRemovals },
        }),
      ),
  });
}

export function useImports() {
  return useQuery({
    queryKey: ['/api/admin/imports'],
    queryFn: () => unwrap(api.GET('/api/admin/imports')),
  });
}

export function useUploadImport() {
  return useMutation({
    mutationFn: async (file: File) =>
      (await unwrap(
        api.POST('/api/admin/imports', {
          // The generated type describes the binary part as a string; the serializer sends the File itself.
          body: { file: file as unknown as string },
          bodySerializer: () => {
            const form = new FormData();
            form.append('file', file);
            return form;
          },
        }),
      )) as ImportPreview,
  });
}

export function useDiscardImport() {
  return useMutation({
    mutationFn: (id: number) =>
      unwrap(api.POST('/api/admin/imports/{id}/discard', { params: { path: { id } } })),
  });
}

export function useRollbackImport() {
  return useMutation({
    mutationFn: (id: number) =>
      unwrap(api.POST('/api/admin/imports/{id}/rollback', { params: { path: { id } } })),
  });
}

/** Disabled for a non-positive or non-integer id (the page says "Import not found" without calling the API). */
export function useImport(id: number) {
  return useQuery({
    queryKey: ['/api/admin/imports/{id}', id],
    queryFn: async () =>
      (await unwrap(
        api.GET('/api/admin/imports/{id}', { params: { path: { id } } }),
      )) as ImportPreview,
    enabled: Number.isInteger(id) && id > 0,
  });
}
