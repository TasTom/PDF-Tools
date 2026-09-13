import type { Metadata } from 'next';

import PdfToolPage from '@/components/PdfToolPage';
import { toolMetadata } from '@/lib/metadata';

export const metadata: Metadata = toolMetadata('unprotect');

export default function UnprotectPage() {
  return <PdfToolPage slug="unprotect" />;
}
