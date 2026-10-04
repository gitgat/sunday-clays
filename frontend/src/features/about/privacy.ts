/** One line of the About page's "Your privacy" card. `feature` marks a line that shows only while
 * that launch switch is visible (an admin sees it with the "Admin preview" badge). */
export interface PrivacyLine {
  text: string;
  feature?: 'events';
}

/** Plan 19 §4: shown only while `link_previews` is visible (it describes that feature), last. */
export const LINK_PREVIEWS_LINE =
  'Links shared in chat apps show only the club name, and for a Sunday its date (or a special shoot’s title), how many shot and the round type. Never shooter names or scores.';

/** How long backups hold deleted data (backup prune: 14 daily + 8 weekly dumps). One place to edit. */
export const BACKUP_RETENTION_SENTENCE =
  'Nightly backups that still hold deleted data are themselves deleted within about two months.';

/**
 * Plan 20 §5.7.6. The two club-event lines state the retention rules of
 * backend/src/sunday_clays/domain/club_events.py (30 days, 730 days, D16): change them together.
 * The link-preview sentence is not here: the page adds it after these lines (Plan 19).
 */
export function privacyLines(clubEvents: boolean): PrivacyLine[] {
  return [
    { text: 'No accounts. There are no logins beyond the club’s shared password.' },
    {
      text: 'Browsing the site collects nothing about you: no name, no email. The site processes the club’s score sheets and analyses them.',
    },
    ...(clubEvents
      ? [
          {
            text: 'If you sign up for a club event, we keep your name and the email you give us so organizers can reach you.',
            feature: 'events' as const,
          },
          {
            text: `Only organizers see emails. We never show them on the site and never send email from it. Sign-ups are deleted 30 days after the event; an email saved for a shooter stays for quicker sign-ups until an organizer removes it or it goes two years unused. ${BACKUP_RETENTION_SENTENCE}`,
            feature: 'events' as const,
          },
        ]
      : []),
    { text: '“Which one are you?” is remembered on your device and never sent anywhere.' },
    {
      text: `Fist bumps and visit counts are anonymous. They use a random ID your browser makes up, never tied to a name. We don’t store IP addresses for any of it${clubEvents ? ', sign-ups included' : ''}.`,
    },
    { text: 'No ads, no third-party trackers.' },
  ];
}
