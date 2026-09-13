import type { Metadata } from 'next';

import PdfToolPage from '@/components/PdfToolPage';
import { toolMetadata } from '@/lib/metadata';

export const metadata: Metadata = toolMetadata('split');

export default function SplitPage() {
  return <PdfToolPage slug="split" />;
}
