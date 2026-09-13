'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useRef } from 'react';

import { useAuth } from '@/lib/auth';

/**
 * Compte : identité, quota du jour, déconnexion.
 *
 * C'est aussi la page qui rend le quota visible. Sans elle, un utilisateur
 * verrait ses opérations refusées sans comprendre pourquoi.
 */
export default function AccountPage() {
  const { user, loading, logout, refresh } = useAuth();
  const router = useRouter();

  // Vrai quand l'utilisateur a lui-même demandé la déconnexion. Sans ce
  // drapeau, le bouton ET la garde ci-dessous declencheraient chacun une
  // navigation : la seconde est abandonnee en vol, la transition React ne se
  // commite jamais, et l'en-tete reste figé sur l'identite precedente.
  const deconnexionVoulue = useRef(false);

  // Le quota affiché doit être à jour : l'utilisateur vient peut-être de
  // consommer des opérations dans un autre onglet.
  useEffect(() => {
    if (!loading && user) void refresh();
  }, [loading, user, refresh]);

  // Garde : session absente ou expirée. On renvoie vers la connexion en
  // mémorisant la page d'origine pour y revenir ensuite.
  useEffect(() => {
    if (loading || user || deconnexionVoulue.current) return;
    router.replace('/auth/login?suivant=/account');
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="mx-auto max-w-2xl px-5 py-16">
        <p className="text-ink-faint">Chargement…</p>
      </div>
    );
  }

  const utilisees = user.daily_usage;
  const total = user.daily_limit;
  const restantes = Math.max(0, total - utilisees);

  return (
    <div className="mx-auto max-w-2xl px-5 py-16">
      <h1 className="text-[28px] font-semibold leading-tight tracking-[-0.01em]">Compte</h1>

      <dl className="mt-8 divide-y divide-rule border-y border-rule">
        <div className="flex items-baseline justify-between gap-6 py-4">
          <dt className="text-ink-soft">Nom d’utilisateur</dt>
          <dd className="font-mono text-sm text-ink">{user.username}</dd>
        </div>
        <div className="flex items-baseline justify-between gap-6 py-4">
          <dt className="text-ink-soft">Adresse email</dt>
          <dd className="font-mono text-sm text-ink">{user.email}</dd>
        </div>
        <div className="flex items-baseline justify-between gap-6 py-4">
          <dt className="text-ink-soft">Opérations aujourd’hui</dt>
          <dd className="font-mono text-sm text-ink">
            {utilisees} sur {total}
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-6 py-4">
          <dt className="text-ink-soft">Restantes</dt>
          <dd className={`font-mono text-sm ${restantes === 0 ? 'text-accent' : 'text-ink'}`}>
            {restantes}
          </dd>
        </div>
      </dl>

      {restantes === 0 && (
        <p className="mt-4 text-sm text-ink-soft">
          Le quota se réinitialise à minuit.
        </p>
      )}

      <div className="mt-10 flex flex-wrap items-center gap-4">
        <Link
          href="/"
          className="rounded-sm bg-ink px-5 py-2.5 font-medium text-paper hover:bg-accent"
        >
          Retour aux outils
        </Link>
        <button
          type="button"
          onClick={() => {
            deconnexionVoulue.current = true;
            logout();
            // Une seule navigation : la garde ci-dessus est neutralisee.
            router.replace('/auth/login');
          }}
          className="rounded-sm border border-rule px-5 py-2.5 font-medium text-ink hover:border-ink"
        >
          Se déconnecter
        </button>
      </div>
    </div>
  );
}
