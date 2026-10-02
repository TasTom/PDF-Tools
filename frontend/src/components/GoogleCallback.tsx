'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';

import { useAuth } from '@/lib/auth';
import { extraireJeton, lireRetourGoogle } from '@/lib/google';

/**
 * Finalise la connexion Google.
 *
 * Google renvoie le navigateur ici avec un jeton d'identité dans le fragment
 * d'URL. Ce composant l'extrait, vérifie qu'il répond bien à la tentative de
 * connexion en cours, puis le remet au serveur — seul juge de son authenticité.
 *
 * Le traitement est enveloppé dans une garde : en développement, React exécute
 * les effets deux fois, et sans cela le jeton serait envoyé deux fois. Sans
 * conséquence ici, mais cela produirait deux appels réseau et un état d'erreur
 * possible au second passage, puisque le `nonce` est consommé à la première
 * lecture.
 */
export default function GoogleCallback() {
  const { googleLogin } = useAuth();
  const router = useRouter();
  const [erreur, setErreur] = useState('');
  const dejaTraite = useRef(false);

  useEffect(() => {
    if (dejaTraite.current) return;
    dejaTraite.current = true;

    const terminer = async () => {
      try {
        const { nonce, suivant } = lireRetourGoogle();
        const jeton = extraireJeton(window.location.hash, nonce);
        await googleLogin(jeton);
        // On remplace l'entrée courante : revenir en arrière ne doit pas
        // rejouer un jeton déjà consommé.
        router.replace(suivant);
      } catch (cause) {
        setErreur(
          cause instanceof Error
            ? cause.message
            : 'La connexion avec Google a échoué.',
        );
      }
    };

    void terminer();
  }, [googleLogin, router]);

  if (erreur) {
    return (
      <div className="mx-auto max-w-md px-5 py-16">
        <h1 className="text-[28px] font-semibold leading-tight tracking-[-0.01em]">
          Connexion Google
        </h1>
        <p
          role="alert"
          className="mt-6 rounded-sm border border-accent bg-accent-soft px-4 py-3 text-sm text-accent"
        >
          {erreur}
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/auth/login"
            className="rounded-sm bg-ink px-5 py-2.5 font-medium text-paper hover:bg-accent"
          >
            Revenir à la connexion
          </Link>
          <Link
            href="/"
            className="rounded-sm border border-rule px-5 py-2.5 font-medium text-ink hover:border-ink"
          >
            Accueil
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md px-5 py-16">
      <h1 className="text-[28px] font-semibold leading-tight tracking-[-0.01em]">
        Connexion Google
      </h1>
      <p className="mt-2 text-ink-soft">Un instant…</p>
    </div>
  );
}
