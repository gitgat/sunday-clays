import { screen } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import * as download from '../../../lib/download';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { ExportScores } from './ExportScores';

const URL_PATTERN = '*/api/shooters/:id/claysmasher-export';
const ZIP = 'claysmasher-doe-jane-scores.zip';

function zipResponse() {
  return new HttpResponse(new Uint8Array([0x50, 0x4b, 3, 4]), {
    headers: {
      'Content-Type': 'application/zip',
      'Content-Disposition': `attachment; filename="${ZIP}"`,
    },
  });
}

function errorResponse(code: string, status: number) {
  return HttpResponse.json({ error: { code, message: 'x' } }, { status });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('ExportScores', () => {
  it('shows a live button with helper text that names the ClaySmasher import', () => {
    renderWithProviders(<ExportScores shooterId={3} />);

    expect(screen.getByRole('button', { name: 'Export my scores' })).toBeEnabled();
    expect(
      screen.getByText(/import into the ClaySmasher app: Settings › Import & export scores/),
    ).toBeInTheDocument();
  });

  it('downloads the zip under the server filename', async () => {
    let asked = '';
    server.use(
      http.get(URL_PATTERN, ({ params }) => {
        asked = String(params.id);
        return zipResponse();
      }),
    );
    const save = vi.spyOn(download, 'downloadBlob').mockImplementation(() => undefined);
    const { user } = renderWithProviders(<ExportScores shooterId={3} />);

    await user.click(screen.getByRole('button', { name: 'Export my scores' }));

    await vi.waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(asked).toBe('3');
    const [blob, filename] = save.mock.calls[0] ?? [];
    expect(filename).toBe(ZIP);
    expect(blob).toMatchObject({ size: 4, type: 'application/zip' });
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('is busy while the export is prepared and ignores a second click', async () => {
    let calls = 0;
    server.use(
      http.get(URL_PATTERN, async () => {
        calls += 1;
        await delay(50);
        return zipResponse();
      }),
    );
    const save = vi.spyOn(download, 'downloadBlob').mockImplementation(() => undefined);
    const { user } = renderWithProviders(<ExportScores shooterId={3} />);
    const button = screen.getByRole('button', { name: /Export my scores|Preparing/ });

    await user.click(button);

    expect(button).toHaveAttribute('aria-busy', 'true');
    expect(button).toHaveTextContent('Preparing your scores…');
    await user.click(button);
    await vi.waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(calls).toBe(1);
    expect(button).not.toHaveAttribute('aria-busy');
    expect(button).toHaveTextContent('Export my scores');
  });

  it('says so when the shooter has no Sunday rounds to export', async () => {
    server.use(http.get(URL_PATTERN, () => errorResponse('no_exportable_rounds', 404)));
    const save = vi.spyOn(download, 'downloadBlob');
    const { user } = renderWithProviders(<ExportScores shooterId={3} />);

    await user.click(screen.getByRole('button', { name: 'Export my scores' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'There are no Sunday rounds to export yet.',
    );
    expect(save).not.toHaveBeenCalled();
  });

  it('shows a retryable error when the export fails, and clears it on success', async () => {
    server.use(http.get(URL_PATTERN, () => errorResponse('internal', 500)));
    vi.spyOn(download, 'downloadBlob').mockImplementation(() => undefined);
    const { user } = renderWithProviders(<ExportScores shooterId={3} />);
    const button = screen.getByRole('button', { name: 'Export my scores' });

    await user.click(button);
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not export your scores. Try again.',
    );

    server.use(http.get(URL_PATTERN, () => zipResponse()));
    await user.click(button);
    await vi.waitFor(() => expect(screen.queryByRole('alert')).toBeNull());
  });

  it('reports a network failure the same way', async () => {
    server.use(http.get(URL_PATTERN, () => HttpResponse.error()));
    const { user } = renderWithProviders(<ExportScores shooterId={3} />);

    await user.click(screen.getByRole('button', { name: 'Export my scores' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not export your scores. Try again.',
    );
  });
});
