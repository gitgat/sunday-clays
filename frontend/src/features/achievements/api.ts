import { skipToken, useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';

export function useAchievements() {
  return useQuery({
    queryKey: ['/api/achievements'],
    queryFn: () => unwrap(api.GET('/api/achievements')),
  });
}

export function useAchievement(code: string) {
  return useQuery({
    queryKey: ['/api/achievements/{code}', code],
    queryFn: () => unwrap(api.GET('/api/achievements/{code}', { params: { path: { code } } })),
  });
}

/** `null` (no "That's me" choice yet) skips the request (TanStack v5 `skipToken`). */
export function useShooterAchievements(shooterId: number | null) {
  return useQuery({
    queryKey: ['/api/shooters/{id}/achievements', shooterId],
    queryFn:
      shooterId === null
        ? skipToken
        : () =>
            unwrap(
              api.GET('/api/shooters/{id}/achievements', { params: { path: { id: shooterId } } }),
            ),
  });
}

export function useEventAchievements(date: string) {
  return useQuery({
    queryKey: ['/api/events/{date}/achievements', date],
    queryFn: () =>
      unwrap(api.GET('/api/events/{date}/achievements', { params: { path: { date } } })),
  });
}
