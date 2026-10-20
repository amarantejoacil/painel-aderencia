import type { SprintAnalysis } from '@/lib/api'

export type DeliveryStage = 'planned' | 'started' | 'in_progress' | 'completed' | 'validated'
export type ActionPriority = 'alta' | 'media' | 'baixa'
export type EvidenceKind = 'fact' | 'inference' | 'recommendation'

export type SprintAnalysisRiskItem = {
  description: string
  impact: string
  known_status: string
  recommended_action?: string | null
  evidence_ids: number[]
  kind: EvidenceKind
}

export type SprintAnalysisWorkFront = {
  name: string
  summary: string
  expected_benefit: string
  situation: string
  story_ids: number[]
}

export type SprintAnalysisDelivery = {
  title: string
  stage: DeliveryStage
  narrative: string
  relevance: string
  story_ids: number[]
}

export type SprintAnalysisTeamHighlight = {
  name: string
  primary_front: string
  activity_summary: string
  story_ids: number[]
  task_ids: number[]
}

export type SprintAnalysisManagementAction = {
  action: string
  reason: string
  priority: ActionPriority
  responsible?: string | null
  evidence_ids: number[]
}

export type SprintAnalysisMultiItem = {
  kind: EvidenceKind
  text: string
  evidence_ids: number[]
}

export type NormalizedSprintAnalysisResult = {
  schema_version: number
  legacy_derived: boolean
  executive_summary: string
  work_fronts: SprintAnalysisWorkFront[]
  deliveries: SprintAnalysisDelivery[]
  team_highlights: SprintAnalysisTeamHighlight[]
  risks: {
    confirmed_impediments: SprintAnalysisRiskItem[]
    registered_challenges: SprintAnalysisRiskItem[]
    alerts: SprintAnalysisRiskItem[]
  }
  management_actions: SprintAnalysisManagementAction[]
  comparison_narrative?: string | null
  timeline: SprintAnalysisMultiItem[]
  changes_between_sprints: SprintAnalysisMultiItem[]
  impediments_note?: string | null
}

type LegacyEvidence = { kind: EvidenceKind; text: string; evidence_ids: number[] }

function isV2(raw: Record<string, unknown>): boolean {
  const version = Number(raw.schema_version)
  if (version >= 2) return true
  return raw.risks != null && (Array.isArray(raw.deliveries) || Array.isArray(raw.management_actions))
}

function legacyToRisk(items: LegacyEvidence[]): SprintAnalysisRiskItem[] {
  return items.map((item) => ({
    description: item.text,
    impact: 'Impacto a confirmar com a equipe, com base nos registros citados.',
    known_status: 'Conforme evidências relacionadas.',
    recommended_action: null,
    evidence_ids: [...item.evidence_ids],
    kind: item.kind,
  }))
}

function inferDeliveryStage(text: string): DeliveryStage {
  const lower = text.toLowerCase()
  if (/validad|aceite|homolog/.test(lower)) return 'validated'
  if (/conclu|finaliz|entregue|closed|done|resolved/.test(lower)) return 'completed'
  if (/iniciad|começ|start|desenvolvimento iniciado/.test(lower)) return 'started'
  if (/planej|previst|escopo/.test(lower)) return 'planned'
  return 'in_progress'
}

function deriveWorkFrontsFromPack(pack: SprintAnalysis['pack']): SprintAnalysisWorkFront[] {
  if (!pack?.sprints) return []
  const groups = new Map<string, { ids: number[]; titles: string[] }>()
  for (const sprint of pack.sprints) {
    for (const story of sprint.stories ?? []) {
      const feature = story.feature?.title?.trim()
      const key = feature || 'Demais histórias da Sprint'
      const entry = groups.get(key) ?? { ids: [], titles: [] }
      entry.ids.push(story.work_item_id)
      if (story.title) entry.titles.push(story.title)
      groups.set(key, entry)
    }
  }
  return [...groups.entries()].map(([name, data]) => ({
    name,
    summary: data.titles.slice(0, 2).join('; ') || 'Histórias agrupadas por feature ou escopo.',
    expected_benefit: 'Benefício inferido a partir dos títulos e features vinculadas.',
    situation: 'Situação conforme estados registrados no Azure DevOps.',
    story_ids: data.ids,
  }))
}

function deriveTeamHighlights(pack: SprintAnalysis['pack']): SprintAnalysisTeamHighlight[] {
  return (pack?.collaborators ?? [])
    .filter((row) => row.name !== 'Sem responsável')
    .slice(0, 12)
    .map((row) => ({
      name: row.name,
      primary_front: 'A confirmar com a equipe',
      activity_summary: `Atua em ${row.stories} história(s) e ${row.tasks} task(s) no recorte analisado.`,
      story_ids: row.items.filter((i) => i.kind !== 'task').map((i) => i.work_item_id),
      task_ids: row.items.filter((i) => i.kind === 'task').map((i) => i.work_item_id),
    }))
}

export function normalizeSprintAnalysisResult(
  result: SprintAnalysis['result'],
  pack: SprintAnalysis['pack'],
): NormalizedSprintAnalysisResult | null {
  if (!result) return null
  const raw = result as Record<string, unknown>

  if (isV2(raw)) {
    const risks = (raw.risks ?? {}) as Record<string, unknown>
    return {
      schema_version: 2,
      legacy_derived: false,
      executive_summary: String(raw.executive_summary ?? ''),
      work_fronts: (raw.work_fronts as SprintAnalysisWorkFront[]) ?? [],
      deliveries: (raw.deliveries as SprintAnalysisDelivery[]) ?? [],
      team_highlights: (raw.team_highlights as SprintAnalysisTeamHighlight[]) ?? [],
      risks: {
        confirmed_impediments: (risks.confirmed_impediments as SprintAnalysisRiskItem[]) ?? [],
        registered_challenges: (risks.registered_challenges as SprintAnalysisRiskItem[]) ?? [],
        alerts: (risks.alerts as SprintAnalysisRiskItem[]) ?? [],
      },
      management_actions: (raw.management_actions as SprintAnalysisManagementAction[]) ?? [],
      comparison_narrative: (raw.comparison_narrative as string | null) ?? null,
      timeline: (raw.timeline as SprintAnalysisMultiItem[]) ?? [],
      changes_between_sprints: (raw.changes_between_sprints as SprintAnalysisMultiItem[]) ?? [],
      impediments_note: (raw.impediments_note as string | null) ?? null,
    }
  }

  const advances = (raw.advances as LegacyEvidence[]) ?? []
  const challenges = (raw.challenges as LegacyEvidence[]) ?? []
  const impediments = (raw.impediments as LegacyEvidence[]) ?? []
  const attention = (raw.attention_points as LegacyEvidence[]) ?? []
  const steps = (raw.next_steps as LegacyEvidence[]) ?? []

  return {
    schema_version: 1,
    legacy_derived: true,
    executive_summary: String(raw.executive_summary ?? ''),
    work_fronts: deriveWorkFrontsFromPack(pack),
    deliveries: advances.map((item, index) => ({
      title: `Avanço ${index + 1}`,
      stage: inferDeliveryStage(item.text),
      narrative: item.text,
      relevance: 'Relevância descrita no relatório anterior.',
      story_ids: [...item.evidence_ids],
    })),
    team_highlights: deriveTeamHighlights(pack),
    risks: {
      confirmed_impediments: legacyToRisk(impediments),
      registered_challenges: legacyToRisk(challenges),
      alerts: legacyToRisk(attention),
    },
    management_actions: steps.map((item) => ({
      action: item.text,
      reason: '',
      priority: 'media' as const,
      responsible: null,
      evidence_ids: [...item.evidence_ids],
    })),
    comparison_narrative: (raw.comparison_narrative as string | null) ?? null,
    timeline: (raw.timeline as SprintAnalysisMultiItem[]) ?? [],
    changes_between_sprints: (raw.changes_between_sprints as SprintAnalysisMultiItem[]) ?? [],
    impediments_note: (raw.impediments_note as string | null) ?? null,
  }
}

export function buildBriefingPlainText(
  normalized: NormalizedSprintAnalysisResult,
  meta: { scopeLabel: string; sprintNames: string[]; generatedAt?: string | null },
): string {
  const lines: string[] = []
  lines.push(`Relatório executivo — ${meta.scopeLabel}`)
  if (meta.sprintNames.length) lines.push(`Sprints: ${meta.sprintNames.join(', ')}`)
  if (meta.generatedAt) lines.push(`Gerado em: ${meta.generatedAt}`)
  lines.push('')
  lines.push('Visão geral')
  lines.push(normalized.executive_summary)
  lines.push('')
  if (normalized.work_fronts.length) {
    lines.push('O que está sendo desenvolvido')
    for (const front of normalized.work_fronts) {
      lines.push(`- ${front.name}: ${front.summary}`)
    }
    lines.push('')
  }
  if (normalized.deliveries.length) {
    lines.push('Entregas e evolução')
    for (const d of normalized.deliveries) {
      lines.push(`- [${d.stage}] ${d.title}: ${d.narrative}`)
    }
    lines.push('')
  }
  const { risks } = normalized
  if (
    risks.confirmed_impediments.length ||
    risks.registered_challenges.length ||
    risks.alerts.length
  ) {
    lines.push('Riscos e pontos de atenção')
    for (const item of risks.confirmed_impediments) lines.push(`- Impedimento: ${item.description}`)
    for (const item of risks.registered_challenges) lines.push(`- Desafio: ${item.description}`)
    for (const item of risks.alerts) lines.push(`- Alerta: ${item.description}`)
    lines.push('')
  }
  if (normalized.management_actions.length) {
    lines.push('Ações recomendadas para a gestão')
    for (const action of normalized.management_actions) {
      const reason = action.reason ? ` (${action.reason})` : ''
      lines.push(`- [${action.priority}] ${action.action}${reason}`)
    }
  }
  return lines.join('\n')
}

export const DELIVERY_STAGE_LABEL: Record<DeliveryStage, string> = {
  planned: 'Planejado',
  started: 'Desenvolvimento iniciado',
  in_progress: 'Em andamento',
  completed: 'Implementação concluída',
  validated: 'Entrega validada',
}

export const PRIORITY_LABEL: Record<ActionPriority, string> = {
  alta: 'Alta',
  media: 'Média',
  baixa: 'Baixa',
}
