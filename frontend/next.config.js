/** @type {import('next').NextConfig} */
const apiBase = process.env.BACKEND_URL || 'http://localhost:8000';

// Le service accepte des fichiers jusqu'a MAX_UPLOAD_MB (50 Mo par defaut).
// Le proxy de Next, lui, plafonne a 10 Mo (DEFAULT_BODY_CLONE_SIZE_LIMIT) : au
// dela il ne transmet qu'un corps tronque, la requete part malformee et echoue
// en 500 apres trente secondes. Mesure sur cette machine : un PDF de 13,9 Mo
// passe en 2,3 s en direct contre le service, et echouait a travers le proxy.
//
// Cette limite porte sur le corps TOTAL de la requete, alors que le service
// verifie fichier par fichier : « fusionner » accepte jusqu'a 20 fichiers. Elle
// doit donc depasser MAX_UPLOAD_MB, sinon un fichier hors limite serait tronque
// ici et l'utilisateur lirait « transfert echoue » au lieu du message precis du
// service (« Fichier trop volumineux »).
//
// A savoir : Next bufferise ce corps EN MEMOIRE, par requete en cours. Relever
// la limite releve d'autant l'empreinte memoire du serveur frontal ; la baisser
// est le premier levier si l'hebergeur manque de memoire.
const parsedProxyMb = Number(process.env.PROXY_MAX_BODY_MB ?? 100);
const proxyMaxBodyMb = Number.isFinite(parsedProxyMb) && parsedProxyMb > 0 ? parsedProxyMb : 100;

const nextConfig = {
  output: 'standalone',
  experimental: {
    middlewareClientMaxBodySize: `${proxyMaxBodyMb}mb`,
  },
  async rewrites() {
    return [
      { source: '/api/:path*', destination: `${apiBase}/api/:path*` },
    ];
  },
};

module.exports = nextConfig;
