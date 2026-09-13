import type { Metadata } from 'next';

import PdfToolPage from '@/components/PdfToolPage';
import { toolMetadata } from '@/lib/metadata';

export const metadata: Metadata = toolMetadata('compress');

export default function CompressPage() {
  return <PdfToolPage slug="compress" />;
}
