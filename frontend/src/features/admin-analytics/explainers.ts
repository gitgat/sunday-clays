import type { Explainer } from '../../components/charts/types';

/**
 * Plain-language copy for the admin Analytics page, keyed by ChartFrame urlKey. Written against
 * domain/page_views.py and domain/site_analytics.py (STYLE.md: no jargon, neutral pronouns,
 * "Sunday" not "event").
 */
export const analyticsExplainers = {
  visitors: {
    what: 'How many different phones and computers opened the site each day or week.',
    read: [
      'Tall bars are busy days. Per week runs Monday to Sunday.',
      'Ends today. Starts at the window start, or the first day the site has any data if later.',
      'Fullscreen and the CSV download cover every day on record.',
    ],
    computed: [
      'Each browser keeps a random id that says nothing about who uses it.',
      'A week counts each id once, so a week is not its days added up.',
      'Admin visits and browsers that block site storage are never counted.',
    ],
  },
  pages: {
    what: 'Which parts of the site people open most.',
    read: [
      'Longer bars are the pages people open most.',
      'Ends today. Starts at the window start, or the first day the site has any data if later.',
      'Fullscreen and the CSV download cover every day on record.',
    ],
    computed: [
      'A device opening a page counts once per page type every 30 minutes.',
      'Pages are grouped: every shooter profile is “Shooter profiles” and every Sunday’s results page is “One Sunday”.',
      'Admin visits are never counted.',
    ],
  },
  bumps: {
    what: 'How many fist bumps insights got each day, and which insights got the most.',
    read: [
      'A bar is the bumps given that day that still stand.',
      'Ends today. Starts at the window start, or the first day the site has any data if later.',
      'Fullscreen and the CSV download cover every day on record.',
    ],
    computed: [
      'One bump per device per insight. Taking a bump back removes it.',
      'The list shows each insight’s headline and its bump count. One no longer on the site loses its headline.',
      'Devices that bumped counts each device once.',
    ],
  },
  uptake: {
    what: 'How many devices answered “Which one are you?”, week by week.',
    read: [
      'Picked a name: chose a shooter. Skipped: said not a shooter. Not answered: neither yet.',
      'Weeks start on Monday. Ends today. Starts at the window start, or the first day the site has any data if later.',
      'Fullscreen and the CSV download cover every week on record.',
    ],
    computed: [
      'Each device counts once a week, with its last answer that week.',
      'The line above the chart uses each device’s last answer, from visits still kept in detail.',
      'Only the answer is kept, never the name picked.',
    ],
  },
} satisfies Record<string, Explainer>;
