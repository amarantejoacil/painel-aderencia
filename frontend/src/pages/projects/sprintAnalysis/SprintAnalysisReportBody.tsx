import { Fragment, useMemo, useState, type ReactNode } from 'react'
import type { SprintAnalysis } from '@/lib/api'
import { formatDate, formatDateTime, formatPercent } from '@/lib/format'
import {
  DELIVERY_STAGE_LABEL,
  normalizeSprintAnalysisResult,
  PRIORITY_LABEL,
  type NormalizedSprintAnalysisResult,
} from '@/lib/sprintAnalysisResult'
import { Table, Td, Th } from '@/components/ui/table'
import { EvidenceLinks } from '@/pages/projects/sprintAnalysis/EvidenceLinks'

const STATUS_LABEL: Record<string, string> = {
  planned: 'Planejada',
  active: 'Em andamento',
  closed: 'Encerrada',
}

export type ViewMode = 'executive' | 'detailed'

function ReportSection({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <section className="border-b border-line pb-10 last:border-b-0">
      <h3 className="text-lg font-semibold tracking-tight">{title}</h3>
      {subtitle ? <p className="mt-1 max-w-3xl text-sm text-muted">{subtitle}</p> : null}
      <div className="mt-4">{children}</div>
    </section>
  )
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-line bg-white px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {hint ? <p className="mt-2 text-xs leading-snug text-muted">{hint}</p> : null}
    </div>
  )
}

function stageTone(stage: string): string {
  switch (stage) {
    case 'validated':
    case 'completed':
      return 'bg-emerald-50 text-emerald-900'
    case 'in_progress':
    case 'started':
      return 'bg-sky-50 text-sky-900'
    case 'planned':
      return 'bg-slate-100 text-slate-800'
    default:
      return 'bg-amber-50 text-amber-950'
  }
}

function priorityTone(priority: string): string {
  if (priority === 'alta') return 'border-red-200 bg-red-50 text-red-950'
  if (priority === 'baixa') return 'border-line bg-slate-50 text-slate-800'
  return 'border-amber-200 bg-amber-50 text-amber-950'
}

export function SprintAnalysisReportBody({
  data,
  viewMode,
  printMode = false,
}: {
  data: SprintAnalysis
  viewMode: ViewMode
  printMode?: boolean
}) {
  const pack = data.pack
  const indicators = pack?.consolidated
  const criteria = pack?.criteria ?? {}
  const normalized = useMemo(
    () => normalizeSprintAnalysisResult(data.result, pack),
    [data.result, pack],
  )
  const urls = useMemo(() => {
    const map = new Map<number, string>()
    for (const item of data.evidence ?? pack?.evidence_index ?? []) {
      if (item.azure_url) map.set(item.work_item_id, item.azure_url)
    }
    for (const sprint of pack?.sprints ?? []) {
      for (const story of sprint.stories ?? []) {
        if (story.azure_url) map.set(story.work_item_id, story.azure_url)
      }
    }
    return map
  }, [data.evidence, pack])

  const [openCollab, setOpenCollab] = useState<string | null>(null)
  const [openStoryDetail, setOpenStoryDetail] = useState<number | null>(null)

  if (!pack || !normalized) return null

  const num = (value: number | null | undefined) => (value == null ? '—' : String(value))
  const collaborators = pack.collaborators ?? []
  const involvedCount = collaborators.filter((row) => row.name !== 'Sem responsável').length
  const highlightByName = new Map(normalized.team_highlights.map((row) => [row.name, row]))

  const detailed = viewMode === 'detailed' || printMode

  const detailedIndicatorsBlock =
    indicators && detailed ? (
      <>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Kpi label="Criadas no período" value={num(indicators.stories_created)} hint={criteria.stories_created} />
          <Kpi label="Pendentes" value={num(indicators.stories_pending)} hint={criteria.stories_pending} />
          <Kpi label="Reabertas" value={num(indicators.stories_reopened)} hint={criteria.stories_reopened} />
          <Kpi
            label="Sem movimentação"
            value={num(indicators.stories_without_movement)}
            hint={criteria.stories_without_movement}
          />
          <Kpi label="Tasks vinculadas" value={num(indicators.tasks_total)} />
          <Kpi
            label="Conclusão"
            value={
              indicators.completion_percent != null
                ? `${formatPercent(Number(indicators.completion_percent))} (${indicators.completion_numerator}/${indicators.completion_denominator})`
                : '—'
            }
            hint={criteria.completion_percent}
          />
        </div>
        <p className="mt-4 text-xs text-muted">{criteria.cut}</p>
        {(pack.sprints ?? []).length > 1 ? (
          <div className="mt-4 overflow-x-auto">
            <Table>
              <thead>
                <tr>
                  <Th>Sprint</Th>
                  <Th>Previstas</Th>
                  <Th>Concluídas</Th>
                  <Th>Pendentes</Th>
                  <Th>Conclusão</Th>
                </tr>
              </thead>
              <tbody>
                {(pack.sprints ?? []).map((sprint) => (
                  <tr key={sprint.sprint_key}>
                    <Td>{sprint.name}</Td>
                    <Td>{num(sprint.indicators.stories_total)}</Td>
                    <Td>{num(sprint.indicators.stories_completed)}</Td>
                    <Td>{num(sprint.indicators.stories_pending)}</Td>
                    <Td>
                      {sprint.indicators.completion_percent != null
                        ? formatPercent(Number(sprint.indicators.completion_percent))
                        : '—'}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        ) : null}
      </>
    ) : null

  return (
    <div className={`mx-auto w-full space-y-10 ${printMode ? 'max-w-none sprint-analysis-print' : 'max-w-6xl'}`}>
      <header className="border-b border-line pb-8">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">Iniciativa</p>
        <h1 className="mt-1 text-2xl font-semibold">{data.scope_label}</h1>
        <p className="mt-1 text-sm text-muted">
          {data.team_project}
          {data.area_path ? ` · ${data.area_path}` : ''}
        </p>
        <ul className="mt-4 space-y-2 text-sm">
          {(pack.sprints ?? []).map((sprint) => (
            <li key={sprint.sprint_key} className="flex flex-wrap gap-x-2 gap-y-1">
              <span className="font-medium">{sprint.name}</span>
              <span className="text-muted">
                {formatDate(sprint.start_date)} — {formatDate(sprint.finish_date)}
              </span>
              <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-800">
                {STATUS_LABEL[sprint.status] ?? sprint.status}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-muted">
          {data.generated_at ? `Relatório gerado em ${formatDateTime(data.generated_at)}` : 'Geração em andamento'}
          {data.model ? ` · Modelo ${data.model}` : ''}
          {normalized.legacy_derived ? ' · Estrutura derivada de relatório anterior' : ''}
        </p>
      </header>

      <ReportSection title="Visão geral do projeto">
        {normalized.executive_summary.split(/\n\n+/).map((paragraph, index) => (
          <p key={index} className="text-sm leading-relaxed text-foreground last:mb-0 mb-4">
            {paragraph}
          </p>
        ))}
      </ReportSection>

      {indicators ? (
        <ReportSection
          title="Indicadores principais"
          subtitle="Totais consolidados entre as Sprints selecionadas, conforme regras do painel."
        >
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi
              label="Histórias previstas na Sprint"
              value={num(indicators.stories_total)}
              hint={criteria.stories_total}
            />
            <Kpi label="Histórias concluídas" value={num(indicators.stories_completed)} hint={criteria.stories_completed} />
            <Kpi
              label="Histórias em andamento"
              value={num(indicators.stories_in_progress)}
              hint={criteria.stories_in_progress}
            />
            <Kpi
              label="Colaboradores envolvidos"
              value={String(involvedCount)}
              hint="Responsáveis distintos nas histórias analisadas (exceto itens sem responsável)."
            />
          </div>
          {detailed ? (
            printMode ? (
              <div className="mt-6">
                <h4 className="text-sm font-semibold">Indicadores detalhados</h4>
                {detailedIndicatorsBlock}
              </div>
            ) : (
              <details className="mt-6 rounded-lg border border-line bg-slate-50/50 px-4 py-3">
                <summary className="cursor-pointer text-sm font-medium">Indicadores detalhados</summary>
                {detailedIndicatorsBlock}
              </details>
            )
          ) : null}
        </ReportSection>
      ) : null}

      {normalized.work_fronts.length > 0 ? (
        <ReportSection
          title="O que está sendo desenvolvido"
          subtitle="Agrupamento por funcionalidade ou objetivo de negócio, com base nas histórias analisadas."
        >
          <ul className="space-y-5">
            {normalized.work_fronts.map((front) => (
              <li key={front.name} className="rounded-lg border border-line bg-white p-4">
                <h4 className="font-semibold">{front.name}</h4>
                {front.summary ? <p className="mt-2 text-sm leading-relaxed">{front.summary}</p> : null}
                <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="text-xs uppercase text-muted">Benefício esperado</dt>
                    <dd className="mt-0.5">{front.expected_benefit || '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-muted">Situação</dt>
                    <dd className="mt-0.5">{front.situation || '—'}</dd>
                  </div>
                </dl>
                <EvidenceLinks ids={front.story_ids} urls={urls} />
              </li>
            ))}
          </ul>
        </ReportSection>
      ) : null}

      {normalized.deliveries.length > 0 ? (
        <ReportSection title="Entregas e evolução">
          <ul className="space-y-4">
            {normalized.deliveries.map((item, index) => (
              <li key={`${item.title}-${index}`} className="border-l-2 border-accent/30 pl-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{item.title}</span>
                  <span className={`rounded px-2 py-0.5 text-xs font-medium ${stageTone(item.stage)}`}>
                    {DELIVERY_STAGE_LABEL[item.stage] ?? item.stage}
                  </span>
                </div>
                {item.narrative ? <p className="mt-2 text-sm leading-relaxed">{item.narrative}</p> : null}
                {item.relevance ? <p className="mt-1 text-sm text-muted">{item.relevance}</p> : null}
                <EvidenceLinks ids={item.story_ids} urls={urls} />
              </li>
            ))}
          </ul>
        </ReportSection>
      ) : null}

      {detailed ? (
        <ReportSection title="Equipe e distribuição das atividades" subtitle={criteria.collaborators}>
          <div className="overflow-x-auto">
            <Table>
              <thead>
                <tr>
                  <Th>Colaborador</Th>
                  <Th>Principal frente</Th>
                  <Th>Histórias</Th>
                  <Th>Tasks</Th>
                  <Th>Concluídos</Th>
                  <Th>Em andamento</Th>
                  <Th>Pendentes</Th>
                  <Th className="print:hidden" />
                </tr>
              </thead>
              <tbody>
                {collaborators.length === 0 ? (
                  <tr>
                    <Td colSpan={8} className="text-center text-muted">
                      Nenhum responsável identificado.
                    </Td>
                  </tr>
                ) : (
                  collaborators.map((row) => {
                    const highlight = highlightByName.get(row.name)
                    return (
                      <Fragment key={row.name}>
                        <tr>
                          <Td>{row.name}</Td>
                          <Td className="max-w-[200px] text-sm">{highlight?.primary_front || '—'}</Td>
                          <Td>{row.stories}</Td>
                          <Td>{row.tasks}</Td>
                          <Td>{row.completed}</Td>
                          <Td>{row.in_progress}</Td>
                          <Td>{row.pending}</Td>
                          <Td className="print:hidden">
                            <button
                              type="button"
                              className="text-sm text-accent hover:underline"
                              onClick={() => setOpenCollab(openCollab === row.name ? null : row.name)}
                            >
                              {openCollab === row.name ? 'Recolher' : 'Ver itens'}
                            </button>
                          </Td>
                        </tr>
                        {highlight?.activity_summary ? (
                          <tr>
                            <Td colSpan={8} className="bg-slate-50/80 text-sm text-muted">
                              {highlight.activity_summary}
                            </Td>
                          </tr>
                        ) : null}
                        {openCollab === row.name ? (
                          <tr>
                            <Td colSpan={8}>
                              <ul className="space-y-1 text-sm">
                                {row.items.map((item) => (
                                  <li key={`${item.kind}-${item.work_item_id}-${item.sprint_name}`}>
                                    <span className="text-muted">{item.kind === 'task' ? 'Task' : 'História'}</span>{' '}
                                    <a
                                      href={item.azure_url}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="text-accent hover:underline"
                                    >
                                      #{item.work_item_id}
                                    </a>{' '}
                                    {item.title}
                                    <span className="text-muted"> · {item.bucket}</span>
                                  </li>
                                ))}
                              </ul>
                            </Td>
                          </tr>
                        ) : null}
                      </Fragment>
                    )
                  })
                )}
              </tbody>
            </Table>
          </div>
        </ReportSection>
      ) : null}

      <ReportSection title="Riscos e pontos de atenção">
        <RiskGroup
          title="Impedimentos confirmados"
          emptyNote={normalized.impediments_note}
          items={normalized.risks.confirmed_impediments}
          urls={urls}
          explicit={(pack.explicit_impediments ?? []).map((item) => item)}
        />
        <RiskGroup
          title="Desafios registrados"
          items={normalized.risks.registered_challenges}
          urls={urls}
        />
        <RiskGroup title="Alertas e riscos identificados" items={normalized.risks.alerts} urls={urls} />
      </ReportSection>

      {normalized.management_actions.length > 0 ? (
        <ReportSection title="Ações recomendadas para a gestão">
          <p className="mb-4 text-xs text-muted">Sugestões para apoiar a decisão; não representam decisões já tomadas.</p>
          <ul className="space-y-3">
            {normalized.management_actions.map((action, index) => (
              <li
                key={`${action.action}-${index}`}
                className={`rounded-lg border px-4 py-3 ${priorityTone(action.priority)}`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold">{action.action}</span>
                  <span className="rounded bg-white/60 px-1.5 py-0.5 text-[11px] font-medium uppercase">
                    {PRIORITY_LABEL[action.priority]}
                  </span>
                </div>
                {action.reason ? <p className="mt-1 text-sm">{action.reason}</p> : null}
                {action.responsible ? (
                  <p className="mt-1 text-xs">Responsável sugerido: {action.responsible}</p>
                ) : null}
                <EvidenceLinks ids={action.evidence_ids} urls={urls} />
              </li>
            ))}
          </ul>
        </ReportSection>
      ) : null}

      {detailed && pack.multiple_sprints && (normalized.comparison_narrative || normalized.timeline.length) ? (
        <ReportSection title="Comparativo entre Sprints">
          {normalized.comparison_narrative ? (
            <p className="mb-4 text-sm leading-relaxed">{normalized.comparison_narrative}</p>
          ) : null}
          {normalized.timeline.length > 0 ? (
            <>
              <h4 className="mb-2 text-sm font-semibold">Linha do tempo</h4>
              <MultiList items={normalized.timeline} urls={urls} />
            </>
          ) : null}
          {normalized.changes_between_sprints.length > 0 ? (
            <>
              <h4 className="mb-2 mt-4 text-sm font-semibold">Mudanças entre as Sprints</h4>
              <MultiList items={normalized.changes_between_sprints} urls={urls} />
            </>
          ) : null}
        </ReportSection>
      ) : null}

      <details className="rounded-lg border border-line px-4 py-3 print:open print:border-0" open={printMode}>
        <summary className="cursor-pointer font-semibold print:cursor-default">
          Histórias e evidências analisadas
        </summary>
        <div className="mt-4 overflow-x-auto">
          <Table>
            <thead>
              <tr>
                <Th>ID</Th>
                <Th>Título</Th>
                <Th>Responsável</Th>
                <Th>Estado</Th>
                <Th>Feature</Th>
                <Th>Sprint</Th>
                {detailed ? <Th className="print:hidden">Detalhe</Th> : null}
              </tr>
            </thead>
            <tbody>
              {(pack.sprints ?? []).flatMap((sprint) =>
                (sprint.stories ?? []).map((story) => (
                  <Fragment key={`${sprint.sprint_key}-${story.work_item_id}`}>
                    <tr>
                      <Td>
                        <a href={story.azure_url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                          #{story.work_item_id}
                        </a>
                      </Td>
                      <Td className="max-w-md">{story.title}</Td>
                      <Td>{story.assignee_at_cut || '—'}</Td>
                      <Td>{story.state_at_cut || '—'}</Td>
                      <Td>{story.feature?.title || '—'}</Td>
                      <Td>{sprint.name}</Td>
                      {detailed ? (
                        <Td className="print:hidden">
                          <button
                            type="button"
                            className="text-xs text-accent hover:underline"
                            onClick={() =>
                              setOpenStoryDetail(
                                openStoryDetail === story.work_item_id ? null : story.work_item_id,
                              )
                            }
                          >
                            {openStoryDetail === story.work_item_id ? 'Ocultar' : 'Comentários'}
                          </button>
                        </Td>
                      ) : null}
                    </tr>
                    {detailed && openStoryDetail === story.work_item_id ? (
                      <tr>
                        <Td colSpan={7} className="bg-slate-50 text-sm">
                          {(story.movements ?? []).length > 0 ? (
                            <p className="text-muted">Movimentações: {(story.movements ?? []).join(' · ')}</p>
                          ) : null}
                          {'comments' in story && Array.isArray(story.comments) && story.comments.length > 0 ? (
                            <ul className="mt-2 space-y-1">
                              {(story.comments as Array<{ author?: string; text?: string }>).map((comment, ci) => (
                                <li key={ci}>
                                  {comment.author ? `${comment.author}: ` : null}
                                  {comment.text}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="mt-2 text-muted">Sem comentários disponíveis no recorte.</p>
                          )}
                          {'tasks' in story && Array.isArray(story.tasks) && story.tasks.length > 0 ? (
                            <ul className="mt-2 space-y-1 text-muted">
                              {(story.tasks as Array<{ work_item_id: number; title?: string; state?: string }>).map(
                                (task) => (
                                  <li key={task.work_item_id}>
                                    Task #{task.work_item_id} · {task.title} · {task.state}
                                  </li>
                                ),
                              )}
                            </ul>
                          ) : null}
                        </Td>
                      </tr>
                    ) : null}
                  </Fragment>
                )),
              )}
            </tbody>
          </Table>
        </div>
      </details>

      {detailed && (pack.limitations ?? []).length > 0 ? (
        <section className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          <p className="font-medium">Limitações da análise</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {pack.limitations?.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {printMode ? (
        <footer className="border-t border-line pt-6 text-xs text-muted">
          Fontes: Azure DevOps (work items, revisões e registros citados) e interpretação por modelo de IA configurado
          no painel. Evidências completas no anexo de histórias.
        </footer>
      ) : null}
    </div>
  )
}

function MultiList({
  items,
  urls,
}: {
  items: { kind: string; text: string; evidence_ids: number[] }[]
  urls: Map<number, string>
}) {
  return (
    <ul className="space-y-2">
      {items.map((item, index) => (
        <li key={`${item.text}-${index}`} className="text-sm leading-relaxed">
          {item.text}
          <EvidenceLinks ids={item.evidence_ids} urls={urls} />
        </li>
      ))}
    </ul>
  )
}

function RiskGroup({
  title,
  items,
  urls,
  emptyNote,
  explicit,
}: {
  title: string
  items: NormalizedSprintAnalysisResult['risks']['alerts']
  urls: Map<number, string>
  emptyNote?: string | null
  explicit?: Array<{ work_item_id: number; description: string; azure_url: string; assignee?: string | null }>
}) {
  return (
    <div className="mb-6 last:mb-0">
      <h4 className="text-sm font-semibold">{title}</h4>
      {emptyNote && items.length === 0 && title.includes('Impedimentos') ? (
        <p className="mt-2 text-sm text-muted">{emptyNote}</p>
      ) : null}
      {items.length > 0 ? (
        <ul className="mt-3 space-y-3">
          {items.map((item, index) => (
            <li key={`${item.description}-${index}`} className="rounded border border-line bg-white p-3 text-sm">
              <p>{item.description}</p>
              <p className="mt-1 text-muted">
                <span className="font-medium text-foreground">Impacto:</span> {item.impact}
              </p>
              <p className="mt-1 text-muted">
                <span className="font-medium text-foreground">Situação:</span> {item.known_status}
              </p>
              {item.recommended_action ? (
                <p className="mt-1 text-muted">
                  <span className="font-medium text-foreground">Ação sugerida:</span> {item.recommended_action}
                </p>
              ) : null}
              <EvidenceLinks ids={item.evidence_ids} urls={urls} />
            </li>
          ))}
        </ul>
      ) : null}
      {explicit && explicit.length > 0 ? (
        <ul className="mt-3 space-y-1 text-sm text-muted">
          {explicit.map((item) => (
            <li key={item.work_item_id}>
              <a href={item.azure_url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                #{item.work_item_id}
              </a>{' '}
              {item.description}
              {item.assignee ? ` · ${item.assignee}` : ''}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
