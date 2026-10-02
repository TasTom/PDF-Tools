/**
 * Connexion Google : départ vers Google, puis retour.
 *
 * Le mécanisme est réparti sur deux pages qui ne se voient pas — le formulaire
 * de connexion d'un côté, la page de retour de l'autre. Elles doivent pourtant
 * s'accorder sur deux points précis : la valeur de `nonce` et la page où
 * revenir ensuite. Les clés de stockage et la construction d'URL sont donc
 * définies ici, une seule fois, plutôt que dupliquées : une désynchronisation
 * entre les deux moitiés produit un échec de connexion difficile à lire.
 *
 * Pourquoi une redirection complète plutôt que le widget « Google Identity
 * Services » : ce dernier s'appuie sur FedCM, que les navigateurs et les
 * bloqueurs de contenu désactivent ou retardent de plus en plus souvent. La
 * redirection, elle, ne dépend d'aucun script tiers chargé dans la page.
 */

export const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? '';

const CLE_NONCE = 'google_oauth_nonce';
const CLE_SUIVANT = 'google_oauth_suivant';

/** Identifiants stockés le temps de l'aller-retour chez Google. */
type RetourGoogle = {
  /** `nonce` déposé avant le départ, à retrouver dans le jeton au retour. */
  nonce: string | null;
  /** Page demandée par l'utilisateur, pour l'y ramener. */
  suivant: string;
};

export function googleConfigure(): boolean {
  return GOOGLE_CLIENT_ID.length > 0;
}

/**
 * Construit l'adresse du jeton et envoie le navigateur chez Google.
 *
 * Le `nonce` est tiré au sort ici et vérifié au retour : il prouve que le jeton
 * reçu répond bien à CE départ, et non à une requête forgée entre-temps. Il est
 * conservé en `sessionStorage`, donc effacé à la fermeture de l'onglet.
 *
 * `suivant` est mémorisé pour la même raison : sans lui, un visiteur venu de
 * `/tools/compress` se retrouverait à l'accueil après s'être connecté.
 */
export function demarrerConnexionGoogle(suivant: string): void {
  if (!googleConfigure()) {
    throw new Error("La connexion Google n'est pas configurée.");
  }

  // Google accepte `http://localhost:…` mais pas `http://127.0.0.1:…` : les deux
  // adresses désignent pourtant la même machine, et l'une des deux se rencontre
  // dès qu'un serveur de développement écoute sur la boucle locale.
  let origine = window.location.origin;
  try {
    const url = new URL(origine);
    if (url.hostname === '127.0.0.1' || url.hostname === '::1') {
      url.hostname = 'localhost';
      origine = url.toString().replace(/\/$/, '');
    }
  } catch {
    // Origine inhabituelle : on la garde telle quelle.
  }

  const nonce = crypto.randomUUID();
  window.sessionStorage.setItem(CLE_NONCE, nonce);
  window.sessionStorage.setItem(CLE_SUIVANT, suivant);

  const parametres = new URLSearchParams({
    client_id: GOOGLE_CLIENT_ID,
    redirect_uri: `${origine}/auth/google/callback`,
    response_type: 'id_token',
    scope: 'openid email profile',
    nonce,
    prompt: 'select_account',
  });

  window.location.href = `https://accounts.google.com/o/oauth2/v2/auth?${parametres}`;
}

/**
 * Relit ce qui a été déposé au départ, et efface le `nonce`.
 *
 * Il est retiré à la lecture : un aller-retour ne doit servir qu'une fois, même
 * si l'utilisateur revient en arrière ou recharge la page.
 *
 * `suivant` est assaini au passage. Sa valeur vient du `sessionStorage`, que
 * l'utilisateur peut modifier : sans contrôle, elle pourrait désigner une adresse
 * externe et servir de tremplin au moment de la redirection.
 */
export function lireRetourGoogle(): RetourGoogle {
  const nonce = window.sessionStorage.getItem(CLE_NONCE);
  const brut = window.sessionStorage.getItem(CLE_SUIVANT) || '/';

  // Une destination valide est un chemin interne. « //exemple.com » et
  // « https://exemple.com » sont des adresses absolues déguisées : on les refuse.
  const suivant = brut.startsWith('/') && !brut.startsWith('//') ? brut : '/';

  window.sessionStorage.removeItem(CLE_NONCE);
  window.sessionStorage.removeItem(CLE_SUIVANT);
  return { nonce, suivant };
}

/**
 * Décode la charge utile d'un JWT, écrite en base64url.
 *
 * `atob` n'accepte que le base64 standard. Les charges utiles JWT utilisent
 * l'alphabet « url » (`-` et `_` au lieu de `+` et `/`) et omettent le
 * remplissage `=`. Les passer tel quel à `atob` fonctionne tant qu'aucun de ces
 * caractères n'apparaît — puis échoue sur « Jeton illisible » pour un jeton
 * parfaitement valide. La conversion est donc faite explicitement.
 */
function decoderChargeUtile(charge: string): Record<string, unknown> {
  const base64 = charge.replace(/-/g, '+').replace(/_/g, '/');
  const complete = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=');
  return JSON.parse(atob(complete));
}

/**
 * Extrait le jeton d'identité du fragment d'URL, et vérifie le `nonce`.
 *
 * Google place le jeton après le `#`, pas dans la requête : le fragment n'est
 * jamais transmis au serveur, ce qui évite qu'un jeton traîne dans les journaux.
 *
 * Le `nonce` est lu dans le jeton SANS en vérifier la signature — c'est
 * volontaire et sans risque : cette lecture sert seulement à écarter un jeton
 * qui ne correspond pas à ce départ. L'authenticité, elle, est établie par le
 * serveur, qui interroge Google. Un jeton forgé échouerait là-bas.
 */
export function extraireJeton(fragment: string, nonceAttendu: string | null): string {
  const parametres = new URLSearchParams(fragment.replace(/^#/, ''));
  const jeton = parametres.get('id_token');

  if (!jeton) {
    const refus = parametres.get('error');
    throw new Error(
      refus === 'access_denied'
        ? 'Connexion Google annulée.'
        : "Google n'a pas renvoyé de jeton.",
    );
  }

  if (!nonceAttendu) {
    // Le dépôt a disparu : onglet rouvert, stockage vidé, ou aller-retour
    // déclenché depuis une autre page que la nôtre.
    throw new Error('Session expirée. Relancez la connexion depuis le formulaire.');
  }

  try {
    const charge = decoderChargeUtile(jeton.split('.')[1]);
    if (charge.nonce !== nonceAttendu) {
      throw new Error('Le jeton reçu ne correspond pas à cette tentative de connexion.');
    }
  } catch (cause) {
    if (cause instanceof Error && cause.message.startsWith('Le jeton')) throw cause;
    throw new Error('Jeton Google illisible.');
  }

  return jeton;
}
