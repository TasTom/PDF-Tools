'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { useAuth } from '@/lib/auth';
import { TOOLS } from '@/lib/tools';

/**
 * En-tête : identité de la marque, index des dix outils, état de session.
 *
 * Ce n'est pas un menu deroulant mais la liste complete : dix mots courts
 * tiennent sur une ligne et evitent d'avoir a ouvrir quoi que ce soit. Quand
 * la place manque, la liste passe a la ligne : rien n'est jamais masque
 * derriere un defilement horizontal, ou l'oeil ne va pas chercher.
 *
 * La page courante est la seule entree en accent : c'est une information de
 * position, pas une decoration.
 */
export default function SiteHeader() {
  const pathname = usePathname();
  const { user, loading } = useAuth();

  return (
    <header className="border-b border-rule">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-5 py-4 lg:flex-row lg:items-baseline lg:justify-between">
        <Link href="/" className="font-mono text-[13px] font-medium tracking-[0.1em] text-ink">
          WARULT
        </Link>

        <nav
          aria-label="Les dix outils"
          className="flex flex-wrap items-baseline gap-x-5 gap-y-1.5"
        >
          {TOOLS.map(tool => {
            const href = `/tools/${tool.slug}`;
            const courante = pathname === href;
            return (
              <Link
                key={tool.slug}
                href={href}
                aria-current={courante ? 'page' : undefined}
                className={`text-sm ${courante ? 'text-accent' : 'text-ink-soft hover:text-ink'}`}
              >
                {tool.label}
              </Link>
            );
          })}
        </nav>

        {/* `loading` evite de faire clignoter « Connexion » avant de savoir si
            une session existe deja. */}
        <div className="font-mono text-xs">
          {loading ? (
            <span className="text-ink-faint">…</span>
          ) : user ? (
            <Link href="/account" className="text-ink-soft hover:text-ink">
              {user.username}
              <span className="ml-2 text-ink-faint">
                {user.daily_usage}/{user.daily_limit}
              </span>
            </Link>
          ) : (
            <Link href="/auth/login" className="text-ink-soft hover:text-ink">
              Connexion
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
