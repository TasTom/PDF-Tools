import type { Metadata } from 'next';

import PdfToolPage from '@/components/PdfToolPage';
import { toolMetadata } from '@/lib/metadata';

export const metadata: Metadata = toolMetadata('from-images');

export default function FromImagesPage() {
  return <PdfToolPage slug="from-images" />;
}
