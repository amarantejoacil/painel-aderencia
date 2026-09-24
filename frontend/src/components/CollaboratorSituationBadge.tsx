import { Badge } from '@/components/ui/badge'
import type { Collaborator } from '@/lib/api'

export function CollaboratorSituationBadge({ collaborator }: { collaborator: Collaborator }) {
  if (collaborator.end_date) {
    return (
      <Badge className="bg-red-50 font-medium text-red-800 ring-1 ring-inset ring-red-200">Desligado</Badge>
    )
  }
  if (collaborator.active) {
    return <Badge className="bg-emerald-50 text-emerald-800">Ativo</Badge>
  }
  return <Badge className="bg-slate-100 text-slate-600">Inativo</Badge>
}
