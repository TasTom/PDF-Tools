import type { MetadataRoute } from 'next';

import { SITE_URL } from '@/lib/site';

/**
 * Regles d'exploration.
 *
 * Tout est ouvert : c'est un site public dont le trafic vient de la recherche.
 * Le seul refus explicite vise `/api/`, qui n'a rien a faire dans un index et
 * dont l'exploration consommerait le quota de debit par IP.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      disallow: '/api/',
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
