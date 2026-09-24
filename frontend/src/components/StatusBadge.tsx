import { Badge } from '@/components/ui/badge'
import { collaboratorDaySituationLabel } from '@/lib/format'

const STYLES: Record<string, string> = {
  regular: 'bg-emerald-50 text-emerald-800',
  incomplete: 'bg-amber-50 text-amber-800',
  missing: 'bg-red-50 text-red-800',
  excess: 'bg-orange-50 text-orange-800',
  not_required: 'bg-slate-100 text-slate-600',
  justified_absence: 'bg-blue-50 text-blue-800',
  dismissed: 'bg-red-50 text-red-800 ring-1 ring-inset ring-red-200',
}

export function StatusBadge({
  status,
  absenceType,
  dayDate,
  endDate,
}: {
  status: string
  absenceType?: string | null
  dayDate?: string
  endDate?: string | null
}) {
  const label = collaboratorDaySituationLabel(status, dayDate ?? '', endDate, absenceType)
  const styleKey = label === 'Desligado' ? 'dismissed' : status
  return (
    <Badge className={STYLES[styleKey] ?? 'bg-slate-100 text-slate-700'}>
      {label}
    </Badge>
  )
}
