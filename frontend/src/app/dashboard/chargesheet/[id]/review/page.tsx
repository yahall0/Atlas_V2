'use client';

import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ChevronRight } from 'lucide-react';
import DualPaneLayout from '@/components/chargesheet-review/DualPaneLayout';

export default function ChargesheetReviewPage() {
  const params = useParams();
  const csId = params.id as string;

  return (
    <div className="h-full flex flex-col">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-sm text-slate-500 mb-3 shrink-0">
        <Link
          href="/dashboard/chargesheet"
          className="hover:text-slate-800 transition-colors"
        >
          Charge Sheet
        </Link>
        <ChevronRight className="w-3.5 h-3.5" />
        <Link
          href={`/dashboard/chargesheet/${csId}`}
          className="hover:text-slate-800 transition-colors"
        >
          {csId.slice(0, 8)}
        </Link>
        <ChevronRight className="w-3.5 h-3.5" />
        <span className="font-medium text-slate-800">Gap Analysis</span>
      </div>

      {/* Dual pane layout fills remaining space */}
      <div className="flex-1 min-h-0 border rounded-lg overflow-hidden bg-white">
        <DualPaneLayout chargesheetId={csId} />
      </div>
    </div>
  );
}
