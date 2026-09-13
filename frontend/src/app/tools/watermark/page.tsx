import type { Metadata } from 'next';

import PdfToolPage from '@/components/PdfToolPage';
import { toolMetadata } from '@/lib/metadata';

export const metadata: Metadata = toolMetadata('watermark');

export default function WatermarkPage() {
  return <PdfToolPage slug="watermark" />;
}
