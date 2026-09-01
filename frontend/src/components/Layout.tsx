import { NavLink, Outlet } from 'react-router-dom'
import { CalendarDays, LayoutDashboard, Settings, Upload, Users } from 'lucide-react'
import { cn } from '@/lib/utils'

const LINKS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/importacao', label: 'Importação', icon: Upload },
  { to: '/colaboradores', label: 'Colaboradores', icon: Users },
  { to: '/calendario', label: 'Calendário', icon: CalendarDays },
  { to: '/configuracoes', label: 'Configurações', icon: Settings },
]

export function Layout() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">NIA · Azure Boards</p>
            <h1 className="text-xl font-semibold">Painel de Aderência de Atividades</h1>
          </div>
          <nav className="flex flex-wrap gap-2">
            {LINKS.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
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
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
