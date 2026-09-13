import type { Metadata } from 'next';
import { Suspense } from 'react';

import AuthForm from '@/components/AuthForm';

export const metadata: Metadata = {
  title: 'Connexion',
  description: 'Connectez-vous pour utiliser les dix outils PDF.',
  robots: { index: false, follow: false },
};

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <AuthForm mode="login" />
    </Suspense>
  );
}
