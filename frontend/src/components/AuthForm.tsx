'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useState } from 'react';

import { useAuth } from '@/lib/auth';

/**
 * Formulaire d'inscription et de connexion.
 *
 * Un seul composant pour les deux modes : les champs et la validation sont
 * presque identiques, et les séparer garantirait qu'une correction n'atterrisse
 * que d'un côté.
 */
export default function AuthForm({ mode }: { mode: 'login' | 'register' }) {
  const { login, register } = useAuth();
  const router = useRouter();
  const parametres = useSearchParams();

  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [erreur, setErreur] = useState('');
  const [enCours, setEnCours] = useState(false);

  const inscription = mode === 'register';

  const envoyer = async (evenement: React.FormEvent) => {
    evenement.preventDefault();
    setErreur('');
    setEnCours(true);
    try {
      if (inscription) {
        await register(email, username, password);
      } else {
        await login(email, password);
      }
      // Retour à l'outil demandé, ou à l'accueil. `suivant` est posé par la page
      // d'outil quand elle redirige un visiteur sans compte.
      router.push(parametres.get('suivant') || '/');
    } catch (cause) {
      setErreur(cause instanceof Error ? cause.message : 'La connexion a échoué.');
      setEnCours(false);
    }
  };

  return (
    <div className="mx-auto max-w-md px-5 py-16">
      <h1 className="text-[28px] font-semibold leading-tight tracking-[-0.01em]">
        {inscription ? 'Créer un compte' : 'Se connecter'}
      </h1>
      <p className="mt-2 text-ink-soft">
        {inscription
          ? 'Un compte suffit pour les dix outils. Il sert uniquement à compter les opérations du jour.'
          : 'Connectez-vous pour accéder aux outils.'}
      </p>

      <form onSubmit={envoyer} className="mt-8 space-y-5">
        <div>
          <label htmlFor="email" className="block text-sm text-ink-soft">
            Adresse email
          </label>
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={evenement => setEmail(evenement.target.value)}
            className="mt-1.5 w-full rounded-sm border border-rule bg-white px-3 py-2.5 text-ink"
          />
        </div>

        {inscription && (
          <div>
            <label htmlFor="username" className="block text-sm text-ink-soft">
              Nom d’utilisateur
            </label>
            <input
              id="username"
              type="text"
              required
              minLength={3}
              autoComplete="username"
              value={username}
              onChange={evenement => setUsername(evenement.target.value)}
              className="mt-1.5 w-full rounded-sm border border-rule bg-white px-3 py-2.5 text-ink"
            />
            <p className="mt-1.5 text-xs text-ink-faint">
              Au moins 3 caractères, lettres et chiffres uniquement.
            </p>
          </div>
        )}

        <div>
          <label htmlFor="password" className="block text-sm text-ink-soft">
            Mot de passe
          </label>
          <input
            id="password"
            type="password"
            required
            autoComplete={inscription ? 'new-password' : 'current-password'}
            value={password}
            onChange={evenement => setPassword(evenement.target.value)}
            className="mt-1.5 w-full rounded-sm border border-rule bg-white px-3 py-2.5 text-ink"
          />
          {inscription && (
            <p className="mt-1.5 text-xs text-ink-faint">
              Au moins 8 caractères, dont une majuscule et un chiffre.
            </p>
          )}
        </div>

        {erreur && (
          <p
            role="alert"
            className="rounded-sm border border-accent bg-accent-soft px-4 py-3 text-sm text-accent"
          >
            {erreur}
          </p>
        )}

        <button
          type="submit"
          disabled={enCours}
          className="w-full rounded-sm bg-ink px-5 py-3 font-medium text-paper disabled:cursor-not-allowed disabled:bg-rule disabled:text-ink-faint"
        >
          {enCours ? 'Un instant…' : inscription ? 'Créer le compte' : 'Se connecter'}
        </button>
      </form>

      <p className="mt-6 text-sm text-ink-soft">
        {inscription ? (
          <>
            Déjà un compte ?{' '}
            <Link href="/auth/login" className="text-accent">
              Se connecter
            </Link>
          </>
        ) : (
          <>
            Pas encore de compte ?{' '}
            <Link href="/auth/register" className="text-accent">
              En créer un
            </Link>
          </>
        )}
      </p>
    </div>
  );
}
