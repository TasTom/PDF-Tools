import type { Metadata } from 'next';
import { Suspense } from 'react';

import AuthForm from '@/components/AuthForm';

export const metadata: Metadata = {
  title: 'Créer un compte',
  description: 'Créez un compte gratuit pour utiliser les dix outils PDF.',
  robots: { index: false, follow: false },
};

export default function RegisterPage() {
  return (
    <Suspense fallback={null}>
      <AuthForm mode="register" />
    </Suspense>
  );
}
