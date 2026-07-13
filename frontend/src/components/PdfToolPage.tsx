'use client';

import { useState, useCallback } from 'react';

interface PdfToolPageProps {
  title: string;
  description: string;
  icon: string;
  endpoint: string;
  accept: string;
  multiple?: boolean;
  params?: Array<{ name: string; label: string; type: 'text' | 'number' | 'select'; options?: string[]; default?: string | number }>;
  outputType?: 'blob' | 'json';
}

export default function PdfToolPage({ title, description, icon, endpoint, accept = '.pdf', multiple = false, params = [], outputType = 'blob' }: PdfToolPageProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [resultJson, setResultJson] = useState<any>(null);
  const [paramValues, setParamValues] = useState<Record<string, string>>({});

  const handleFiles = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files));
      setError('');
      setResultUrl(null);
      setResultJson(null);
    }
  }, []);

  const process = async () => {
    if (files.length === 0) return;
    setLoading(true);
    setError('');
    setResultUrl(null);
    setResultJson(null);

    const fd = new FormData();
    files.forEach(f => fd.append('file', f));
    if (multiple) {
      files.forEach(f => fd.append('files', f));
    } else {
      fd.append('file', files[0]);
    }
    Object.entries(paramValues).forEach(([k, v]) => fd.append(k, v));

    try {
      const res = await fetch(endpoint, { method: 'POST', body: fd });
      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: 'Erreur de traitement' }));
        throw new Error(data.detail || 'Erreur de traitement');
      }
      if (outputType === 'json') {
        const data = await res.json();
        setResultJson(data);
      } else {
        const blob = await res.blob();
        if (resultUrl) URL.revokeObjectURL(resultUrl);
        setResultUrl(URL.createObjectURL(blob));
      }
    } catch (err: any) {
      setError(err.message || 'Erreur');
    } finally {
      setLoading(false);
    }
  };

  const download = () => {
    if (!resultUrl) return;
    const a = document.createElement('a');
    a.href = resultUrl;
    a.download = 'result.pdf';
    a.click();
  };

  const copyBase64 = () => {
    if (resultJson?.base64) {
      navigator.clipboard.writeText(resultJson.base64);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-10">
      <h1 className="text-3xl font-bold text-white mb-2">{icon} {title}</h1>
      <p className="text-slate-400 mb-8">{description}</p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="space-y-6">
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
            <label className="block text-sm font-medium text-slate-300 mb-2">
              {multiple ? 'Sélectionnez vos fichiers' : 'Sélectionnez votre fichier'}
            </label>
            <input
              type="file"
              accept={accept}
              multiple={multiple}
              onChange={handleFiles}
              className="w-full text-sm text-slate-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-blue-600 file:text-white file:cursor-pointer hover:file:bg-blue-700"
            />
            {files.length > 0 && (
              <p className="mt-2 text-sm text-slate-400">
                {files.length} fichier(s) sélectionné(s) — {(files.reduce((a, f) => a + f.size, 0) / 1024 / 1024).toFixed(1)} MB
              </p>
            )}
          </div>

          {params.map(p => (
            <div key={p.name}>
              <label className="block text-sm text-slate-400 mb-1">{p.label}</label>
              {p.type === 'select' ? (
                <select
                  value={paramValues[p.name] || p.default || ''}
                  onChange={e => setParamValues({ ...paramValues, [p.name]: e.target.value })}
                  className="w-full bg-slate-800 border border-slate-600 rounded-lg px-4 py-2.5 text-white"
                >
                  {p.options?.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                </select>
              ) : (
                <input
                  type={p.type}
                  value={paramValues[p.name] || p.default || ''}
                  onChange={e => setParamValues({ ...paramValues, [p.name]: e.target.value })}
                  className="w-full bg-slate-800 border border-slate-600 rounded-lg px-4 py-2.5 text-white"
                />
              )}
            </div>
          ))}

          <button
            onClick={process}
            disabled={files.length === 0 || loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-semibold py-3 rounded-xl transition"
          >
            {loading ? 'Traitement en cours...' : 'Traiter'}
          </button>
          {error && <div className="bg-red-500/10 border border-red-500/30 text-red-300 rounded-xl px-4 py-3 text-sm">{error}</div>}
        </div>

        <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 flex flex-col items-center justify-center min-h-[300px]">
          {resultUrl ? (
            <div className="flex flex-col items-center gap-4 w-full">
              <div className="rounded-xl overflow-hidden shadow-2xl w-full">
                <iframe src={resultUrl} className="w-full h-[400px] border-0" />
              </div>
              <button onClick={download} className="bg-green-600 hover:bg-green-700 text-white font-medium px-6 py-2.5 rounded-xl transition">
                Télécharger le résultat
              </button>
            </div>
          ) : resultJson ? (
            <div className="w-full">
              <p className="text-sm text-slate-400 mb-2">Taille: {resultJson.size_display}</p>
              <textarea readOnly value={resultJson.base64?.substring(0, 500) + '...'} className="w-full h-40 bg-slate-800 rounded-lg p-3 text-xs text-slate-300 font-mono" />
              <button onClick={copyBase64} className="mt-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm">
                Copier le Base64
              </button>
            </div>
          ) : (
            <div className="text-center text-slate-500">
              <div className="text-6xl mb-4">{icon}</div>
              <p>Le résultat apparaîtra ici</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
