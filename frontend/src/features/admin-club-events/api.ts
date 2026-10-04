import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import { toApiError } from '../../api/errors';
import type { components } from '../../api/schema';
import { downloadBlob } from '../../lib/download';

export type AdminEvent = components['schemas']['ClubEventAdminOut'];
export type AdminRosterRow = components['schemas']['ClubAdminRosterRowOut'];
export type EventBody = components['schemas']['ClubEventIn'];
export type Contact = components['schemas']['ShooterContactOut'];
export type EmailsStatus = 'going' | 'waitlist' | 'active';

export const ADMIN_EVENTS_KEY = ['/api/admin/club-events'] as const;
export const rosterKey = (id: number) => ['/api/admin/club-events', id, 'roster'] as const;
export const CONTACTS_KEY = ['/api/admin/shooter-contacts'] as const;

export function useAdminClubEvents() {
  return useQuery({
    queryKey: ADMIN_EVENTS_KEY,
    queryFn: () => unwrap(api.GET('/api/admin/club-events')),
  });
}

/** An audited read (§5.5): never refetched on focus, so switching tabs writes no audit row. */
export function useAdminRoster(id: number) {
  return useQuery({
    queryKey: rosterKey(id),
    queryFn: () =>
      unwrap(
        api.GET('/api/admin/club-events/{event_id}/roster', { params: { path: { event_id: id } } }),
      ),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}

/** An audited read, like the roster. */
export function useContacts() {
  return useQuery({
    queryKey: CONTACTS_KEY,
    queryFn: () => unwrap(api.GET('/api/admin/shooter-contacts')),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}

function useRefresh() {
  const qc = useQueryClient();
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ADMIN_EVENTS_KEY }),
      qc.invalidateQueries({ queryKey: CONTACTS_KEY }),
      qc.invalidateQueries({ queryKey: ['/api/club-events'] }),
    ]);
}

export function useCreateEvent() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: EventBody) => unwrap(api.POST('/api/admin/club-events', { body })),
    onSuccess: refresh,
  });
}

export function useUpdateEvent(id: number) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: EventBody) =>
      unwrap(
        api.PATCH('/api/admin/club-events/{event_id}', {
          params: { path: { event_id: id } },
          body,
        }),
      ),
    onSuccess: refresh,
  });
}

export function useCancelEvent(id: number) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: () =>
      unwrap(
        api.POST('/api/admin/club-events/{event_id}/cancel', {
          params: { path: { event_id: id } },
        }),
      ),
    onSuccess: refresh,
  });
}

export function useRestoreEvent(id: number) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: () =>
      unwrap(
        api.POST('/api/admin/club-events/{event_id}/restore', {
          params: { path: { event_id: id } },
        }),
      ),
    onSuccess: refresh,
  });
}

export function useDeleteEvent(id: number) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE('/api/admin/club-events/{event_id}', { params: { path: { event_id: id } } }),
      ),
    onSuccess: refresh,
  });
}

type RegistrationPath = { params: { path: { event_id: number; registration_id: number } } };
const regPath = (eventId: number, registrationId: number): RegistrationPath => ({
  params: { path: { event_id: eventId, registration_id: registrationId } },
});

export function useRemoveRegistration(eventId: number) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (registrationId: number) =>
      unwrap(
        api.DELETE(
          '/api/admin/club-events/{event_id}/registrations/{registration_id}',
          regPath(eventId, registrationId),
        ),
      ),
    onSuccess: refresh,
  });
}

export function useSetGuests(eventId: number) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ registrationId, guests }: { registrationId: number; guests: number }) =>
      unwrap(
        api.PATCH('/api/admin/club-events/{event_id}/registrations/{registration_id}', {
          ...regPath(eventId, registrationId),
          body: { guests },
        }),
      ),
    onSuccess: refresh,
  });
}

export function useLinkRegistration(eventId: number) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ registrationId, shooterId }: { registrationId: number; shooterId: number }) =>
      unwrap(
        api.POST('/api/admin/club-events/{event_id}/registrations/{registration_id}/link', {
          ...regPath(eventId, registrationId),
          body: { shooter_id: shooterId },
        }),
      ),
    onSuccess: refresh,
  });
}

export function useResetCancelLimit(eventId: number) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (registrationId: number) =>
      unwrap(
        api.POST(
          '/api/admin/club-events/{event_id}/registrations/{registration_id}/reset-cancel-limit',
          regPath(eventId, registrationId),
        ),
      ),
    onSuccess: refresh,
  });
}

export function useSetContact() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ shooterId, email }: { shooterId: number; email: string }) =>
      unwrap(
        api.PUT('/api/admin/shooter-contacts/{shooter_id}', {
          params: { path: { shooter_id: shooterId } },
          body: { email },
        }),
      ),
    onSuccess: refresh,
  });
}

export function useDeleteContact() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (shooterId: number) =>
      unwrap(
        api.DELETE('/api/admin/shooter-contacts/{shooter_id}', {
          params: { path: { shooter_id: shooterId } },
        }),
      ),
    onSuccess: refresh,
  });
}

/** One audited read per click (§5.5), for "Copy emails". */
export async function fetchEmails(id: number, status: EmailsStatus): Promise<string[]> {
  const body = await unwrap(
    api.GET('/api/admin/club-events/{event_id}/emails', {
      params: { path: { event_id: id }, query: { status } },
    }),
  );
  return body.emails;
}

/** Downloads the server's CSV (every cell already escaped there, §5.5). */
export async function downloadRosterCsv(
  event: Pick<AdminEvent, 'id' | 'local_date'>,
): Promise<void> {
  const response = await fetch(`/api/admin/club-events/${event.id}/roster.csv`, {
    credentials: 'include',
  });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => undefined);
    throw toApiError(response.status, body);
  }
  downloadBlob(await response.blob(), `club-event-${event.id}-${event.local_date}-roster.csv`);
}
