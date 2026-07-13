import PdfToolPage from '@/components/PdfToolPage';

export default function CompressPage() {
  return (
    <PdfToolPage
      title="Compresser PDF"
      description="Réduire la taille de vos fichiers PDF tout en conservant la qualité de lecture."
      icon="🗜️"
      endpoint="/api/pdf/compress"
      accept=".pdf"
      params={[
        { name: 'quality', label: 'Niveau de compression', type: 'select', options: ['low', 'medium', 'high'], default: 'medium' },
      ]}
    />
  );
}
