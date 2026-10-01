import { createContext, useContext, useId, useState, type ReactNode } from 'react';
import { getDeviceId } from '../../lib/device';
import { BUMPS_OFF, bumpsKey, sortedKeys, useBumps, type BumpCounts, type BumpsKey } from './api';
import { BumpButton } from './BumpButton';

interface BumpsContextValue {
  queryKey: BumpsKey;
  deviceId: string | null;
  counts: BumpCounts | undefined;
  noteId: string;
  /** Says a bump failed, once for the whole section (the polite live region). */
  announce: (message: string) => void;
}

const BumpsContext = createContext<BumpsContextValue | null>(null);

/**
 * Fetches the bump counts for every insight a page section shows, in one request, and hands them
 * to each `InsightBump` inside. When this browser cannot keep a device id, it says once why the
 * buttons are off.
 */
export function BumpsProvider({
  keys,
  children,
  note = true,
}: {
  keys: Iterable<string>;
  children: ReactNode;
  /** False when the page puts the "off" note somewhere itself, with `<BumpsOffNote />`. */
  note?: boolean;
}) {
  const [deviceId] = useState(getDeviceId);
  const noteId = useId();
  const [announcement, announce] = useState('');
  const sorted = sortedKeys(keys);
  const bumps = useBumps(sorted, deviceId);
  const value = {
    queryKey: bumpsKey(sorted, deviceId),
    deviceId,
    counts: bumps.data,
    noteId,
    announce,
  };
  return (
    <BumpsContext value={value}>
      {note && <BumpsOffNote />}
      {/* One permanent polite region (not role=status: that reads as "loading" to the e2e), so
          several failed bumps are read out once. Each failed button still shows its own text. */}
      <p aria-live="polite" className="sr-only">
        {announcement}
      </p>
      {children}
    </BumpsContext>
  );
}

/** Why the buttons are off, once per section: nothing when this browser keeps a device id. */
export function BumpsOffNote() {
  const bumps = useContext(BumpsContext);
  if (bumps === null || bumps.deviceId !== null) return null;
  return (
    <p id={bumps.noteId} className="text-sm text-text-muted">
      {BUMPS_OFF}
    </p>
  );
}

/** 🤜🤛 for one insight; nothing outside a BumpsProvider, so a lone card never fetches. */
export function InsightBump({
  insightKey,
  describedBy,
}: {
  insightKey: string;
  /** The id of the insight's headline: the button's description (its name stays "Fist bump, N"). */
  describedBy?: string;
}) {
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
      announce={bumps.announce}
      describedBy={describedBy}
    />
  );
}
