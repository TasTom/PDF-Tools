import type { Metadata } from 'next';

import { getTool } from '@/lib/tools';

/**
 * Metadonnees d'une page d'outil : titre, description et URL canonique.
 *
 * Centralise ici plutot que recopie dans les dix pages : le titre et la
 * description viennent deja de `lib/tools.ts`, et la canonique ne doit pas
 * pouvoir diverger du slug. Les pages tres proches se ressemblent beaucoup, et
 * une canonique explicite evite que les moteurs les traitent comme du contenu
 * duplique.
 */
export function toolMetadata(slug: string): Metadata {
  const tool = getTool(slug);
  return {
    title: tool.title,
    description: tool.blurb,
    alternates: { canonical: `/tools/${tool.slug}` },
  };
}
