import { api, unwrap } from '../../api/client';

export interface ScoresExport {
  blob: Blob;
  filename: string;
}

/** The quoted filename of a Content-Disposition attachment, or a name built from the id. */
export function filenameFrom(disposition: string | null, shooterId: number): string {
  const match = disposition === null ? null : /filename="([^"]+)"/.exec(disposition);
  return match?.[1] ?? `claysmasher-shooter-${shooterId}-scores.zip`;
}

/**
 * The shooter's scores as a zip of ClaySmasher import CSVs, one per discipline. Throws ApiError
 * (404 `no_exportable_rounds` when there is nothing to export) or the network TypeError.
 */
export async function fetchScoresExport(shooterId: number): Promise<ScoresExport> {
  const request = api.GET('/api/shooters/{id}/claysmasher-export', {
    params: { path: { id: shooterId } },
    parseAs: 'blob',
  });
  const blob = await unwrap(request);
  const { response } = await request;
  return { blob, filename: filenameFrom(response.headers.get('Content-Disposition'), shooterId) };
}
