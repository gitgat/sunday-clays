import { describe, expect, it } from 'vitest';
import { ApiError, toApiError } from './errors';

describe('toApiError', () => {
  it('unpacks the C2 error envelope', () => {
    const e = toApiError(400, {
      error: { code: 'invalid_query', message: 'Group by station needs Hit %' },
    });
    expect(e).toBeInstanceOf(ApiError);
    expect(e).toMatchObject({
      status: 400,
      code: 'invalid_query',
      message: 'Group by station needs Hit %',
    });
  });

  it.each([
    [422, { detail: [{ msg: 'x' }] }, 'http_422', 'The request was not valid.'],
    [429, 'Too Many Requests', 'http_429', 'Too many attempts. Try again in a few minutes.'],
    [502, undefined, 'http_502', 'Server error. Try again shortly.'],
    [418, null, 'http_418', 'Request failed.'],
    [409, { error: 'conflict' }, 'http_409', 'Request failed.'],
    [404, { error: { code: 7, message: null } }, 'http_404', 'Not found.'],
  ])('falls back to http_%s and a default message', (status, body, code, message) => {
    expect(toApiError(status, body)).toMatchObject({ status, code, message });
  });
});
