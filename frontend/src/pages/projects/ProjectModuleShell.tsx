import type { ReactNode } from 'react'
import { Card } from '@/components/ui/card'

export function ProjectModuleShell({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children?: ReactNode
}) {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">
          Acompanhamento de Projetos
        </p>
        <h2 className="text-2xl font-semibold">{title}</h2>
        <p className="mt-1 max-w-3xl text-sm text-muted">{description}</p>
      </div>
      {children ?? (
        <Card className="p-5">
          <p className="text-sm text-muted">
            A consulta ao Azure DevOps desta tela ainda não está ligada. Projetos, Sprints e histórias
            reais entram na etapa de integração, sem números simulados.
          </p>
        </Card>
      )}
    </div>
  )
}
