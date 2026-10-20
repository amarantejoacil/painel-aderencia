import type { ReactNode } from 'react'

export function TimeEntryShell({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">
          Gestão de Apontamentos
        </p>
        <h2 className="text-2xl font-semibold">{title}</h2>
        <p className="mt-1 max-w-3xl text-sm text-muted">{description}</p>
      </div>
      {children}
    </div>
  )
}

export const fieldClass =
  'w-full rounded-md border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-accent'

export function newOperationKey(): string {
  return crypto.randomUUID()
}
