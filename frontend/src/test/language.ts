/**
 * R1 (Plan 19 §5.1): app copy never uses he/she/his/her/him/hers/himself/herself or "class".
 * Each new copy file's test asserts no match over every string it exports.
 */
export const BANNED_WORDS = /\b(he|she|his|her|him|hers|himself|herself|class(es)?)\b/i;

/** Every string inside a value: strings themselves, and the strings of arrays and objects. */
export function allStrings(value: unknown): string[] {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(allStrings);
  if (value !== null && typeof value === 'object') return Object.values(value).flatMap(allStrings);
  return [];
}

/**
 * The weekly club email is read by people who never open the site: nothing in it may point at the
 * site's own words (second person, ratings and skill, models, tiers and metals, charts, taps).
 */
export const OUTSIDER_BANNED =
  /\b(you|your|yours|rating|skill|model|tier|level|chart|tap|see the|bronze|silver|gold|platinum|diamond)s?\b|usual for a day like/i;
