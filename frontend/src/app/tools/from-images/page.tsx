import PdfToolPage from '@/components/PdfToolPage';

export default function FromImagesPage() {
  return (
    <PdfToolPage
      title="Image → PDF"
      description="Créer un fichier PDF à partir de plusieurs images (PNG, JPG). Les images sont insérées dans l'ordre."
      icon="📋"
      endpoint="/api/pdf/from-images"
      accept="image/*"
      multiple={true}
    />
  );
}
