import Link from 'next/link';

import Diagram from '@/components/Diagram';
import { TOOLS } from '@/lib/tools';

/**
 * L'accueil EST le sommaire. Pas de heros centre, pas de paragraphes de vente,
 * pas de bloc « pourquoi nous » : qui arrive ici a un fichier a traiter, et la
 * seule chose utile est la liste des operations.
 *
 * La liste n'est pas rangee au hasard : elle est groupee par SENS de la
 * transformation (reunir, separer, retoucher, verrouiller), ce qui reprend
 * exactement ce que montre chaque schema. Quatre groupes de 2, 2, 4 et 2 —
 * structure volontairement inegale, choisie pour le contenu et non pour
 * remplir une grille.
 */
const GROUPS: { label: string; slugs: string[] }[] = [
  { label: 'Réunir', slugs: ['merge', 'from-images'] },
  { label: 'Séparer', slugs: ['split', 'to-image'] },
  { label: 'Retoucher', slugs: ['compress', 'crop', 'rotate', 'watermark'] },
  { label: 'Verrouiller', slugs: ['protect', 'unprotect'] },
];

export default function Home() {
  return (
    <div className="mx-auto max-w-6xl px-5">
      <div className="pt-12 pb-14 sm:pt-16">
        <h1 className="text-[32px] font-semibold leading-[1.15] tracking-[-0.02em] sm:text-[40px]">
          PDF Tools
        </h1>
        <p className="mt-4 max-w-measure text-lg text-ink-soft">
          Dix opérations sur un document, gratuitement et sans compte.
        </p>
        <p className="mt-2 max-w-measure text-ink-faint">
          Vos fichiers ne sont pas conservés.
        </p>
      </div>

      <div className="space-y-12 pb-4">
        {GROUPS.map(group => (
          <section key={group.label} aria-labelledby={`groupe-${group.label}`}>
            <div className="lg:grid lg:grid-cols-[8rem_minmax(0,1fr)] lg:gap-x-10">
              <h2
                id={`groupe-${group.label}`}
                className="mb-4 font-mono text-xs text-ink-faint lg:mb-0 lg:pt-1"
              >
                {group.label}
              </h2>

              <ul className="grid gap-x-10 gap-y-7 sm:grid-cols-2">
                {group.slugs.map(slug => {
                  const tool = TOOLS.find(t => t.slug === slug);
                  if (!tool) return null;
                  return (
                    <li key={slug}>
                      <Link
                        href={`/tools/${tool.slug}`}
                        className="group flex items-start gap-4"
                      >
                        <Diagram slug={tool.slug} className="mt-0.5" />
                        <span className="min-w-0">
                          <span className="block font-medium text-ink transition-colors group-hover:text-accent">
                            {tool.title}
                          </span>
                          <span className="mt-1 block text-sm text-ink-soft">
                            {tool.blurb}
                          </span>
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
