import type { Metadata } from 'next';

import PdfToolPage from '@/components/PdfToolPage';
import { toolMetadata } from '@/lib/metadata';

export const metadata: Metadata = toolMetadata('crop');

export default function CropPage() {
  return <PdfToolPage slug="crop" />;
}
