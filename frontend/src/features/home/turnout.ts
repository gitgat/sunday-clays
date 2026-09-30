import type { EventSummary } from './api';

/** An event's turnout: its attendance head count, else the shooters with scores. */
export function turnout(event: EventSummary): number {
  return event.head_count ?? event.n_shooters;
}
