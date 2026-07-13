const tools = [
  { slug: 'merge', icon: '📄', title: 'Fusionner PDF', desc: 'Combiner plusieurs PDF en un seul fichier', color: 'from-blue-500 to-blue-600' },
  { slug: 'split', icon: '✂️', title: 'Découper PDF', desc: 'Extraire des pages spécifiques d\'un PDF', color: 'from-purple-500 to-purple-600' },
  { slug: 'compress', icon: '🗜️', title: 'Compresser PDF', desc: 'Réduire la taille de vos fichiers PDF', color: 'from-green-500 to-green-600' },
  { slug: 'to-image', icon: '🖼️', title: 'PDF → Image', desc: 'Convertir les pages PDF en images PNG/JPG', color: 'from-orange-500 to-orange-600' },
  { slug: 'from-images', icon: '📋', title: 'Image → PDF', desc: 'Créer un PDF à partir de plusieurs images', color: 'from-pink-500 to-pink-600' },
  { slug: 'protect', icon: '🔒', title: 'Protéger PDF', desc: 'Ajouter un mot de passe à vos PDF', color: 'from-red-500 to-red-600' },
  { slug: 'unprotect', icon: '🔓', title: 'Déverrouiller PDF', desc: 'Supprimer la protection mot de passe', color: 'from-yellow-500 to-yellow-600' },
  { slug: 'watermark', icon: '💧', title: 'Filigrane PDF', desc: 'Ajouter un filigrane texte à chaque page', color: 'from-cyan-500 to-cyan-600' },
  { slug: 'rotate', icon: '🔄', title: 'Pivoter PDF', desc: 'Rotation 90°, 180° ou 270° des pages', color: 'from-indigo-500 to-indigo-600' },
  { slug: 'crop', icon: '✂️', title: 'Recadrer PDF', desc: 'Recadrer les pages à une taille personnalisée', color: 'from-teal-500 to-teal-600' },
];

export default function Home() {
  return (
    <div className="max-w-6xl mx-auto px-4 py-16">
      <div className="text-center mb-16">
        <h1 className="text-5xl font-bold mb-6 bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
          PDF Tools
        </h1>
        <p className="text-xl text-slate-300 mb-4">
          Outils PDF gratuits et rapides — tout en ligne, sans inscription
        </p>
        <p className="text-slate-400 max-w-2xl mx-auto">
          Fusionnez, découpez, compressez, convertissez et protégez vos fichiers PDF
          directement depuis votre navigateur. Gratuit, rapide et sécurisé.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {tools.map((tool) => (
          <a
            key={tool.slug}
            href={`/tools/${tool.slug}`}
            className="group rounded-2xl border border-slate-700 bg-slate-900/50 p-6 hover:border-blue-500 hover:bg-blue-500/5 transition-all"
          >
            <div className="text-4xl mb-3">{tool.icon}</div>
            <h2 className="text-lg font-semibold text-white group-hover:text-blue-300 mb-1">
              {tool.title}
            </h2>
            <p className="text-sm text-slate-400">{tool.desc}</p>
          </a>
        ))}
      </div>

      <div className="mt-20 text-center">
        <h2 className="text-2xl font-bold text-white mb-4">Pourquoi PDF Tools ?</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-8">
          <div className="text-center">
            <div className="text-3xl mb-2">⚡</div>
            <h3 className="font-semibold text-white mb-1">Ultra rapide</h3>
            <p className="text-sm text-slate-400">Traitement côté serveur en quelques secondes</p>
          </div>
          <div className="text-center">
            <div className="text-3xl mb-2">🔒</div>
            <h3 className="font-semibold text-white mb-1">100% sécurisé</h3>
            <p className="text-sm text-slate-400">Les fichiers sont supprimés après traitement</p>
          </div>
          <div className="text-center">
            <div className="text-3xl mb-2">💰</div>
            <h3 className="font-semibold text-white mb-1">Gratuit</h3>
            <p className="text-sm text-slate-400">10 opérations/jour sans inscription</p>
          </div>
        </div>
      </div>
    </div>
  );
}
