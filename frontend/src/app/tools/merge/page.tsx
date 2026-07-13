import PdfToolPage from '@/components/PdfToolPage';

export default function MergePage() {
  return (
    <PdfToolPage
      title="Fusionner PDF"
      description="Combiner plusieurs fichiers PDF en un seul document. Glissez-déposez vos fichiers dans l'ordre souhaité."
      icon="📄"
      endpoint="/api/pdf/merge"
      accept=".pdf"
      multiple={true}
    />
  );
}
