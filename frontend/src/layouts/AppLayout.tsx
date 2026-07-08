import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { OnboardingGuide } from '../onboarding/OnboardingGuide'
import { OnboardingProvider } from '../onboarding/OnboardingContext'
import { Sidebar } from '../components/Sidebar'

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <OnboardingProvider>
      <div className="flex h-full min-h-screen bg-bg">
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

        <div className="flex flex-1 flex-col overflow-hidden">
          <header className="flex items-center gap-4 border-b border-border bg-surface px-4 py-3 lg:hidden">
            <button
              onClick={() => setSidebarOpen(true)}
              className="rounded-lg p-2 text-muted hover:bg-surface-hover hover:text-text"
              aria-label="Abrir menú"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <span className="text-sm font-semibold text-text">PrecioPartes</span>
          </header>

          <main className="flex-1 overflow-auto p-4 md:p-6">
            <Outlet />
          </main>
        </div>

        <OnboardingGuide />
      </div>
    </OnboardingProvider>
  )
}
