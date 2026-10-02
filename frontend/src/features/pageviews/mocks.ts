import { http, HttpResponse } from 'msw';

/** Every page view is accepted (204). Tests that inspect beacons override this with server.use. */
export const handlers = [
  http.post('*/api/pageviews', () => new HttpResponse(null, { status: 204 })),
];
