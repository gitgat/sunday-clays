import { http, HttpResponse } from 'msw';

/** Zero counts for every asked key. Tests override this with server.use. */
export const handlers = [
  http.get('*/api/bumps', ({ request }) => {
    const keys = (new URL(request.url).searchParams.get('keys') ?? '').split(',').filter(Boolean);
    return HttpResponse.json(
      Object.fromEntries(keys.map((key) => [key, { bumps: 0, bumped: false }])),
    );
  }),
];
