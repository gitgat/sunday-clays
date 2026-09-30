/** An API failure with the C2 error envelope {"error": {"code", "message"}} unpacked. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

const DEFAULT_MESSAGES: Record<number, string> = {
  401: 'Please log in again.',
  403: 'You do not have access to this.',
  404: 'Not found.',
  413: 'That file is too large.',
  422: 'The request was not valid.',
  429: 'Too many attempts. Try again in a few minutes.',
};

function defaultMessage(status: number): string {
  return (
    DEFAULT_MESSAGES[status] ??
    (status >= 500 ? 'Server error. Try again shortly.' : 'Request failed.')
  );
}

/** Builds an ApiError from a status and a parsed response body (JSON object, text or undefined). */
export function toApiError(status: number, body: unknown): ApiError {
  const envelope =
    typeof body === 'object' && body !== null && 'error' in body
      ? (body as { error: unknown }).error
      : null;
  const fields =
    typeof envelope === 'object' && envelope !== null ? (envelope as Record<string, unknown>) : {};
  const code = typeof fields.code === 'string' ? fields.code : `http_${status}`;
  const message = typeof fields.message === 'string' ? fields.message : defaultMessage(status);
  return new ApiError(status, code, message);
}
