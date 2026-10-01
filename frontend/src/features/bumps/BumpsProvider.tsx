import { createContext, useContext, useId, useState, type ReactNode } from 'react';
import { getDeviceId } from '../../lib/device';
import { BUMPS_OFF, bumpsKey, sortedKeys, useBumps, type BumpCounts, type BumpsKey } from './api';
import { BumpButton } from './BumpButton';

interface BumpsContextValue {
  queryKey: BumpsKey;
  deviceId: string | null;
  counts: BumpCounts | undefined;
  noteId: string;
}

const BumpsContext = createContext<BumpsContextValue | null>(null);

/**
 * Fetches the bump counts for every insight a page section shows, in one request, and hands them
 * to each `InsightBump` inside. When this browser cannot keep a device id, it says once why the
 * buttons are off.
 */
export function BumpsProvider({ keys, children }: { keys: Iterable<string>; children: ReactNode }) {
  const [deviceId] = useState(getDeviceId);
  const noteId = useId();
  const sorted = sortedKeys(keys);
  const bumps = useBumps(sorted, deviceId);
  const value = { queryKey: bumpsKey(sorted, deviceId), deviceId, counts: bumps.data, noteId };
  return (
    <BumpsContext value={value}>
      {deviceId === null && (
        <p id={noteId} className="text-sm text-text-muted">
          {BUMPS_OFF}
        </p>
      )}
      {children}
    </BumpsContext>
  );
}

/** 🤜🤛 for one insight; nothing outside a BumpsProvider, so a lone card never fetches. */
export function InsightBump({ insightKey }: { insightKey: string }) {
  const bumps = useContext(BumpsContext);
  if (bumps === null) return null;
  return (
    <BumpButton
      queryKey={bumps.queryKey}
      insightKey={insightKey}
      deviceId={bumps.deviceId}
      state={bumps.counts?.[insightKey]}
      noteId={bumps.noteId}
      counts={bumps.counts}
    />
  );
}
