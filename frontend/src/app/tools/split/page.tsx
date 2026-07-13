import PdfToolPage from '@/components/PdfToolPage';

export default function SplitPage() {
  return (
    <PdfToolPage
      title="Découper PDF"
      description="Extraire des pages spécifiques d'un PDF. Entrez les numéros de pages (ex: 1,3,5-8) ou laissez vide pour toutes les pages."
      icon="✂️"
      endpoint="/api/pdf/split"
      accept=".pdf"
      params={[
        { name: 'pages', label: 'Pages à extraire (ex: 1,3,5-8)', type: 'text', default: '' },
      ]}
    />
  );
}
