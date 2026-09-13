'use client';

import { useCallback, useState } from 'react';

import Diagram from '@/components/Diagram';
import { getTool } from '@/lib/tools';

/** Taille lisible : on reste en Ko tant que le fichier est petit. */
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} Ko`;
  return `${(bytes / 1024 / 1024).toFixed(1)} Mo`;
}

/**
 * Message d'erreur affichable.
 *
 * FastAPI renvoie `detail`, sauf le limiteur de debit qui renvoie `error` en
 * anglais : on le traduit ici, sinon l'utilisateur recevrait une phrase qu'il
 * ne peut pas comprendre au moment precis ou il a besoin d'aide.
 */
function readError(status: number, payload: unknown): string {
  const rateLimited =
    'Trop de demandes en peu de temps. Patientez une minute, puis réessayez.';

  if (typeof payload === 'object' && payload !== null) {
    const body = payload as Record<string, unknown>;
    if (typeof body.detail === 'string') return body.detail;
    if (typeof body.error === 'string') return status === 429 ? rateLimited : body.error;
  }

  if (status === 429) return rateLimited;

  // Reponse non JSON : c'est le proxy de l'hebergeur qui a echoue, pas l'API.
  // Mesure : un envoi de 13,9 Mo passe en 2,3 s en direct contre le service,
  // mais echoue en 500 apres 30 s a travers le proxy. Le plafond reel d'envoi
  // est donc celui de l'hebergeur, pas les 50 Mo annonces par le service.
  if (status >= 500) {
    return 'Le transfert a échoué avant d’atteindre le service. Si le fichier est volumineux, essayez d’abord de le compresser ou de le découper.';
  }

  return `Le serveur a répondu ${status}.`;
}

type Result = { url: string; name: string; archive: boolean };
type Phase = 'idle' | 'busy' | 'done';

export default function PdfToolPage({ slug }: { slug: string }) {
  const tool = getTool(slug);

  const [files, setFiles] = useState<File[]>([]);
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState('');
  const [result, setResult] = useState<Result | null>(null);
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries((tool.params ?? []).map(p => [p.name, p.defaultValue ?? ''])),
  );

  const selectFiles = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    setFiles(Array.from(event.target.files ?? []));
    setError('');
    setResult(current => {
      if (current) URL.revokeObjectURL(current.url);
      return null;
    });
    setPhase('idle');
  }, []);

  const run = async () => {
    if (files.length === 0) return;

    setPhase('busy');
    setError('');
    setResult(current => {
      if (current) URL.revokeObjectURL(current.url);
      return null;
    });

    // Les endpoints qui acceptent plusieurs fichiers attendent `files`, les
    // autres `file`. Envoyer les deux ferait transiter chaque fichier en double.
    const body = new FormData();
    if (tool.multiple) {
      files.forEach(file => body.append('files', file));
    } else {
      body.append('file', files[0]);
    }
    Object.entries(values).forEach(([name, value]) => {
      if (value !== '') body.append(name, value);
    });

    try {
      const response = await fetch(tool.endpoint, { method: 'POST', body });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(readError(response.status, payload));
      }

      const blob = await response.blob();
      // Une archive ne peut pas s'afficher dans un aperçu intégré.
      const archive = blob.type === 'application/zip';
      const disposition = response.headers.get('Content-Disposition') ?? '';
      const named = disposition.match(/filename="?([^";]+)"?/);

      setResult({
        url: URL.createObjectURL(blob),
        name: named ? named[1] : archive ? 'pages.zip' : 'resultat.pdf',
        archive,
      });
      setPhase('done');
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Le traitement a échoué. Réessayez dans un instant.',
      );
      setPhase('idle');
    }
  };

  const totalBytes = files.reduce((sum, file) => sum + file.size, 0);

  return (
    <div className="mx-auto max-w-6xl px-5">
      <div className="flex items-start gap-5 pt-12 pb-10">
        <Diagram slug={slug} className="mt-2 hidden sm:block" />
        <div className="min-w-0">
          <h1 className="text-[28px] font-semibold leading-[1.2] tracking-[-0.01em] sm:text-[34px]">
            {tool.title}
          </h1>
          <p className="mt-2 max-w-measure text-ink-soft">{tool.blurb}</p>
        </div>
      </div>

      <div className="grid gap-10 lg:grid-cols-2">
        {/* Colonne des réglages */}
        <div className="space-y-6">
          <div>
            {/* Simple intitule visuel : un seul `label` doit pointer sur le
                champ, sinon le nom annonce aux lecteurs d'ecran est la
                concatenation des deux. */}
            <span className="block text-sm text-ink-soft">
              {tool.multiple ? 'Fichiers à traiter' : 'Fichier à traiter'}
            </span>

            {/* Le champ natif est masque : le navigateur y ecrit « Choose File »
                et « No file chosen », dans SA langue et non dans celle du site.
                On garde l'element (donc l'accessibilite et le clavier) et on
                dessine le bouton nous-memes, en francais. */}
            <input
              id="fichiers"
              type="file"
              accept={tool.accept}
              multiple={tool.multiple}
              onChange={selectFiles}
              className="peer sr-only"
            />
            <label
              htmlFor="fichiers"
              className="mt-1.5 inline-block cursor-pointer rounded-sm border border-ink bg-ink px-4 py-2 text-sm font-medium text-paper peer-focus-visible:ring-2 peer-focus-visible:ring-accent peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-paper hover:border-accent hover:bg-accent"
            >
              {tool.multiple ? 'Choisir des fichiers' : 'Choisir un fichier'}
            </label>

            {files.length > 0 && (
              <ul className="mt-3 space-y-1">
                {(files.length > 4 ? files.slice(0, 4) : files).map(file => (
                  <li
                    key={`${file.name}-${file.size}`}
                    className="flex items-baseline justify-between gap-4"
                  >
                    <span className="truncate font-mono text-xs text-ink">
                      {file.name}
                    </span>
                    <span className="shrink-0 font-mono text-xs text-ink-faint">
                      {formatSize(file.size)}
                    </span>
                  </li>
                ))}
                {files.length > 4 && (
                  <li className="text-xs text-ink-soft">
                    et {files.length - 4} autre{files.length - 4 > 1 ? 's' : ''}
                  </li>
                )}
                {files.length > 1 && (
                  <li className="pt-0.5 text-xs text-ink-soft">
                    Total : {formatSize(totalBytes)}
                  </li>
                )}
              </ul>
            )}
          </div>

          {tool.params?.map(param => (
            <div key={param.name}>
              <label htmlFor={param.name} className="block text-sm text-ink-soft">
                {param.label}
              </label>

              {param.type === 'select' ? (
                <select
                  id={param.name}
                  value={values[param.name] ?? ''}
                  aria-describedby={param.hint ? `${param.name}-aide` : undefined}
                  onChange={event =>
                    setValues({ ...values, [param.name]: event.target.value })
                  }
                  className="mt-1.5 w-full rounded-sm border border-rule bg-white px-3 py-2.5 text-ink"
                >
                  {param.options?.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id={param.name}
                  type="text"
                  value={values[param.name] ?? ''}
                  aria-describedby={param.hint ? `${param.name}-aide` : undefined}
                  onChange={event =>
                    setValues({ ...values, [param.name]: event.target.value })
                  }
                  className="mt-1.5 w-full rounded-sm border border-rule bg-white px-3 py-2.5 text-ink"
                />
              )}

              {param.hint && (
                <p id={`${param.name}-aide`} className="mt-1.5 text-xs text-ink-faint">
                  {param.hint}
                </p>
              )}
            </div>
          ))}

          <button
            type="button"
            onClick={run}
            disabled={files.length === 0 || phase === 'busy'}
            className="w-full rounded-sm bg-ink px-5 py-3 font-medium text-paper disabled:cursor-not-allowed disabled:bg-rule disabled:text-ink-faint"
          >
            {phase === 'busy' ? 'Traitement en cours…' : tool.action}
          </button>

          {error && (
            <p
              role="alert"
              className="rounded-sm border border-accent bg-accent-soft px-4 py-3 text-sm text-accent"
            >
              {error}
            </p>
          )}
        </div>

        {/* Colonne du résultat */}
        <div>
          <h2 className="mb-2 font-mono text-xs text-ink-faint">Résultat</h2>
          <div className="flex min-h-[300px] flex-col items-center justify-center rounded-sm border border-rule bg-white p-6">
            {phase === 'done' && result ? (
              <div className="flex w-full flex-col gap-5">
                {result.archive ? (
                  <div className="py-6">
                    <p className="font-medium text-ink">Archive prête</p>
                    <p className="mt-1 max-w-measure text-sm text-ink-soft">
                      {tool.archiveNote}
                    </p>
                  </div>
                ) : (
                  <iframe
                    src={result.url}
                    title="Aperçu du résultat"
                    className="h-[380px] w-full rounded-sm border border-rule"
                  />
                )}
                <button
                  type="button"
                  onClick={() => {
                    const link = document.createElement('a');
                    link.href = result.url;
                    link.download = result.name;
                    link.click();
                  }}
                  className="self-start rounded-sm bg-ink px-5 py-2.5 font-medium text-paper hover:bg-accent"
                >
                  Télécharger {result.name}
                </button>
              </div>
            ) : phase === 'busy' ? (
              <div className="w-full max-w-xs text-center">
                <p className="text-sm text-ink-soft">Traitement en cours…</p>
                <div className="mt-3 h-0.5 w-full overflow-hidden bg-rule">
                  <div className="h-full w-1/2 animate-indeterminate bg-accent" />
                </div>
              </div>
            ) : (
              <p className="max-w-measure text-center text-sm text-ink-faint">
                Le résultat s’affichera ici une fois l’opération lancée.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
