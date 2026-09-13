/**
 * Definition unique des dix outils.
 *
 * Tout vient d'ici : le sommaire de l'accueil, l'index de l'en-tete, le titre
 * de la page, ses champs et les metadonnees de referencement. Une seule liste
 * a tenir a jour, donc aucun risque qu'un libelle diverge entre deux endroits.
 */

export type ParamOption = {
  /** Valeur transmise a l'API. */
  value: string;
  /** Libelle affiche, en francais. */
  label: string;
};

export type Param = {
  name: string;
  label: string;
  type: 'text' | 'number' | 'select';
  options?: ParamOption[];
  defaultValue?: string;
  /** Precisions affichees sous le champ. */
  hint?: string;
};

export type Tool = {
  slug: string;
  /** Nom court, pour l'index de l'en-tete. */
  label: string;
  /** Titre complet, en tete de page et dans le sommaire. */
  title: string;
  /** Une phrase : ce que l'outil fait au document. */
  blurb: string;
  /**
   * Verbe a l'imperatif, affiche sur le bouton. Un bouton dit ce qui va se
   * passer, et garde le meme nom du debut a la fin du parcours.
   */
  action: string;
  endpoint: string;
  accept: string;
  multiple?: boolean;
  params?: Param[];
  /**
   * Ce qui est dit quand le resultat prend la forme d'une archive ZIP.
   * Propre a chaque outil : « le document a ete separe » convient au decoupage
   * mais pas a la conversion en images, qui ne separe rien du tout.
   */
  archiveNote: string;
};

export const TOOLS: Tool[] = [
  {
    slug: 'merge',
    label: 'Fusionner',
    title: 'Fusionner des PDF',
    blurb: 'Réunir plusieurs fichiers en un seul document, dans l’ordre choisi.',
    action: 'Fusionner',
    endpoint: '/api/pdf/merge',
    accept: '.pdf',
    multiple: true,
    archiveNote: 'Les fichiers fusionnés sont réunis dans une archive ZIP.',
  },
  {
    slug: 'split',
    label: 'Découper',
    title: 'Découper un PDF',
    blurb: 'Extraire certaines pages, ou séparer le document page par page.',
    action: 'Découper',
    endpoint: '/api/pdf/split',
    accept: '.pdf',
    archiveNote: 'Le document a été séparé page par page. Elles sont réunies dans une archive ZIP.',
    params: [
      {
        name: 'pages',
        label: 'Pages à extraire',
        type: 'text',
        defaultValue: '',
        hint: 'Par exemple 1,3,5-8. Laisser vide pour prendre toutes les pages.',
      },
    ],
  },
  {
    slug: 'compress',
    label: 'Compresser',
    title: 'Compresser un PDF',
    blurb: 'Alléger un document trop lourd, en réencodant ses images.',
    action: 'Compresser',
    endpoint: '/api/pdf/compress',
    accept: '.pdf',
    archiveNote: 'Le document compressé est dans une archive ZIP.',
    params: [
      {
        name: 'quality',
        label: 'Niveau de compression',
        type: 'select',
        defaultValue: 'medium',
        options: [
          // La resolution est indiquee : c'est la seule facon pour l'utilisateur
          // de savoir ce qu'il perd. Les trois valeurs correspondent aux paliers
          // du service (voir _COMPRESS_PRESETS cote backend).
          { value: 'low', label: 'Forte — fichier le plus léger (≈ 100 ppp)' },
          { value: 'medium', label: 'Moyenne — bon compromis (≈ 160 ppp)' },
          { value: 'high', label: 'Légère — qualité préservée (≈ 250 ppp)' },
        ],
        hint: 'La définition et la qualité sont ajustées. Le fichier renvoyé n’est jamais plus lourd que celui envoyé.',
      },
    ],
  },
  {
    slug: 'to-image',
    label: 'PDF → Image',
    title: 'Convertir un PDF en images',
    blurb: 'Rendre chaque page en PNG ou JPEG, à la résolution choisie.',
    action: 'Convertir',
    endpoint: '/api/pdf/to-image',
    accept: '.pdf',
    archiveNote: 'Chaque page a été convertie en image. Elles sont réunies dans une archive ZIP.',
    params: [
      {
        name: 'format',
        label: 'Format des images',
        type: 'select',
        defaultValue: 'png',
        options: [
          { value: 'png', label: 'PNG (sans perte)' },
          { value: 'jpeg', label: 'JPEG (plus léger)' },
        ],
      },
      {
        name: 'dpi',
        label: 'Résolution',
        type: 'select',
        defaultValue: '150',
        options: [
          { value: '72', label: '72 ppp (écran)' },
          { value: '150', label: '150 ppp (standard)' },
          { value: '300', label: '300 ppp (impression)' },
        ],
      },
    ],
  },
  {
    slug: 'from-images',
    label: 'Image → PDF',
    title: 'Assembler des images en PDF',
    blurb: 'Réunir des PNG ou JPEG en un document, une image par page.',
    action: 'Assembler',
    endpoint: '/api/pdf/from-images',
    accept: 'image/*',
    multiple: true,
    archiveNote: 'Le PDF assemblé est dans une archive ZIP.',
  },
  {
    slug: 'protect',
    label: 'Protéger',
    title: 'Protéger un PDF',
    blurb: 'Verrouiller le document par un mot de passe.',
    action: 'Protéger',
    endpoint: '/api/pdf/protect',
    accept: '.pdf',
    archiveNote: 'Le document protégé est dans une archive ZIP.',
    params: [
      {
        name: 'password',
        label: 'Mot de passe à appliquer',
        type: 'text',
        hint: 'Il sera demandé à chaque ouverture du document.',
      },
    ],
  },
  {
    slug: 'unprotect',
    label: 'Déverrouiller',
    title: 'Déverrouiller un PDF',
    blurb: 'Retirer le mot de passe d’un document dont vous le connaissez.',
    action: 'Déverrouiller',
    endpoint: '/api/pdf/unprotect',
    accept: '.pdf',
    archiveNote: 'Le document déverrouillé est dans une archive ZIP.',
    params: [
      { name: 'password', label: 'Mot de passe actuel', type: 'text' },
    ],
  },
  {
    slug: 'watermark',
    label: 'Filigrane',
    title: 'Ajouter un filigrane',
    blurb: 'Marquer chaque page d’un texte en diagonale.',
    action: 'Appliquer le filigrane',
    endpoint: '/api/pdf/watermark',
    accept: '.pdf',
    archiveNote: 'Le document filigrané est dans une archive ZIP.',
    params: [
      { name: 'text', label: 'Texte du filigrane', type: 'text', defaultValue: 'CONFIDENTIEL' },
      {
        name: 'opacity',
        label: 'Opacité',
        type: 'select',
        defaultValue: '0.3',
        options: [
          { value: '0.1', label: 'Très discrète (0,1)' },
          { value: '0.3', label: 'Discrète (0,3)' },
          { value: '0.6', label: 'Marquée (0,6)' },
          { value: '1', label: 'Opaque (1)' },
        ],
      },
    ],
  },
  {
    slug: 'rotate',
    label: 'Pivoter',
    title: 'Pivoter des pages',
    blurb: 'Redresser un document scanné de travers, page par page.',
    action: 'Pivoter',
    endpoint: '/api/pdf/rotate',
    accept: '.pdf',
    archiveNote: 'Le document pivoté est dans une archive ZIP.',
    params: [
      {
        name: 'angle',
        label: 'Angle',
        type: 'select',
        defaultValue: '90',
        options: [
          { value: '90', label: '90° dans le sens horaire' },
          { value: '180', label: '180° (sens dessus dessous)' },
          { value: '270', label: '270° dans le sens horaire' },
        ],
      },
      {
        name: 'pages',
        label: 'Pages concernées',
        type: 'text',
        defaultValue: '',
        hint: 'Par exemple 1,3,5-8. Laisser vide pour tourner toutes les pages.',
      },
    ],
  },
  {
    slug: 'crop',
    label: 'Recadrer',
    title: 'Recadrer des pages',
    blurb: 'Réduire les pages à une zone précise, en points typographiques.',
    action: 'Recadrer',
    endpoint: '/api/pdf/crop',
    accept: '.pdf',
    archiveNote: 'Le document recadré est dans une archive ZIP.',
    params: [
      { name: 'x', label: 'Marge gauche (points)', type: 'text', defaultValue: '0' },
      { name: 'y', label: 'Marge basse (points)', type: 'text', defaultValue: '0' },
      { name: 'w', label: 'Largeur (points)', type: 'text', defaultValue: '595' },
      { name: 'h', label: 'Hauteur (points)', type: 'text', defaultValue: '842' },
    ],
  },
];

export function getTool(slug: string): Tool {
  const tool = TOOLS.find(t => t.slug === slug);
  if (!tool) throw new Error(`Outil inconnu : ${slug}`);
  return tool;
}
