import { ApiError } from '../../../api/errors';

export function adminErrorMessage(error: Error): string {
  if (error instanceof ApiError && error.status === 403) {
    return 'Admins only — sign in with the admin password.';
  }
  return error.message;
}

/** Server-rejected admin action (Review Focus #5): the message sits next to the control that failed. */
export function AdminError({ error }: { error: Error }) {
  return (
    <p role="alert" className="text-error">
      {adminErrorMessage(error)}
    </p>
  );
}
