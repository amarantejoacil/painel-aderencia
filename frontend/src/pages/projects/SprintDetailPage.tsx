import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { Card } from '@/components/ui/card'
import { Table, Td, Th } from '@/components/ui/table'
import { ProjectModuleShell } from '@/pages/projects/ProjectModuleShell'
import { api, type ProjectSprintDetail, type ProjectScope } from '@/lib/api'
import { formatAzureState, formatDate, formatPercent } from '@/lib/format'

const STATUS_LABEL: Record<string, string> = {
  planned: 'Planejada',
  active: 'Em andamento',
  closed: 'Encerrada',
}

export function SprintDetailPage() {
  const { sprintKey } = useParams()
  const [searchParams] = useSearchParams()
  const scopeKey = searchParams.get('scope') || ''
  const [scopes, setScopes] = useState<ProjectScope[]>([])
  const [data, setData] = useState<ProjectSprintDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const areaPath = scopes.find((item) => item.key === scopeKey)?.area_path ?? undefined

  useEffect(() => {
    api.listProjectScopes().then(setScopes).catch(() => setScopes([]))
  }, [])

  useEffect(() => {
    if (!sprintKey) return
    setLoading(true)
    setError(null)
    api
      .projectSprintDetail(sprintKey, areaPath)
      .then(setData)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [sprintKey, areaPath])

  if (!sprintKey) {
    return (
      <ProjectModuleShell
        title="Detalhamento da Sprint"
        description="Abra uma Sprint pela listagem para ver o detalhamento."
      />
    )
  }

  return (
    <ProjectModuleShell
      title={data?.name ?? 'Detalhamento da Sprint'}
      description="Histórias, estados no início e no fim da Sprint, comentários e análise do período."
    >
      <div className="flex flex-wrap gap-3">
        <Link to={`/projetos/sprints?scope=${encodeURIComponent(scopeKey)}`} className="text-sm text-accent hover:underline">
          ← Voltar às Sprints
        </Link>
      </div>

      {error ? (
        <Card className="border-red-200 bg-red-50 p-4 text-sm text-red-900">{error}</Card>
      ) : null}

      {loading ? (
        <p className="text-sm text-muted">Carregando histórias e histórico…</p>
      ) : data ? (
        <>
          <Card className="grid gap-4 p-4 md:grid-cols-2 lg:grid-cols-4">
            <Info label="Projeto" value={data.team_project} />
            <Info label="Período" value={`${formatDate(data.start_date)} — ${formatDate(data.finish_date)}`} />
            <Info label="Situação" value={STATUS_LABEL[data.status] ?? data.status} />
            <Info
              label="Conclusão"
              value={
                data.metrics.completion_percent != null
                  ? `${formatPercent(data.metrics.completion_percent)} (${data.metrics.completion_numerator}/${data.metrics.completion_denominator})`
                  : '—'
              }
            />
            <Info label="Histórias" value={String(data.metrics.stories_total)} />
            <Info label="Criadas na Sprint" value={String(data.metrics.stories_created_in_sprint)} />
            <Info label="Concluídas na Sprint" value={String(data.metrics.stories_completed_in_sprint)} />
            <Info label="Pendentes" value={String(data.metrics.stories_pending)} />
          </Card>

          <Card className="overflow-x-auto p-0">
            <Table>
              <thead>
                <tr>
                  <Th>ID</Th>
                  <Th>Título</Th>
                  <Th>Responsável</Th>
                  <Th>Início Sprint</Th>
                  <Th>Corte Sprint</Th>
                  <Th>Atual</Th>
                  <Th>Azure</Th>
                </tr>
              </thead>
              <tbody>
                {data.stories.map((story) => (
                  <tr key={story.work_item_id}>
                    <Td>{story.work_item_id}</Td>
                    <Td>{story.title}</Td>
                    <Td>{story.assignee ?? '—'}</Td>
                    <Td>{formatAzureState(story.state_at_start)}</Td>
                    <Td>{formatAzureState(story.state_at_cut)}</Td>
                    <Td>{formatAzureState(story.state_current)}</Td>
                    <Td>
                      <a
                        href={story.azure_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-accent hover:underline"
                      >
                        Abrir
                      </a>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Card>

          {data.limitations.length > 0 ? (
            <Card className="border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
              <p className="font-medium">Limitações</p>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {data.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </Card>
          ) : null}
        </>
      ) : null}
    </ProjectModuleShell>
  )
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-sm text-muted">{label}</p>
      <p className="font-semibold">{value}</p>
    </div>
  )
}
