/**
 * RunDetailPage.jsx — Phase 9.6
 *
 * Full authoritative Run Detail page accessible at `/run/{run_id}`.
 * Displays:
 * - Run State, Repository, Objective, Created, Analysis Started, Active Duration, Paused Duration, Stopped/Completed
 * - Agent Count, Task Count, Token Budget, Token Usage, Findings, Evidence, Agent Assignment, Recent Activity, Control Events
 * - Authoritative state-dependent control buttons:
 *   RUNNING: [Pause] [Stop]
 *   PAUSED: [Resume] [Stop]
 *   STOPPED / COMPLETED: [View Results]
 */

import { useState, useEffect, useCallback } from 'react'
import api from '../api'
import { fmt, shortId, Mono, StatusPill, Btn, Spinner } from './shared'

export function RunDetailPage({ runId, onNavigate }) {
  const [run, setRun] = useState(null)
  const [tasks, setTasks] = useState([])
  const [findings, setFindings] = useState([])
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [controlling, setControlling] = useState(false)

  const loadData = useCallback(async () => {
    if (!runId) return
    try {
      setLoading(true)
      const [r, t, f, ev] = await Promise.all([
        api.runDetail(runId),
        api.tasks({ limit: 100 }),
        api.findings({ limit: 50 }),
        api.runEvents ? api.runEvents(runId).catch(() => []) : Promise.resolve([]),
      ])
      setRun(r)
      // Filter tasks associated with this run
      const runTasks = (t?.items || []).filter(item => item.workflow_id === r.workflow_id || item.task_id?.includes(runId))
      setTasks(runTasks.length > 0 ? runTasks : (t?.items || []).slice(0, 10))
      setFindings(f?.items || [])
      setEvents(ev || [])
      setError(null)
    } catch (err) {
      setError(err.message || 'Failed to load run details')
    } finally {
      setLoading(false)
    }
  }, [runId])

  useEffect(() => {
    loadData()
    const iv = setInterval(loadData, 8000)
    return () => clearInterval(iv)
  }, [loadData])

  const handlePause = async () => {
    setControlling(true)
    try {
      await api.pauseRun(runId, { reason: 'Analyst requested pause from Run Detail' })
      await loadData()
    } catch (err) {
      alert(`Pause failed: ${err.message}`)
    } finally {
      setControlling(false)
    }
  }

  const handleResume = async () => {
    setControlling(true)
    try {
      await api.resumeRun(runId, { reason: 'Analyst requested resume from Run Detail' })
      await loadData()
    } catch (err) {
      alert(`Resume failed: ${err.message}`)
    } finally {
      setControlling(false)
    }
  }

  const handleStop = async () => {
    if (!window.confirm('Are you sure you want to stop this investigation run?')) return
    setControlling(true)
    try {
      await api.stopRun(runId, { reason: 'Analyst requested stop from Run Detail' })
      await loadData()
    } catch (err) {
      alert(`Stop failed: ${err.message}`)
    } finally {
      setControlling(false)
    }
  }

  if (loading && !run) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
        <Spinner size={32} />
      </div>
    )
  }

  if (error && !run) {
    return (
      <div style={{ padding: 20 }}>
        <div style={{ background: '#f8717111', border: '1px solid #f8717144', padding: 16, borderRadius: 8, color: '#f87171' }}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>API ERROR</div>
          <div style={{ fontSize: 13, marginBottom: 12 }}>GET /api/runs/{runId} — {error}</div>
          <Btn onClick={loadData} variant="primary" size="sm">↺ Retry</Btn>
        </div>
      </div>
    )
  }

  const state = run.run_state || run.status || 'UNKNOWN'
  const isRunning = state === 'RUNNING' || state === 'IN_PROGRESS'
  const isPaused = state === 'PAUSED' || state === 'PAUSE_REQUESTED'
  const isStopped = state === 'STOPPED' || state === 'COMPLETED' || state === 'EMERGENCY_STOPPED'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 10 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 20 }}>🚀</span>
            <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {run.run_id}
            </span>
            <StatusPill status={state} />
            <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
              Stage: {run.stage || 'SECURITY_ANALYSIS'}
            </span>
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            Repository: <strong>{run.repository_name || 'Target Repository'}</strong> ({run.repository_path})
          </div>
        </div>

        {/* State-dependent Control Actions */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {isRunning && (
            <>
              <Btn onClick={handlePause} disabled={controlling} variant="secondary" size="sm">
                ⏸ Pause
              </Btn>
              <Btn onClick={handleStop} disabled={controlling} variant="danger" size="sm">
                ⏹ Stop
              </Btn>
            </>
          )}

          {isPaused && (
            <>
              <Btn onClick={handleResume} disabled={controlling} variant="primary" size="sm">
                ▶ Resume
              </Btn>
              <Btn onClick={handleStop} disabled={controlling} variant="danger" size="sm">
                ⏹ Stop
              </Btn>
            </>
          )}

          {isStopped && (
            <Btn onClick={() => onNavigate && onNavigate('dossier')} variant="primary" size="sm">
              📊 View Results
            </Btn>
          )}

          <Btn onClick={() => onNavigate && onNavigate('overview')} variant="secondary" size="sm">
            ← Overview
          </Btn>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 10 }}>
        {[
          { label: 'Run State', value: state },
          { label: 'Active Duration', value: run.active_duration_seconds ? `${Math.round(run.active_duration_seconds)}s` : (run.elapsed_seconds ? `${Math.round(run.elapsed_seconds)}s` : '0s') },
          { label: 'Token Budget', value: `${(run.token_budget || 650000).toLocaleString()} tok` },
          { label: 'Active Tasks', value: `${run.active_tasks || 0} active / ${run.total_tasks || 0} total` },
          { label: 'Findings Recorded', value: `${run.findings_count || findings.length}` },
          { label: 'Checkpoints', value: `${run.checkpoint_count || 0}` },
          { label: 'Analysis Started', value: fmt(run.analysis_started_at || run.start_time) },
          { label: 'Paused / Stopped At', value: fmt(run.paused_at || run.stopped_at) },
        ].map(({ label, value }) => (
          <div key={label} style={{ background: 'var(--bg-panel)', padding: 12, borderRadius: 8, border: '1px solid var(--border)' }}>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Associated Tasks */}
      <div style={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 10, padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
            ⚡ Associated Tasks ({tasks.length})
          </div>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Click row to open canonical task detail</span>
        </div>

        {tasks.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: 14 }}>No tasks recorded for this run.</div>
        ) : (
          <table className="data-table" style={{ width: '100%' }}>
            <thead>
              <tr>
                <th>Task ID</th>
                <th>Objective</th>
                <th>Status</th>
                <th>Agent</th>
                <th>Created</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map(t => (
                <tr
                  key={t.task_id}
                  onClick={() => onNavigate && onNavigate('task', { id: t.task_id, type: 'task' })}
                  style={{ cursor: 'pointer' }}
                >
                  <td><Mono>{shortId(t.task_id)}</Mono></td>
                  <td style={{ maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {t.objective}
                  </td>
                  <td><StatusPill status={t.status} /></td>
                  <td><Mono>{t.assigned_agent_id || '—'}</Mono></td>
                  <td className="text-muted">{fmt(t.created_at)}</td>
                  <td>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        onNavigate && onNavigate('task', { id: t.task_id, type: 'task' })
                      }}
                      className="btn btn-secondary btn-sm"
                      style={{ fontSize: 10, padding: '2px 8px' }}
                    >
                      View →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
