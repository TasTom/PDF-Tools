import type { Metadata } from 'next';
import { IBM_Plex_Mono, IBM_Plex_Sans } from 'next/font/google';

import SiteHeader from '@/components/SiteHeader';
import { AuthProvider } from '@/lib/auth';
import { SITE_URL } from '@/lib/site';
import './globals.css';

/**
 * Deux fontes, deux roles distincts.
 *
 * IBM Plex Sans vient de la documentation technique : dessinee pour du texte
 * d'ingenierie, ce qui est le sujet du site. IBM Plex Mono sert a tout ce qui
 * est MESURE (tailles, pages, points) ; sa presence n'est pas decorative, elle
 * separe les valeurs des phrases. Aucune des deux n'est la fonte par defaut
 * d'un projet genere (Inter, system-ui).
 */
const sans = IBM_Plex_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-sans',
  display: 'swap',
});

const mono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  // Sans metadataBase, Next ne peut pas construire les URL absolues des
  // metadonnees et emet un avertissement au build.
  metadataBase: new URL(SITE_URL),
  title: {
    default: 'PDF Tools — dix opérations sur un document',
    template: '%s · PDF Tools',
  },
  alternates: { canonical: '/' },
  description:
    'Fusionner, découper, compresser, convertir, protéger vos PDF. Dix outils gratuits, dans la limite d’un quota quotidien. Les fichiers sont traités le temps de l’opération, puis oubliés.',
  keywords: [
    'pdf', 'fusionner pdf', 'compresser pdf', 'découper pdf',
    'convertir pdf en image', 'protéger pdf', 'filigrane pdf',
  ],
  openGraph: {
    type: 'website',
    locale: 'fr_FR',
    url: SITE_URL,
    siteName: 'PDF Tools',
    title: 'PDF Tools — dix opérations sur un document',
    description: 'Dix outils PDF gratuits, dans la limite d’un quota quotidien.',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className={`${sans.variable} ${mono.variable}`}>
      <body className="flex min-h-screen flex-col bg-paper text-ink">
        {/* Le fournisseur de session enveloppe l'en-tete ET le contenu : les
            deux lisent l'etat de connexion, et le contenu des outils s'en sert
            pour envoyer son jeton. */}
        <AuthProvider>
          <SiteHeader />

          <main className="flex-1">{children}</main>

          <footer className="mt-24 border-t border-rule">
            <div className="mx-auto flex max-w-6xl flex-col gap-2 px-5 py-8 sm:flex-row sm:items-baseline sm:justify-between">
              <p className="max-w-measure text-sm text-ink-soft">
                Les fichiers sont traités le temps de l’opération, puis oubliés.
                Aucun stockage, aucune revente.
              </p>
              <p className="font-mono text-xs text-ink-faint">© 2026 warult-tools.com</p>
            </div>
          </footer>
        </AuthProvider>
      </body>
    </html>
  );
}
