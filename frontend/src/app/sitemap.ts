import type { MetadataRoute } from 'next';

import { SITE_URL } from '@/lib/site';
import { TOOLS } from '@/lib/tools';
/**
 * Plan de site.
 *
 * Lighthouse note le referencement d'UNE page ; il ne dit rien de la
 * trouvabilite de l'ensemble. Les dix outils sont autant de portes d'entree
 * par recherche (« compresser un pdf »), ils doivent donc tous etre declares.
 *
 * `lastModified` est volontairement omis : les pages sont statiques et ne
 * bougent pas seules. Une date inventee serait un mensonge que les moteurs
 * finissent par ignorer.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const home = {
    url: `${SITE_URL}/`,
    changeFrequency: 'monthly' as const,
    priority: 1,
  };

  const tools = TOOLS.map(tool => ({
    url: `${SITE_URL}/tools/${tool.slug}`,
    changeFrequency: 'monthly' as const,
    priority: 0.8,
  }));

  return [home, ...tools];
}
