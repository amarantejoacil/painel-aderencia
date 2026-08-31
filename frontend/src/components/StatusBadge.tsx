import { Badge } from '@/components/ui/badge'
import { STATUS_LABEL } from '@/lib/format'

const STYLES: Record<string, string> = {
  regular: 'bg-emerald-50 text-emerald-800',
  incomplete: 'bg-amber-50 text-amber-800',
  missing: 'bg-red-50 text-red-800',
  excess: 'bg-orange-50 text-orange-800',
  not_required: 'bg-slate-100 text-slate-600',
}

export function StatusBadge({ status }: { status: string }) {
  return <Badge className={STYLES[status] ?? 'bg-slate-100 text-slate-700'}>{STATUS_LABEL[status] ?? status}</Badge>
}
