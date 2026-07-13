import PdfToolPage from '@/components/PdfToolPage';

export default function RotatePage() {
  return (
    <PdfToolPage
      title="Pivoter PDF"
      description="Faire pivoter les pages d'un PDF de 90°, 180° ou 270°."
      icon="🔄"
      endpoint="/api/pdf/rotate"
      accept=".pdf"
      params={[
        { name: 'angle', label: 'Angle de rotation', type: 'select', options: ['90', '180', '270'], default: '90' },
        { name: 'pages', label: 'Pages (vide = toutes)', type: 'text', default: '' },
      ]}
    />
  );
}
