import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type ClubEventSummary = components['schemas']['ClubEventSummaryOut'];
export type ClubEventDetail = components['schemas']['ClubEventDetailOut'];
export type ClubEventList = components['schemas']['ClubEventListOut'];
export type RosterRow = components['schemas']['ClubRosterRowOut'];
export type SignupCheck = components['schemas']['ClubSignupCheckOut'];
export type SignupBody = components['schemas']['ClubSignupIn'];
export type SignupResult = components['schemas']['ClubSignupOut'];

/** Every club-event query starts with this key, so one invalidation refreshes them all. */
export const CLUB_EVENTS_KEY = ['/api/club-events'] as const;
export const clubEventKey = (id: number) => ['/api/club-events', id] as const;

/** The list. Cached for a minute, so the Home card renders at once on a later visit (§5.7.4). */
export function useClubEvents(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: CLUB_EVENTS_KEY,
    queryFn: () => unwrap(api.GET('/api/club-events')),
    staleTime: 60_000,
    enabled: options.enabled ?? true,
  });
}

export function useClubEvent(id: number) {
  return useQuery({
    queryKey: clubEventKey(id),
    queryFn: () =>
      unwrap(api.GET('/api/club-events/{event_id}', { params: { path: { event_id: id } } })),
    enabled: Number.isInteger(id) && id > 0,
  });
}

/** One check per picked name (D11 accepted exception); never refetched on focus. */
export function useSignupCheck(eventId: number, shooterId: number | null) {
  return useQuery({
    queryKey: ['/api/club-events', eventId, 'signup-check', shooterId] as const,
    queryFn: () =>
      unwrap(
        api.GET('/api/club-events/{event_id}/signup-check', {
          params: { path: { event_id: eventId }, query: { shooter_id: Number(shooterId) } },
        }),
      ),
    enabled: shooterId !== null,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}

export function useSignUp(eventId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SignupBody) =>
      unwrap(
        api.POST('/api/club-events/{event_id}/registrations', {
          params: { path: { event_id: eventId } },
          body,
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: CLUB_EVENTS_KEY }),
  });
}

export type CancelInput =
  { registrationId: number; token: string } | { registrationId: number; email: string };

export function useCancelSignup(eventId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CancelInput) =>
      unwrap(
        api.POST('/api/club-events/{event_id}/registrations/{registration_id}/cancel', {
          params: { path: { event_id: eventId, registration_id: input.registrationId } },
          body: 'token' in input ? { token: input.token } : { email: input.email },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: CLUB_EVENTS_KEY }),
  });
}
