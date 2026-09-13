'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { TOOLS } from '@/lib/tools';

/**
 * L'index des dix outils, dans l'en-tete.
 *
 * Ce n'est pas un menu deroulant mais la liste complete : dix mots courts
 * tiennent sur une ligne et evitent d'avoir a ouvrir quoi que ce soit. Quand
 * la place manque, la liste passe a la ligne : rien n'est jamais masque
 * derriere un defilement horizontal, ou l'oeil ne va pas chercher.
 *
 * La page courante est la seule entree en accent : c'est une information de
 * position, pas une decoration.
 */
export default function ToolIndex() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Les dix outils"
      className="flex flex-wrap items-baseline gap-x-5 gap-y-1.5"
    >
      {TOOLS.map(tool => {
        const href = `/tools/${tool.slug}`;
        const current = pathname === href;
        return (
          <Link
            key={tool.slug}
            href={href}
            aria-current={current ? 'page' : undefined}
            className={`text-sm ${
              current ? 'text-accent' : 'text-ink-soft hover:text-ink'
            }`}
          >
            {tool.label}
          </Link>
        );
      })}
    </nav>
  );
}
