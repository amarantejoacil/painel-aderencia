import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  CalendarDays,
  ClipboardList,
  FileText,
  History,
  Layers,
  LayoutDashboard,
  ListChecks,
  Menu,
  Settings,
  SquareKanban,
  TrendingUp,
  TriangleAlert,
  Upload,
  Users,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'

type NavItem = {
  to: string
  label: string
  icon: typeof LayoutDashboard
  end?: boolean
}

const SECTIONS: Array<{ title: string; links: NavItem[] }> = [
  {
    title: 'Aderência de Atividades',
    links: [
      { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
      { to: '/relatorio-inconsistencias', label: 'Inconsistências', icon: TriangleAlert },
      { to: '/importacao', label: 'Importações', icon: Upload },
      { to: '/colaboradores', label: 'Colaboradores', icon: Users },
      { to: '/calendario', label: 'Calendário', icon: CalendarDays },
    ],
  },
  {
    title: 'Acompanhamento de Projetos',
    links: [
      { to: '/projetos', label: 'Visão Geral', icon: SquareKanban, end: true },
      { to: '/projetos/sprints', label: 'Sprints', icon: ListChecks },
      { to: '/projetos/evolucao', label: 'Evolução', icon: TrendingUp },
      { to: '/projetos/relatorios', label: 'Relatórios', icon: FileText },
    ],
  },
  {
    title: 'Gestão de Apontamentos',
    links: [
      { to: '/apontamentos', label: 'Meus Apontamentos', icon: ClipboardList, end: true },
      { to: '/apontamentos/lote', label: 'Lançamento em Lote', icon: Layers },
      { to: '/apontamentos/historico', label: 'Histórico', icon: History },
    ],
  },
  {
    title: 'Administração',
    links: [{ to: '/configuracoes', label: 'Configurações', icon: Settings }],
  },
]

function SideNav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-6 px-3 py-4">
      {SECTIONS.map((section) => (
        <div key={section.title}>
          <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-[0.14em] text-muted">
            {section.title}
          </p>
          <div className="flex flex-col gap-1">
            {section.links.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    'inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm',
                    isActive ? 'bg-accent-soft text-accent' : 'text-muted hover:bg-paper hover:text-ink',
                  )
                }
              >
                <Icon size={16} />
                {label}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>
  )
}

export function Layout() {
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  return (
    <div className="min-h-screen md:grid md:grid-cols-[16rem_minmax(0,1fr)]">
      <aside className="hidden border-r border-line bg-white md:sticky md:top-0 md:flex md:h-screen md:flex-col md:overflow-y-auto">
        <div className="border-b border-line px-6 py-5">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">NIA · Azure Boards</p>
          <p className="mt-1 text-base font-semibold leading-snug">Painel de Aderência</p>
        </div>
        <SideNav />
      </aside>

      <div className="min-w-0">
        <header className="flex items-center justify-between border-b border-line bg-white px-4 py-3 md:hidden">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">NIA · Azure Boards</p>
            <p className="text-sm font-semibold">Painel de Aderência</p>
          </div>
          <button
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-md text-ink hover:bg-paper"
            aria-expanded={menuOpen}
            aria-label={menuOpen ? 'Fechar menu' : 'Abrir menu'}
            onClick={() => setMenuOpen((open) => !open)}
          >
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </header>

        {menuOpen ? (
          <div className="border-b border-line bg-white md:hidden">
            <SideNav onNavigate={() => setMenuOpen(false)} />
          </div>
        ) : null}

        <main className="mx-auto w-full max-w-6xl px-4 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
