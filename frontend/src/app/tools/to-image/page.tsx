import PdfToolPage from '@/components/PdfToolPage';

export default function ToImagePage() {
  return (
    <PdfToolPage
      title="PDF → Image"
      description="Convertir les pages d'un fichier PDF en images PNG ou JPG haute qualité."
      icon="🖼️"
      endpoint="/api/pdf/to-image"
      accept=".pdf"
      params={[
        { name: 'format', label: 'Format de sortie', type: 'select', options: ['png', 'jpeg'], default: 'png' },
        { name: 'dpi', label: 'Résolution (DPI)', type: 'select', options: ['72', '150', '300'], default: '150' },
      ]}
    />
  );
}
