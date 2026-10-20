import { useState } from 'react'

export function EvidenceLinks({
  ids,
  urls,
  label = 'histórias relacionadas',
}: {
  ids: number[]
  urls: Map<number, string>
  label?: string
}) {
  const unique = [...new Set(ids)].filter(Boolean)
  const [open, setOpen] = useState(false)
  if (unique.length === 0) return null
  const countLabel = unique.length === 1 ? '1 história relacionada' : `Ver ${unique.length} ${label}`
  return (
    <span className="mt-1 block print:hidden">
      <button
        type="button"
        className="text-xs font-medium text-accent hover:underline"
        onClick={() => setOpen((value) => !value)}
      >
        {open ? 'Recolher evidências' : countLabel}
      </button>
      {open ? (
        <span className="mt-1 flex flex-wrap gap-x-2 gap-y-1 text-xs text-muted">
          {unique.map((id) =>
            urls.get(id) ? (
              <a key={id} href={urls.get(id)} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                #{id}
              </a>
            ) : (
              <span key={id}>#{id}</span>
            ),
          )}
        </span>
      ) : null}
      <span className="hidden print:inline text-xs text-muted">
        {' '}
        (IDs: {unique.map((id) => `#${id}`).join(', ')})
      </span>
    </span>
  )
}
