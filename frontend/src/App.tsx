import { useCallback, useEffect, useState } from 'react'
import { api, type Stats } from './api'
import ChatView from './views/ChatView'
import CandidatesView from './views/CandidatesView'
import UploadView from './views/UploadView'

type View = 'chat' | 'candidates' | 'upload'

const NAV: { id: View; label: string; icon: React.ReactNode }[] = [
  {
    id: 'chat',
    label: 'Chat',
    icon: (
      <svg viewBox="0 0 16 16" aria-hidden="true">
        <path d="M2.5 3.5h11v7h-6l-3 3v-3h-2z" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    id: 'candidates',
    label: 'Candidates',
    icon: (
      <svg viewBox="0 0 16 16" aria-hidden="true">
        <circle cx="5.5" cy="5" r="2.3" fill="none" stroke="currentColor" strokeWidth="1.4" />
        <path d="M1.8 13c.5-2.5 2-3.8 3.7-3.8S8.7 10.5 9.2 13" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        <circle cx="11" cy="5.5" r="1.9" fill="none" stroke="currentColor" strokeWidth="1.4" />
        <path d="M10.6 9.4c1.9 0 3.2 1.2 3.6 3.4" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: 'upload',
    label: 'Upload CVs',
    icon: (
      <svg viewBox="0 0 16 16" aria-hidden="true">
        <path d="M8 10.5V2.8M4.8 5.8 8 2.6l3.2 3.2M2.8 13.2h10.4" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
]

export default function App() {
  const [view, setView] = useState<View>('chat')
  const [stats, setStats] = useState<Stats | null>(null)

  const refreshStats = useCallback(() => {
    api.stats().then(setStats).catch(() => setStats(null))
  }, [])

  useEffect(refreshStats, [refreshStats])

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">CV Checker</span>
        </div>

        <nav className="nav" aria-label="Main">
          {NAV.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav-item${view === item.id ? ' is-active' : ''}`}
              aria-current={view === item.id ? 'page' : undefined}
              onClick={() => setView(item.id)}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-foot">
          {stats
            ? `${stats.candidates} candidate${stats.candidates === 1 ? '' : 's'} indexed`
            : 'Backend not reachable'}
        </div>
      </aside>

      <main className="main">
        {view === 'chat' && <ChatView hasCandidates={(stats?.candidates ?? 0) > 0} />}
        {view === 'candidates' && <CandidatesView />}
        {view === 'upload' && <UploadView onIngested={refreshStats} />}
      </main>
    </div>
  )
}
