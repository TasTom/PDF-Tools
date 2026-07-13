import PdfToolPage from '@/components/PdfToolPage';

export default function CropPage() {
  return (
    <PdfToolPage
      title="Recadrer PDF"
      description="Recadrer les pages d'un PDF à des dimensions personnalisées (en points, 72 DPI). Format A4 = 595×842 points."
      icon="✂️"
      endpoint="/api/pdf/crop"
      accept=".pdf"
      params={[
        { name: 'x', label: 'Position X (points)', type: 'text', default: '0' },
        { name: 'y', label: 'Position Y (points)', type: 'text', default: '0' },
        { name: 'w', label: 'Largeur (points)', type: 'text', default: '595' },
        { name: 'h', label: 'Hauteur (points)', type: 'text', default: '842' },
      ]}
    />
  );
}
