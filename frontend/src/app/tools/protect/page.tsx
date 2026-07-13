import PdfToolPage from '@/components/PdfToolPage';

export default function ProtectPage() {
  return (
    <PdfToolPage
      title="Protéger PDF"
      description="Ajouter un mot de passe à votre fichier PDF pour empêcher l'accès non autorisé."
      icon="🔒"
      endpoint="/api/pdf/protect"
      accept=".pdf"
      params={[
        { name: 'password', label: 'Mot de passe', type: 'text' },
      ]}
    />
  );
}
