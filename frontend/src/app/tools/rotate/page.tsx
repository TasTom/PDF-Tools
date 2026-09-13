import type { Metadata } from 'next';

import PdfToolPage from '@/components/PdfToolPage';
import { toolMetadata } from '@/lib/metadata';

export const metadata: Metadata = toolMetadata('rotate');

export default function RotatePage() {
  return <PdfToolPage slug="rotate" />;
}
