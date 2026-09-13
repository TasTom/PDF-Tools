/**
 * URL publique du site.
 *
 * Next en a besoin pour construire les URL absolues des metadonnees
 * (balises `og:url`, `canonical`) et du plan de site. Sans cela, il emet un
 * avertissement et les URL relatives ne peuvent pas etre resolues.
 *
 * En production, definir `SITE_URL` (meme valeur que cote backend).
 */
export const SITE_URL = (process.env.SITE_URL ?? 'https://pdf.warult-tools.com').replace(/\/$/, '');
