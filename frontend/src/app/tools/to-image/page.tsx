import type { Metadata } from 'next';

import PdfToolPage from '@/components/PdfToolPage';
import { toolMetadata } from '@/lib/metadata';

export const metadata: Metadata = toolMetadata('to-image');

export default function ToImagePage() {
  return <PdfToolPage slug="to-image" />;
}
