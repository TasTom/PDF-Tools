import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: {
    default: 'PDF Tools — Outils PDF Gratuits en Ligne',
    template: '%s | PDF Tools',
  },
  description: 'Outils PDF gratuits : fusionner, découper, compresser, convertir, protéger vos fichiers PDF en ligne.',
  keywords: ['pdf tools', 'merge pdf', 'compress pdf', 'pdf to image', 'split pdf', 'outils pdf gratuits'],
  openGraph: {
    type: 'website',
    locale: 'fr_FR',
    url: 'https://pdf.warult-tools.com',
    siteName: 'PDF Tools',
    title: 'PDF Tools — Outils PDF Gratuits en Ligne',
    description: 'Fusionnez, découpez, compressez et convertissez vos PDF gratuitement.',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="bg-slate-950 text-white min-h-screen">
        <nav className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-md sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-4 flex items-center justify-between h-16">
            <a href="/" className="text-xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
              PDF Tools
            </a>
            <div className="hidden md:flex items-center gap-6 text-sm text-slate-300">
              <a href="/tools/merge" className="hover:text-white transition">Fusionner</a>
              <a href="/tools/split" className="hover:text-white transition">Découper</a>
              <a href="/tools/compress" className="hover:text-white transition">Compresser</a>
              <a href="/tools/to-image" className="hover:text-white transition">PDF → Image</a>
              <a href="/tools/protect" className="hover:text-white transition">Protéger</a>
              <a href="/pricing" className="hover:text-white transition">Tarifs</a>
            </div>
            <a href="/auth/login" className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm transition">
              Connexion
            </a>
          </div>
        </nav>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-slate-800 py-8 text-center text-sm text-slate-500">
          <p>© 2026 PDF Tools — warult-tools.com. Tous droits réservés.</p>
        </footer>
      </body>
    </html>
  );
}
