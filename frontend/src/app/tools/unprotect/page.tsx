import PdfToolPage from '@/components/PdfToolPage';

export default function UnprotectPage() {
  return (
    <PdfToolPage
      title="Déverrouiller PDF"
      description="Supprimer la protection mot de passe d'un fichier PDF."
      icon="🔓"
      endpoint="/api/pdf/unprotect"
      accept=".pdf"
      params={[
        { name: 'password', label: 'Mot de passe actuel', type: 'text' },
      ]}
    />
  );
}
