import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { server } from '../../test/msw/server';
import { downloadRosterCsv, fetchEmails } from './api';

describe('admin club-events downloads', () => {
  it('names the CSV after the event and its date', async () => {
    const created: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      created.push(this.download);
    });
    await downloadRosterCsv({ id: 1, local_date: '2026-10-17' });
    expect(created).toEqual(['club-event-1-2026-10-17-roster.csv']);
    vi.restoreAllMocks();
  });

  it('throws the server message when the CSV is refused', async () => {
    server.use(
      http.get('*/api/admin/club-events/1/roster.csv', () =>
        HttpResponse.json(
          { error: { code: 'not_found', message: 'No such club event.' } },
          { status: 404 },
        ),
      ),
    );
    await expect(downloadRosterCsv({ id: 1, local_date: '2026-10-17' })).rejects.toThrow(
      'No such club event.',
    );
  });

  it('throws a plain error when the refusal has no body', async () => {
    server.use(
      http.get(
        '*/api/admin/club-events/1/roster.csv',
        () => new HttpResponse('nope', { status: 500 }),
      ),
    );
    await expect(downloadRosterCsv({ id: 1, local_date: '2026-10-17' })).rejects.toBeInstanceOf(
      Error,
    );
  });

  it('asks for the emails by status', async () => {
    server.use(
      http.get('*/api/admin/club-events/1/emails', ({ request }) =>
        HttpResponse.json({ emails: [new URL(request.url).searchParams.get('status') ?? ''] }),
      ),
    );
    expect(await fetchEmails(1, 'waitlist')).toEqual(['waitlist']);
  });
});
