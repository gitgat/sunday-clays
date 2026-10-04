import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router';
import { ApiError } from '../../../api/errors';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { AdminPreviewBadge } from '../../../components/ui/AdminPreviewBadge';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { FEATURES_QUERY_KEY } from '../../../lib/features';
import { shareElementAsImage } from '../../../lib/share';
import { useClubEvent, type RosterRow } from '../api';
import { CancelSheet, type CancelTarget } from '../components/CancelSheet';
import { MyStatus } from '../components/MyStatus';
import { Roster } from '../components/Roster';
import { SignUpSheet, type SignedUp } from '../components/SignUpSheet';
import { CANCELLED, deadlineLine, guestsRule, spotsLine, whenLine } from '../format';
import { acknowledgePromotions, forgetEvent, reconcile, useDeviceSignups } from '../tokens';

/** /club-events/:id (§5.7.3). Every open/closed/started decision is the server's `state` (D21). */
export function ClubEventPage() {
  const params = useParams();
  const id = Number(params.id);
  const event = useClubEvent(id);
  const qc = useQueryClient();
  const signups = useDeviceSignups();
  const [signingUp, setSigningUp] = useState(false);
  const [sheetKey, setSheetKey] = useState(0);
  const [cancelling, setCancelling] = useState<CancelTarget | null>(null);
  const [justSigned, setJustSigned] = useState<SignedUp | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const shareRef = useRef<HTMLDivElement>(null);
  const data = event.data;

  useEffect(() => {
    if (data !== undefined) reconcile(data.id, data.roster);
  }, [data]);
  useEffect(() => {
    if (!(event.error instanceof ApiError)) return;
    if (event.error.code === 'club_event_not_found') {
      forgetEvent(id); // the event is gone: its tokens are useless (§5.9)
    } else if (event.error.status === 404 && event.error.code === 'http_404') {
      // The gate's 404: the switch went off while this page was open (§5.1, §5.9). The event may
      // still exist, so keep the tokens, and refetch the switches so FeatureGate shows NotFoundView.
      void qc.invalidateQueries({ queryKey: FEATURES_QUERY_KEY });
    }
  }, [event.error, id, qc]);
  // The "Good news" line shows during the visit that found the promotion, not on every later one.
  useEffect(() => () => acknowledgePromotions(id), [id]);

  if (event.isError && !(event.error instanceof ApiError && event.error.status === 404)) {
    return (
      <div className="flex flex-col gap-3">
        <p role="alert">Could not load this club event. Try again.</p>
        <div>
          <Button variant="tonal" onClick={() => void event.refetch()}>
            Try again
          </Button>
        </div>
      </div>
    );
  }
  if (!Number.isInteger(id) || id <= 0 || event.isError) {
    return (
      <EmptyState
        title="That club event isn't on the list."
        action={
          <Link to="/club-events" className="inline-flex min-h-11 items-center underline">
            See all club events
          </Link>
        }
      />
    );
  }
  if (data === undefined) return <Skeleton label="Loading the club event" />;

  const mine = signups.filter((s) => s.eventId === data.id);
  const mineIds = new Set(mine.map((s) => s.registrationId));
  const myRow = data.roster.find((r) => mineIds.has(r.registration_id));
  const mySignup = mine.find((s) => s.registrationId === myRow?.registration_id);
  const canCancel = data.state !== 'started';
  const deadline = deadlineLine(data);
  const url = `${window.location.origin}/club-events/${data.id}`;

  const cancelRow = (row: RosterRow) => {
    const own = mine.find((s) => s.registrationId === row.registration_id);
    setCancelling(
      own
        ? { kind: 'own', registrationId: row.registration_id, token: own.token, guests: row.guests }
        : { kind: 'other', registrationId: row.registration_id, name: row.name },
    );
  };
  const share = async () => {
    await shareElementAsImage(shareRef.current as HTMLDivElement, `club-event-${data.id}`);
  };
  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setNotice('Link copied');
    } catch {
      setNotice(url);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div ref={shareRef} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="min-w-0 break-words text-2xl font-bold">{data.title}</h1>
            <AdminPreviewBadge feature="events" />
          </div>
          <p className="text-text-muted">{whenLine(data)}</p>
          <div className="flex flex-wrap gap-2" data-share-exclude="">
            <Button variant="tonal" onClick={() => void share()}>
              Share
            </Button>
            <Button variant="tonal" onClick={() => void copyLink()}>
              Copy link
            </Button>
            <p aria-live="polite" className="self-center text-sm text-text-muted">
              {notice}
            </p>
          </div>
        </div>
        {data.state === 'cancelled' && (
          <p
            role="note"
            className="rounded-card border border-outline-variant bg-elevated p-4 font-medium"
          >
            {CANCELLED}
          </p>
        )}
        {myRow !== undefined && (
          <div data-share-exclude="">
            <MyStatus
              row={myRow}
              promoted={mySignup?.promoted === true}
              onFileName={
                justSigned?.result.registration_id === myRow.registration_id &&
                justSigned.result.email_used === 'on_file' &&
                justSigned.typedEmail
                  ? justSigned.name
                  : null
              }
              canCancel={canCancel}
              onCancel={() => cancelRow(myRow)}
            />
          </div>
        )}
        {data.notes !== '' && (
          <Card title="Notes">
            <p className="whitespace-pre-line break-words">{data.notes}</p>
          </Card>
        )}
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
          <dt className="text-text-muted">Spots</dt>
          <dd>{spotsLine(data)}</dd>
          <dt className="text-text-muted">Guests</dt>
          <dd>{guestsRule(data)}</dd>
          {deadline !== null && (
            <>
              <dt className="text-text-muted">Sign-ups</dt>
              <dd>{deadline}</dd>
            </>
          )}
        </dl>
      </div>

      {myRow === undefined && data.state === 'open' && (
        <Button
          className="w-full sm:w-auto"
          onClick={() => {
            setSheetKey((k) => k + 1);
            setSigningUp(true);
          }}
        >
          Sign up
        </Button>
      )}
      {myRow === undefined && (data.state === 'closed' || data.state === 'started') && (
        <Button className="w-full sm:w-auto" disabled>
          Sign-ups closed
        </Button>
      )}

      <Card title="Who's coming">
        <Roster event={data} mine={mineIds} onCancel={cancelRow} />
      </Card>

      <SignUpSheet
        key={sheetKey}
        event={data}
        open={signingUp}
        onClose={() => setSigningUp(false)}
        onSignedUp={(done) => {
          setJustSigned(done);
          setSigningUp(false);
        }}
      />
      <CancelSheet eventId={data.id} target={cancelling} onClose={() => setCancelling(null)} />
    </div>
  );
}
