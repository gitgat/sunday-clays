import type { RequestHandler } from 'msw';

/** The PWA feature calls no API of its own (it reads /api/features through lib/features). */
export const handlers: RequestHandler[] = [];
