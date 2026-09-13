/**
 * Schemas de transformation.
 *
 * Chaque outil est represente par le meme enonce visuel : un document avant,
 * une fleche, un document apres. Le lecteur comprend l'operation sans lire.
 *
 * Regles communes a tous les schemas :
 * - un seul trace, une seule epaisseur (1,5) ;
 * - l'etat AVANT est en `ink-faint`, l'etat APRES en `ink` ;
 * - ce que l'operation AJOUTE au document (verrou, filigrane, reperes de
 *   coupe) est en `accent`, et nulle part ailleurs : c'est le sens de la
 *   couleur dans tout le site.
 *
 * Le schema n'est pas un ornement : le titre de l'outil est juste a cote, donc
 * il est marque `aria-hidden` pour ne pas etre annonce deux fois.
 */

type Tone = 'ink' | 'ink-faint' | 'accent';

const TONE_CLASS: Record<Tone, string> = {
  ink: 'text-ink',
  'ink-faint': 'text-ink-faint',
  accent: 'text-accent',
};

function Group({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return (
    <g
      className={TONE_CLASS[tone]}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="square"
    >
      {children}
    </g>
  );
}

/** Une feuille de papier. */
function Sheet({
  x, y, w, h, tone = 'ink',
}: { x: number; y: number; w: number; h: number; tone?: Tone }) {
  return (
    <Group tone={tone}>
      <rect x={x} y={y} width={w} height={h} rx={1} />
    </Group>
  );
}

/** La fleche de transformation, toujours au meme endroit. */
function Arrow() {
  return (
    <Group tone="ink-faint">
      <path d="M28 18 H40" />
      <path d="M36.5 14.5 L40 18 L36.5 21.5" />
    </Group>
  );
}

/** Pictogramme d'image, pour les conversions. */
function PhotoMark({ cx, cy, size = 9, tone = 'accent' }: { cx: number; cy: number; size?: number; tone?: Tone }) {
  const w = size;
  const h = size * 0.78;
  const x = cx - w / 2;
  const y = cy - h / 2;
  return (
    <Group tone={tone}>
      <rect x={x} y={y} width={w} height={h} rx={0.5} />
      <path
        d={`M${x + w * 0.1} ${y + h * 0.92} L${x + w * 0.42} ${y + h * 0.45} L${x + w * 0.62} ${y + h * 0.72} L${x + w * 0.78} ${y + h * 0.55} L${x + w * 0.95} ${y + h * 0.92}`}
      />
      <circle cx={x + w * 0.28} cy={y + h * 0.3} r={size * 0.07} />
    </Group>
  );
}

/** Verrou ferme. */
function LockMark({ cx, cy }: { cx: number; cy: number }) {
  const w = 11;
  const h = 8;
  const x = cx - w / 2;
  const y = cy - h / 2 + 2;
  const r = 3.4;
  return (
    <Group tone="accent">
      <rect x={x} y={y} width={w} height={h} rx={1} />
      <path d={`M${cx - r} ${y} V${y - 1.6} A${r} ${r} 0 0 1 ${cx + r} ${y - 1.6} V${y}`} />
    </Group>
  );
}

/** Reperes de coupe, aux quatre coins d'une zone. */
function CropMarks({ x, y, w, h, arm = 4.5 }: { x: number; y: number; w: number; h: number; arm?: number }) {
  return (
    <Group tone="accent">
      <path d={`M${x} ${y + arm} V${y} H${x + arm}`} />
      <path d={`M${x + w - arm} ${y} H${x + w} V${y + arm}`} />
      <path d={`M${x + w} ${y + h - arm} V${y + h} H${x + w - arm}`} />
      <path d={`M${x + arm} ${y + h} H${x} V${y + h - arm}`} />
    </Group>
  );
}

const SHEET = { x: 5, y: 7, w: 16, h: 22 };

const DIAGRAMS: Record<string, React.ReactNode> = {
  // Deux documents empiles deviennent un seul.
  merge: (
    <>
      <Sheet x={2} y={9} w={12} h={18} tone="ink-faint" />
      <Sheet x={8} y={6} w={12} h={18} tone="ink-faint" />
      <Arrow />
      <Sheet x={51} y={7} w={16} h={22} />
    </>
  ),

  // Un document se separe en plusieurs.
  split: (
    <>
      <Sheet {...SHEET} tone="ink-faint" />
      <Arrow />
      <Sheet x={46} y={7} w={11} h={22} />
      <Sheet x={59} y={7} w={11} h={22} />
    </>
  ),

  // Meme contenu, resserre dans une feuille plus petite.
  compress: (
    <>
      <Sheet {...SHEET} tone="ink-faint" />
      <Arrow />
      <Sheet x={52} y={10} w={12} h={16} />
      <Group tone="ink-faint">
        <path d="M55 15 H61" />
        <path d="M55 18 H61" />
        <path d="M55 21 H61" />
      </Group>
    </>
  ),

  // Un document dont les pages deviennent des images.
  'to-image': (
    <>
      <Sheet {...SHEET} tone="ink-faint" />
      <Arrow />
      <Sheet x={51} y={7} w={16} h={22} />
      <PhotoMark cx={59} cy={18} size={10} />
    </>
  ),

  // Plusieurs images deviennent un document.
  'from-images': (
    <>
      <Sheet x={2} y={9} w={11} h={18} tone="ink-faint" />
      <PhotoMark cx={7.5} cy={18} size={7} tone="ink-faint" />
      <Sheet x={14} y={9} w={11} h={18} tone="ink-faint" />
      <PhotoMark cx={19.5} cy={18} size={7} tone="ink-faint" />
      <Arrow />
      <Sheet x={51} y={7} w={16} h={22} />
    </>
  ),

  // Le document se ferme : l'accent marque exactement ce qui est ajoute.
  protect: (
    <>
      <Sheet {...SHEET} tone="ink-faint" />
      <Arrow />
      <Sheet x={51} y={7} w={16} h={22} />
      <LockMark cx={59} cy={18} />
    </>
  ),

  // Le verrou s'en va : rien n'est ajoute au document, donc pas d'accent ici.
  unprotect: (
    <>
      <Sheet {...SHEET} tone="ink-faint" />
      <Group tone="ink-faint">
        <rect x={7.5} y={16} width={11} height={8} rx={1} />
        <path d="M10 16 V14.4 A3.4 3.4 0 0 1 16.8 14.4 V16" />
      </Group>
      <Arrow />
      <Sheet x={51} y={7} w={16} h={22} />
    </>
  ),

  // Un texte traverse le document.
  watermark: (
    <>
      <Sheet {...SHEET} tone="ink-faint" />
      <Arrow />
      <Sheet x={51} y={7} w={16} h={22} />
      <Group tone="accent">
        <path d="M53 24 L65 12" />
        <path d="M53 28 L65 16" />
        <path d="M53 20 L65 8" />
      </Group>
    </>
  ),

  // La feuille se redresse.
  rotate: (
    <>
      <Sheet {...SHEET} tone="ink-faint" />
      <Arrow />
      <Group tone="ink">
        <rect x={51} y={7} width={16} height={22} rx={1} transform="rotate(-13 59 18)" />
      </Group>
      <Group tone="accent">
        <path d="M47 12 A6.5 6.5 0 0 1 53.5 6" />
        <path d="M47.6 8.4 L47 12 L50.6 12.6" />
      </Group>
    </>
  ),

  // On ne garde qu'une zone de la page.
  crop: (
    <>
      <Sheet {...SHEET} tone="ink-faint" />
      <CropMarks x={8} y={11} w={10} h={13} />
      <Arrow />
      <Sheet x={53} y={10} w={12} h={16} />
      <CropMarks x={53} y={10} w={12} h={16} arm={3.5} />
    </>
  ),
};

export default function Diagram({ slug, className = '' }: { slug: string; className?: string }) {
  const drawing = DIAGRAMS[slug];
  if (!drawing) return null;

  return (
    <svg
      viewBox="0 0 72 36"
      className={`h-9 w-[72px] shrink-0 ${className}`}
      aria-hidden="true"
      focusable="false"
    >
      {drawing}
    </svg>
  );
}
