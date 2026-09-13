import type { Metadata } from 'next';

import PdfToolPage from '@/components/PdfToolPage';
import { toolMetadata } from '@/lib/metadata';

export const metadata: Metadata = toolMetadata('merge');

export default function MergePage() {
  return <PdfToolPage slug="merge" />;
}
