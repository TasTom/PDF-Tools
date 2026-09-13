'use client';

import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';

/**
 * Session utilisateur.
 *
 * Le jeton est conservé dans `localStorage` : c'est ce qui survit à un
 * rechargement de page, et donc à une navigation entre deux outils. Il n'est
 * PAS dans un cookie, ce qui évite d'avoir à gérer le CSRF pour une API qui
 * n'accepte que l'en-tête `Authorization`.
 */

export type User = {
  id: number;
  email: string;
  username: string;
  is_active: boolean;
  auth_provider: string;
  daily_usage: number;
  daily_limit: number;
  created_at: string;
};

export type Usage = {
  daily_usage: number;
  daily_limit: number;
  remaining: number;
};

type AuthState = {
  user: User | null;
  token: string | null;
  /** Vrai tant que la session n'a pas été vérifiée au démarrage. */
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => void;
  /** Relit le profil : sert à rafraîchir le quota après une opération. */
  refresh: () => Promise<void>;
};

const CLE_JETON = 'pdf-tools-token';

const AuthContext = createContext<AuthState | null>(null);

/** Uniformise les erreurs de l'API en message affichable. */
async function lireErreur(reponse: Response): Promise<string> {
  try {
    const corps = await reponse.json();
    if (typeof corps?.detail === 'string') return corps.detail;
    // FastAPI renvoie un tableau pour les erreurs de validation.
    if (Array.isArray(corps?.detail) && corps.detail[0]?.msg) return corps.detail[0].msg;
    if (typeof corps?.error === 'string') return corps.error;
  } catch {
    // Réponse non JSON : on retombe sur un message générique.
  }
  if (reponse.status === 429) {
    return 'Trop de tentatives. Patientez une minute, puis réessayez.';
  }
  return `Le serveur a répondu ${reponse.status}.`;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Numero de session, incremente a chaque deconnexion et a chaque connexion.
  //
  // Sans lui, une requete `/api/auth/me` encore en vol au moment ou
  // l'utilisateur se deconnecte revient quelques centaines de millisecondes
  // plus tard et remet le profil en place : l'en-tete reaffiche alors le compte
  // alors que le jeton est deja efface. Le numero permet de reconnaitre une
  // reponse perimee et de la jeter.
  const session = useRef(0);

  // Au premier rendu, on valide le jeton conservé. On ne fait pas confiance au
  // contenu de `localStorage` : il peut être périmé ou modifié à la main, et
  // seul le serveur sait si la session est encore valide.
  useEffect(() => {
    const conserve = window.localStorage.getItem(CLE_JETON);
    if (!conserve) {
      setLoading(false);
      return;
    }

    const epoque = session.current;
    fetch('/api/auth/me', { headers: { Authorization: `Bearer ${conserve}` } })
      .then(async reponse => {
        if (epoque !== session.current) return;
        if (reponse.ok) {
          setUser(await reponse.json());
          setToken(conserve);
        } else {
          window.localStorage.removeItem(CLE_JETON);
        }
      })
      .catch(() => {
        // Serveur injoignable : on garde le jeton, il sera revalidé plus tard.
      })
      .finally(() => {
        if (epoque === session.current) setLoading(false);
      });
  }, []);

  const enregistrer = useCallback((jeton: string, profil: User) => {
    session.current += 1;
    window.localStorage.setItem(CLE_JETON, jeton);
    setToken(jeton);
    setUser(profil);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const reponse = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!reponse.ok) throw new Error(await lireErreur(reponse));
      const corps = await reponse.json();
      enregistrer(corps.access_token, corps.user);
    },
    [enregistrer],
  );

  const register = useCallback(
    async (email: string, username: string, password: string) => {
      const reponse = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, username, password }),
      });
      if (!reponse.ok) throw new Error(await lireErreur(reponse));
      const corps = await reponse.json();
      enregistrer(corps.access_token, corps.user);
    },
    [enregistrer],
  );

  const logout = useCallback(() => {
    session.current += 1;
    window.localStorage.removeItem(CLE_JETON);
    setToken(null);
    setUser(null);
  }, []);

  const refresh = useCallback(async () => {
    const jeton = window.localStorage.getItem(CLE_JETON);
    if (!jeton) return;
    const epoque = session.current;
    const reponse = await fetch('/api/auth/me', { headers: { Authorization: `Bearer ${jeton}` } });
    // La session a change pendant l'appel : la reponse ne vaut plus rien.
    if (epoque !== session.current) return;
    if (reponse.ok) {
      setUser(await reponse.json());
    } else if (reponse.status === 401) {
      logout();
    }
  }, [logout]);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const contexte = useContext(AuthContext);
  if (!contexte) {
    throw new Error("useAuth doit être utilisé à l'intérieur de <AuthProvider>.");
  }
  return contexte;
}

/**
 * En-têtes d'authentification pour un appel d'outil.
 *
 * Renvoie une chaîne vide si aucun jeton n'est présent : la requête partira
 * alors sans en-tête et recevra un 401, que l'appelant traduit en invitation à
 * se connecter.
 */
export function entetesAuth(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}
