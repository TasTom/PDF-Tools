import type { Metadata } from 'next';

import PdfToolPage from '@/components/PdfToolPage';
import { toolMetadata } from '@/lib/metadata';

export const metadata: Metadata = toolMetadata('protect');

export default function ProtectPage() {
  return <PdfToolPage slug="protect" />;
}
