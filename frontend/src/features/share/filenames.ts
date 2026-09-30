/** Lower-case ASCII words joined by dashes ("Hadley, Ike" -> "hadley-ike"); never empty. */
export function slugify(text: string): string {
  const slug = text
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '') // combining marks left by NFKD
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return slug === '' ? 'image' : slug;
}

export function eventFilename(date: string): string {
  return `sunday-clays-${date}.png`;
}

export function profileFilename(name: string): string {
  return `sunday-clays-${slugify(name)}.png`;
}

export function trophyFilename(code: string): string {
  return `sunday-clays-trophy-${slugify(code)}.png`;
}

export function cardFilename(title: string): string {
  return `sunday-clays-${slugify(title)}.png`;
}
