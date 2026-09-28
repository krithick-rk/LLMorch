import { useState, useEffect, useCallback } from 'react'
import api from '../api'
import { fmt, shortId, Mono, StatusBadge, Spinner, EmptyState, fmtElapsed } from './shared'

export function RunHistoryPage({ refreshSignal, onNavigate }) {
  const [runs, setRuns] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('ALL')
  const [search, setSearch] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.runs({ limit: 100 })
      const items = Array.isArray(res) ? res : (res.items || [])
      setRuns(items)
    } catch {
      setRuns([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load, refreshSignal])

  const filteredRuns = (runs || []).filter(r => {
    const st = (r.run_state || r.status || '').toUpperCase()
    if (filter === 'RUNNING' && !['RUNNING', 'IN_PROGRESS'].includes(st)) return false
    if (filter === 'PAUSED' && !['PAUSED', 'PAUSE_REQUESTED'].includes(st)) return false
    if (filter === 'STOPPED' && !['STOPPED', 'EMERGENCY_STOPPED', 'STOP_REQUESTED'].includes(st)) return false
    if (filter === 'COMPLETED' && !['COMPLETED', 'SUCCEEDED'].includes(st)) return false
    if (filter === 'FAILED' && st !== 'FAILED') return false

    if (search) {
      const q = search.toLowerCase()
      const matchId = (r.run_id || '').toLowerCase().includes(q)
      const matchRepo = (r.repository_name || r.repository_path || '').toLowerCase().includes(q)
      if (!matchId && !matchRepo) return false
    }
    return true
  })

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">⏱️ Investigation Run History</div>
          <div className="page-subtitle">Authoritative repository investigation lifecycle and audit history</div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-secondary btn-sm" onClick={load}>↺ Refresh</button>
        </div>
      </div>

      {/* Filter and search bar */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        background: 'var(--bg-elevated)', padding: '10px 14px', borderRadius: '8px',
        border: '1px solid var(--border)', marginBottom: '16px', gap: '12px', flexWrap: 'wrap',
      }}>
        <div style={{ display: 'flex', gap: '6px' }}>
          {['ALL', 'RUNNING', 'PAUSED', 'STOPPED', 'COMPLETED', 'FAILED'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                background: filter === f ? 'var(--accent-blue)' : 'var(--bg-base)',
                color: filter === f ? '#fff' : 'var(--text-muted)',
                border: '1px solid var(--border)',
                borderRadius: '5px',
                padding: '4px 10px',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {f}
            </button>
          ))}
        </div>
        <input
          type="text"
          placeholder="Filter by Run ID or Repository…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            background: 'var(--bg-base)',
            border: '1px solid var(--border)',
            borderRadius: '5px',
            padding: '5px 10px',
            fontSize: '12px',
            color: 'var(--text-primary)',
            minWidth: '240px',
          }}
        />
      </div>

      {loading && !runs ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}><Spinner /></div>
      ) : filteredRuns.length === 0 ? (
        <EmptyState icon="⏱️" msg="No runs matching filter" />
      ) : (
        <div className="card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Repository</th>
                <th>Status</th>
                <th>Started</th>
                <th>Security Analysis Duration</th>
                <th>Tasks</th>
                <th>Findings</th>
                <th>Token Budget</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredRuns.map(r => {
                const st = r.run_state || r.status || 'UNKNOWN'
                const isNav = (e) => {
                  if (!e.ctrlKey && !e.metaKey && !e.shiftKey && e.button === 0) {
                    e.preventDefault()
                    if (onNavigate) onNavigate('run', { type: 'run', id: r.run_id })
                  }
                }

                return (
                  <tr
                    key={r.run_id}
                    style={{ cursor: 'pointer' }}
                    onClick={(e) => isNav(e)}
                  >
                    <td>
                      <a
                        href={`/run/${r.run_id}`}
                        onClick={isNav}
                        style={{ textDecoration: 'none', color: 'var(--accent-blue)', fontWeight: 600 }}
                      >
                        <Mono>{shortId(r.run_id)}</Mono>
                      </a>
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        {r.repository_name || 'Generic Repo'}
                      </div>
                      <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        {r.repository_path || '—'}
                      </div>
                    </td>
                    <td><StatusBadge status={st} /></td>
                    <td className="text-muted" style={{ fontSize: '11px' }}>{fmt(r.start_time || r.created_at)}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                      {fmtElapsed(r.active_duration_seconds || r.elapsed_seconds || 0)}
                    </td>
                    <td>
                      <span className="mono">{r.active_tasks > 0 ? `${r.active_tasks} active / ` : ''}{r.total_tasks || 0}</span>
                    </td>
                    <td>
                      <span className={`mono ${(r.findings_count || 0) > 0 ? 'text-amber' : ''}`}>
                        {r.findings_count || 0}
                      </span>
                    </td>
                    <td className="text-muted" style={{ fontSize: '11px' }}>
                      {r.token_budget ? Number(r.token_budget).toLocaleString() : '—'}
                    </td>
                    <td>
                      <button
                        className="btn btn-secondary btn-xs"
                        onClick={(e) => {
                          e.stopPropagation()
                          if (onNavigate) onNavigate('run', { type: 'run', id: r.run_id })
                        }}
                      >
                        View Details →
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
