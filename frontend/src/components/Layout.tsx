import { Link, Outlet, useLocation } from 'react-router-dom'

export function Layout() {
  const loc = useLocation()
  const isFleet = loc.pathname === '/'

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-surface)] px-6 py-3">
        <div className="mx-auto flex max-w-[1400px] items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/" className="font-mono text-sm font-semibold tracking-tight text-white">
              sys<span className="text-[var(--color-ok)]">health</span>
            </Link>
            <span className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2.5 py-1 font-mono text-[11px] text-[var(--color-muted)]">
              Data Center Fleet
            </span>
          </div>
          <nav className="flex items-center gap-3 text-[11px]">
            <Link
              to="/"
              className={isFleet ? 'text-white' : 'text-[var(--color-muted)] hover:text-white'}
            >
              Fleet overview
            </Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-5">
        <Outlet />
      </main>
    </div>
  )
}
