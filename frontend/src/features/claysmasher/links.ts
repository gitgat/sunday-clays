/**
 * ClaySmasher link (spec 2026-10-01 §3.1, §4.2, U1). The app claims the claysmasher.com page as an
 * iOS universal link and an Android App Link; claysmasher.com serves the association files and the
 * page shown without the app. It is a different host from this site on purpose: iOS keeps a
 * universal link tapped on a page of its own domain in Safari.
 */
export const CLAYSMASHER_WEB_LINK = 'https://claysmasher.com/link/sunday-clays';
/** The custom scheme the app registers from its first release (spec §5.1). */
export const CLAYSMASHER_SCHEME_LINK = 'claysmasher://sunday-clays/link';

/**
 * Off until the ClaySmasher release that handles the link ships and claysmasher.com's AASA is
 * validated (spec §11 step 4). Merging to main deploys, so turning the button on is a one-line PR.
 */
export const CLAYSMASHER_BUTTON_ENABLED = false;

/**
 * 'universal' opens the claysmasher.com page (the app, when installed). 'scheme' is the fallback if
 * Apple rejects the AASA that GitHub Pages serves (spec §4.2, §10.2): the button opens the app's
 * custom scheme, with a web link under it for phones without the app.
 */
export type ClaySmasherLinkMode = 'universal' | 'scheme';
export const CLAYSMASHER_LINK_MODE: ClaySmasherLinkMode = 'universal';

export function claysmasherWebUrl(shooterId: number): string {
  return `${CLAYSMASHER_WEB_LINK}?shooter=${shooterId}`;
}

export function claysmasherSchemeUrl(shooterId: number): string {
  return `${CLAYSMASHER_SCHEME_LINK}?shooter=${shooterId}`;
}
