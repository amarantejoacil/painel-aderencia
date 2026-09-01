import { useState } from 'react'
import type { ReactNode } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Card } from '@/components/ui/card'
import { ChartDetailModal, type ChartSelection } from '@/components/ChartDetailModal'
import type { Dashboard } from '@/lib/api'
import { formatDate, formatHours, formatPercent } from '@/lib/format'

const COLORS = {
  accent: '#1f6f5b',
  ok: '#1f6f5b',
  review: '#d97706',
  missing: '#dc2626',
  incomplete: '#d97706',
  excess: '#7c3aed',
  regular: '#1f6f5b',
  inconsistent: '#dc2626',
  muted: '#94a3b8',
}

type ChartPayload = {
  collaboratorId?: number
  date?: string
  fullName?: string
}

function shortName(name: string, max = 22): string {
  if (name.length <= max) return name
  return `${name.slice(0, max - 1)}…`
}

function ChartCard({
  title,
  children,
  empty,
  heightPx = 288,
}: {
  title: string
  children: ReactNode
  empty?: string
  heightPx?: number
}) {
  return (
    <Card className="p-4">
      <h4 className="mb-1 text-sm font-semibold">{title}</h4>
      <p className="mb-3 text-xs text-muted">Clique em um item para ver os registros.</p>
      {empty ? (
        <div
          className="flex items-center justify-center text-sm text-muted"
          style={{ height: heightPx }}
        >
          {empty}
        </div>
      ) : (
        <div className="w-full" style={{ height: heightPx }}>
          {children}
        </div>
      )}
    </Card>
  )
}

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{ name?: string; value?: number; color?: string; payload?: Record<string, unknown> }>
  label?: string
}) {
  if (!active || !payload?.length) return null
  const fullName = payload[0]?.payload?.fullName as string | undefined
  return (
    <div className="rounded-md border border-line bg-white px-3 py-2 text-xs shadow-sm">
      <p className="font-medium">{fullName ?? label}</p>
      <ul className="mt-1 space-y-0.5 text-muted">
        {payload.map((entry) => (
          <li key={String(entry.name)} style={{ color: entry.color }}>
            {entry.name}:{' '}
            {typeof entry.value === 'number' && entry.name?.toString().includes('ader')
              ? formatPercent(entry.value)
              : typeof entry.value === 'number' && entry.name?.toString().includes('Horas')
                ? formatHours(entry.value)
                : entry.value}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[10px] text-muted">Clique para detalhar</p>
    </div>
  )
}

export function DashboardCharts({ data }: { data: Dashboard }) {
  const [selection, setSelection] = useState<ChartSelection | null>(null)
  const { rows, indicators, daily_adherence: dailyAdherence, year, month } = data

  const openCollaborator = (collaboratorId: number) => {
    setSelection({ kind: 'collaborator', collaboratorId })
  }

  const adherenceData = [...rows]
    .map((row) => ({
      collaboratorId: row.collaborator.id,
      name: shortName(row.collaborator.name),
      fullName: row.collaborator.name,
      adherence: Number(row.adherence),
    }))
    .sort((a, b) => a.adherence - b.adherence)

  const hoursData = rows.map((row) => ({
    collaboratorId: row.collaborator.id,
    name: shortName(row.collaborator.name),
    fullName: row.collaborator.name,
    'Horas esperadas': Number(row.expected),
    'Horas executadas': Number(row.executed),
  }))

  const inconsistencyData = rows
    .filter((row) => row.missing + row.incomplete + row.excess > 0)
    .map((row) => ({
      collaboratorId: row.collaborator.id,
      name: shortName(row.collaborator.name),
      fullName: row.collaborator.name,
      'Sem lançamento': row.missing,
      Incompleto: row.incomplete,
      Excedente: row.excess,
    }))

  const okCount = rows.filter(
    (row) => row.missing === 0 && row.incomplete === 0 && row.excess === 0,
  ).length
  const teamSituation = [
    { name: 'OK', value: okCount, color: COLORS.ok, situation: 'ok' as const },
    {
      name: 'Requer revisão',
      value: rows.length - okCount,
      color: COLORS.review,
      situation: 'review' as const,
    },
  ].filter((item) => item.value > 0)

  const dailyData = dailyAdherence.map((item) => ({
    date: item.date,
    day: Number(item.date.split('-')[2]),
    label: formatDate(item.date),
    adherence: Number(item.adherence),
    collaborators: item.collaborators,
  }))

  const inconsistentDays = indicators.incomplete + indicators.missing + indicators.excess
  const dayCompliance = [
    { name: 'Dias regulares', value: indicators.regular, color: COLORS.regular, category: 'regular' as const },
    {
      name: 'Dias com inconsistência',
      value: inconsistentDays,
      color: COLORS.inconsistent,
      category: 'inconsistent' as const,
    },
  ].filter((item) => item.value > 0)

  const adherenceChartHeight = Math.max(288, adherenceData.length * 36)

  const barClickCollaborator = (bar: { payload?: ChartPayload }) => {
    const collaboratorId = bar.payload?.collaboratorId
    if (collaboratorId) openCollaborator(collaboratorId)
  }

  return (
    <>
      <section className="space-y-3">
        <div>
          <h3 className="text-lg font-semibold">Análise Gráfica</h3>
          <p className="mt-1 text-sm text-muted">
            Visualização gerencial da aderência, horas e inconsistências conforme os filtros selecionados.
          </p>
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          <ChartCard
            title="Aderência por Colaborador"
            empty={rows.length === 0 ? 'Sem dados para exibir.' : undefined}
            heightPx={adherenceChartHeight}
          >
            {rows.length > 0 && (
              <ResponsiveContainer width="100%" height={adherenceChartHeight}>
                <BarChart data={adherenceData} layout="vertical" margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} fontSize={12} />
                  <YAxis type="category" dataKey="name" width={110} fontSize={11} />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar
                    dataKey="adherence"
                    name="Aderência"
                    fill={COLORS.accent}
                    radius={[0, 4, 4, 0]}
                    cursor="pointer"
                    onClick={barClickCollaborator}
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard title="Situação da Equipe" empty={rows.length === 0 ? 'Sem dados para exibir.' : undefined}>
            {rows.length > 0 && (
              <ResponsiveContainer width="100%" height={288}>
                <PieChart>
                  <Pie
                    data={teamSituation}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={2}
                    cursor="pointer"
                    onClick={(entry) => {
                      const situation = (entry as { situation?: 'ok' | 'review' }).situation
                      if (situation) setSelection({ kind: 'team-status', situation })
                    }}
                  >
                    {teamSituation.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value, name) => [
                      `${Number(value ?? 0)} colaborador(es)`,
                      String(name),
                    ]}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard title="Horas Esperadas x Executadas" empty={rows.length === 0 ? 'Sem dados para exibir.' : undefined}>
            {rows.length > 0 && (
              <ResponsiveContainer width="100%" height={288}>
                <BarChart data={hoursData} margin={{ left: 8, right: 8, top: 8, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="name" fontSize={11} interval={0} angle={-25} textAnchor="end" height={70} />
                  <YAxis fontSize={12} />
                  <Tooltip content={<ChartTooltip />} />
                  <Legend />
                  <Bar
                    dataKey="Horas esperadas"
                    fill={COLORS.muted}
                    radius={[4, 4, 0, 0]}
                    cursor="pointer"
                    onClick={barClickCollaborator}
                  />
                  <Bar
                    dataKey="Horas executadas"
                    fill={COLORS.accent}
                    radius={[4, 4, 0, 0]}
                    cursor="pointer"
                    onClick={barClickCollaborator}
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard
            title="Inconsistências por Colaborador"
            empty={
              rows.length === 0
                ? 'Sem dados para exibir.'
                : inconsistencyData.length === 0
                  ? 'Nenhum colaborador com inconsistências no período.'
                  : undefined
            }
          >
            {inconsistencyData.length > 0 && (
              <ResponsiveContainer width="100%" height={288}>
                <BarChart data={inconsistencyData} margin={{ left: 8, right: 8, top: 8, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="name" fontSize={11} interval={0} angle={-25} textAnchor="end" height={70} />
                  <YAxis allowDecimals={false} fontSize={12} />
                  <Tooltip content={<ChartTooltip />} />
                  <Legend />
                  <Bar
                    dataKey="Sem lançamento"
                    stackId="a"
                    fill={COLORS.missing}
                    cursor="pointer"
                    onClick={(bar) => {
                      const id = bar.payload?.collaboratorId
                      if (id) setSelection({ kind: 'inconsistency', collaboratorId: id, status: 'missing' })
                    }}
                  />
                  <Bar
                    dataKey="Incompleto"
                    stackId="a"
                    fill={COLORS.incomplete}
                    cursor="pointer"
                    onClick={(bar) => {
                      const id = bar.payload?.collaboratorId
                      if (id) setSelection({ kind: 'inconsistency', collaboratorId: id, status: 'incomplete' })
                    }}
                  />
                  <Bar
                    dataKey="Excedente"
                    stackId="a"
                    fill={COLORS.excess}
                    radius={[4, 4, 0, 0]}
                    cursor="pointer"
                    onClick={(bar) => {
                      const id = bar.payload?.collaboratorId
                      if (id) setSelection({ kind: 'inconsistency', collaboratorId: id, status: 'excess' })
                    }}
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard
            title="Evolução Diária da Aderência"
            empty={dailyData.length === 0 ? 'Nenhum dia com obrigação de lançamento no período.' : undefined}
          >
            {dailyData.length > 0 && (
              <ResponsiveContainer width="100%" height={288}>
                <LineChart data={dailyData} margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="day" fontSize={12} label={{ value: 'Dia', position: 'insideBottom', offset: -4 }} />
                  <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} fontSize={12} />
                  <Tooltip
                    formatter={(value) => [formatPercent(Number(value ?? 0)), 'Aderência']}
                    labelFormatter={(_, payload) => {
                      const item = payload?.[0]?.payload as { label?: string; collaborators?: number } | undefined
                      if (!item?.label) return ''
                      return `${item.label} · ${item.collaborators} colaborador(es)`
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="adherence"
                    name="Aderência"
                    stroke={COLORS.accent}
                    strokeWidth={2}
                    dot={(props) => {
                      const { cx, cy, payload } = props
                      if (cx == null || cy == null) return null
                      const point = payload as { date?: string }
                      return (
                        <circle
                          cx={cx}
                          cy={cy}
                          r={4}
                          fill={COLORS.accent}
                          stroke="#fff"
                          strokeWidth={1}
                          style={{ cursor: 'pointer' }}
                          onClick={() => {
                            if (point.date) setSelection({ kind: 'daily', date: point.date })
                          }}
                        />
                      )
                    }}
                    activeDot={{
                      r: 6,
                      cursor: 'pointer',
                      onClick: (_, payload) => {
                        const point = payload as { payload?: { date?: string } }
                        const date = point.payload?.date
                        if (date) setSelection({ kind: 'daily', date })
                      },
                    }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard
            title="Conformidade dos Dias Analisados"
            empty={dayCompliance.length === 0 ? 'Sem dias obrigatórios no período.' : undefined}
          >
            {dayCompliance.length > 0 && (
              <ResponsiveContainer width="100%" height={288}>
                <PieChart>
                  <Pie
                    data={dayCompliance}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={2}
                    cursor="pointer"
                    onClick={(entry) => {
                      const category = (entry as { category?: 'regular' | 'inconsistent' }).category
                      if (category) setSelection({ kind: 'day-compliance', category })
                    }}
                  >
                    {dayCompliance.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value, name) => [`${Number(value ?? 0)} dia(s)`, String(name)]}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            )}
          </ChartCard>
        </div>
      </section>

      <ChartDetailModal
        selection={selection}
        rows={rows}
        year={year}
        month={month}
        onClose={() => setSelection(null)}
      />
    </>
  )
}
