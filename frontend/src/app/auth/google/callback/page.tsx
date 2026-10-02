import type { Metadata } from 'next';

import GoogleCallback from '@/components/GoogleCallback';

/**
 * Retour de Google.
 *
 * `robots: index false` : cette adresse ne veut rien dire pour un moteur de
 * recherche et n'a rien à faire dans un index. Elle est aussi inatteignable
 * directement, puisqu'elle a besoin d'un jeton dans l'URL.
 */
export const metadata: Metadata = {
  title: 'Connexion Google',
  description: 'Finalisation de la connexion avec Google.',
  robots: { index: false, follow: false },
};

export default function GoogleCallbackPage() {
  return <GoogleCallback />;
}
