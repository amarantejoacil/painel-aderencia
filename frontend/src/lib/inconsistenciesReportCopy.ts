import type { InconsistenciesReportRow } from '@/lib/api'
import { monthLabel } from '@/lib/format'

export const DEFAULT_COPY_INTRO_REQUIRES_REVIEW = `Olá, {primeiro_nome}.

Segue o relatório de aderência referente a {periodo} para sua verificação (com base na última importação do Azure DevOps).
Pedimos que confira os apontamentos abaixo. Caso já tenha regularizado no Azure ou identifique divergência, por favor me avise.`

export const DEFAULT_COPY_INTRO_OK = `Olá, {primeiro_nome}.

Segue a conferência de aderência referente a {periodo}. Não identificamos inconsistências nos seus lançamentos neste período.
Se notar alguma divergência em relação ao Azure DevOps, por favor me avise.`

export type InconsistenciesReportCopySettings = {
  copy_intro_requires_review: string
  copy_intro_ok: string
}

export const COPY_INTRO_PLACEHOLDERS = [
  { key: '{primeiro_nome}', label: 'Primeiro nome do colaborador' },
  { key: '{nome}', label: 'Igual a {primeiro_nome}' },
  { key: '{nome_completo}', label: 'Nome completo' },
  { key: '{periodo}', label: 'Mês/ano do relatório (ex.: outubro/2025)' },
] as const

function collaboratorFirstName(fullName: string): string {
  const trimmed = fullName.trim()
  if (!trimmed) return 'colaborador(a)'
  return trimmed.split(/\s+/)[0] ?? trimmed
}

function periodShort(year: number, month: number): string {
  return monthLabel(year, month).replace(' de ', '/')
}

export function applyCopyIntroTemplate(
  template: string,
  row: InconsistenciesReportRow,
  year: number,
  month: number,
): string {
  const firstName = collaboratorFirstName(row.collaborator.name)
  const fullName = row.collaborator.name.trim() || firstName
  const period = periodShort(year, month)
  let text = template
  text = text.replaceAll('{primeiro_nome}', firstName)
  text = text.replaceAll('{nome}', firstName)
  text = text.replaceAll('{nome_completo}', fullName)
  text = text.replaceAll('{periodo}', period)
  return `${text.trim()}\n\n---\n\n`
}

export function resolveCopySettings(
  settings: InconsistenciesReportCopySettings | null | undefined,
): InconsistenciesReportCopySettings {
  return {
    copy_intro_requires_review:
      settings?.copy_intro_requires_review?.trim() || DEFAULT_COPY_INTRO_REQUIRES_REVIEW,
    copy_intro_ok: settings?.copy_intro_ok?.trim() || DEFAULT_COPY_INTRO_OK,
  }
}

export function buildCollaboratorIntro(
  row: InconsistenciesReportRow,
  year: number,
  month: number,
  settings: InconsistenciesReportCopySettings | null | undefined,
): string {
  const resolved = resolveCopySettings(settings)
  const template =
    row.situation === 'ok' ? resolved.copy_intro_ok : resolved.copy_intro_requires_review
  return applyCopyIntroTemplate(template, row, year, month)
}
