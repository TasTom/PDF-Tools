import PdfToolPage from '@/components/PdfToolPage';

export default function WatermarkPage() {
  return (
    <PdfToolPage
      title="Filigrane PDF"
      description="Ajouter un filigrane texte diagonale sur chaque page du PDF."
      icon="💧"
      endpoint="/api/pdf/watermark"
      accept=".pdf"
      params={[
        { name: 'text', label: 'Texte du filigrane', type: 'text', default: 'CONFIDENTIEL' },
        { name: 'opacity', label: 'Opacité (0.05 - 1.0)', type: 'text', default: '0.3' },
      ]}
    />
  );
}
