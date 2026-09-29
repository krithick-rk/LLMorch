/**
 * ProjectHomePage.jsx — Lightweight Engineering Project Landing Page
 * Section 2:
 * - Project Home is a lightweight landing page
 * - Shows: Project, Target directory, Status, Last run, Current plan status, High-level counts, Recent activity
 * - Primary actions: [Open Verification Workspace], [Open Master Session], [Create Task], [View Results]
 * - Detailed intake, manifests, scope, and planning workflow moved to Verification Workspace
 */

import { useState, useEffect, useCallback } from 'react'
import api from '../api'
import { StatusPill, Spinner, fmt, Mono } from './shared'

export default function ProjectHomePage({ activeProject, onNavigate, onOpenCreateTask }) {
  const [summary, setSummary] = useState(null)
  const [lastRun, setLastRun] = useState(null)
  const [closure, setClosure] = useState(null)
  const [activity, setActivity] = useState([])
  const [loading, setLoading] = useState(true)
  const [instruction, setInstruction] = useState('')
  const [interpreting, setInterpreting] = useState(false)
  const [interpretedAction, setInterpretedAction] = useState(null)
  const [dispatchMsg, setDispatchMsg] = useState(null)

  const loadData = useCallback(async () => {
    if (!activeProject?.project_id) {
      setLoading(false)
      return
    }
    try {
      setLoading(true)
      const [sum, runsRes, closeRes, eventsRes] = await Promise.all([
        api.projectSummary(activeProject.project_id).catch(() => null),
        api.runs({ project_id: activeProject.project_id, limit: 5 }).catch(() => ({ runs: [] })),
        api.getClosure(null, { project_id: activeProject.project_id }).catch(() => null),
        api.events({ project_id: activeProject.project_id, limit: 12 }).catch(() => ({ events: [] }))
      ])
      setSummary(sum)
      const rList = runsRes.runs || []
      setLastRun(rList.length > 0 ? rList[0] : null)
      setClosure(closeRes)
      setActivity(eventsRes.events || [])
    } finally {
      setLoading(false)
    }
  }, [activeProject?.project_id])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleInterpret = async () => {
    if (!instruction.trim() || !activeProject?.project_id) return
    try {
      setInterpreting(true)
      setDispatchMsg(null)
      const res = await api.interpretInstruction(activeProject.project_id, { instruction })
      setInterpretedAction(res)
    } catch (err) {
      alert(`Failed to interpret instruction: ${err.message}`)
    } finally {
      setInterpreting(false)
    }
  }

  const handleConfirmAction = async () => {
    if (!interpretedAction?.suggested_task) return
    try {
      const taskPayload = {
        objective: interpretedAction.suggested_task.title || interpretedAction.goal,
        target_component: interpretedAction.target,
        risk_level: 'MEDIUM',
        assigned_agent_id: interpretedAction.suggested_task.agent || 'agent-agy-01',
        inputs: {
          goal: interpretedAction.goal,
          method: interpretedAction.method,
          tool: interpretedAction.tool,
          scope: interpretedAction.target,
          ...interpretedAction.parameters,
        }
      }
      const res = await api.createTask(taskPayload)
      setDispatchMsg(`Task created successfully: ${res.task_id || 'new task'}. Navigating to Master Session...`)
      setTimeout(() => {
        onNavigate('master')
      }, 800)
    } catch (err) {
      alert(`Failed to dispatch action: ${err.message}`)
    }
  }

  if (loading) return <Spinner />
  if (!activeProject) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, padding: 40, textAlign: 'center' }}>
        <h2 style={{ fontSize: 20, color: 'var(--text-bright)', marginBottom: 12 }}>No Active Project Selected</h2>
        <p style={{ color: 'var(--text-muted)', marginBottom: 20, maxWidth: 500 }}>
          Create a new project or select an existing project from the top switcher to begin verification.
        </p>
      </div>
    )
  }

  const planVersion = summary?.verification_plans > 0 ? `v${summary.verification_plans}` : 'v1'
  const lastRunDisplay = lastRun?.run_id ? (lastRun.run_id.startsWith('run-') ? `RUN-${lastRun.run_id.slice(4, 7).toUpperCase()}` : lastRun.run_id) : 'RUN-001'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflowY: 'auto', padding: '24px 28px', background: 'var(--bg-base)' }}>
      {/* ── Page Header ──────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20, flexWrap: 'wrap', gap: 16 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 13, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', fontWeight: 600 }}>
              PROJECT WORKSPACE
            </span>
            <span className={`badge badge-${(activeProject?.status || 'READY').toLowerCase()}`} style={{ fontSize: 11 }}>
              {activeProject?.status || 'READY'}
            </span>
          </div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-bright)', margin: '4px 0 6px 0' }}>
            {activeProject?.name || 'Untitled Project'}
          </h1>
          <div className="mono text-muted" style={{ fontSize: 13 }}>
            Target: <strong>{activeProject?.target_directory}</strong>
          </div>
        </div>

        {/* ── Primary Action Buttons (Requirement 2) ─────────────────────────── */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            id="btn-open-verification-ws"
            className="btn btn-primary"
            style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}
            onClick={() => onNavigate('verification-plan')}
          >
            📋 Open Verification Workspace
          </button>
          <button
            id="btn-open-master-session"
            className="btn btn-secondary"
            style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}
            onClick={() => onNavigate('master')}
          >
            ⬡ Open Master Session
          </button>
          <button
            id="btn-create-task-home"
            className="btn btn-secondary"
            style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}
            onClick={() => {
              if (onOpenCreateTask) {
                onOpenCreateTask({ project_id: activeProject.project_id })
              } else {
                onNavigate('tasks')
              }
            }}
          >
            ⚡ Create Task
          </button>
          <button
            id="btn-view-results"
            className="btn btn-ghost"
            style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}
            onClick={() => onNavigate('evidence')}
          >
            ◈ View Results
          </button>
        </div>
      </div>

      {dispatchMsg && (
        <div style={{ padding: '10px 16px', background: 'var(--green-bg)', border: '1px solid var(--green-border)', color: 'var(--green)', fontSize: 13, borderRadius: 3, marginBottom: 16 }}>
          ✓ {dispatchMsg}
        </div>
      )}

      {/* ── High-Level Metric Tiles (Requirement 2 & 22) ───────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 14, marginBottom: 20 }}>
        <div className="stat-tile blue">
          <div className="stat-label">Target Status</div>
          <div className="stat-value" style={{ fontSize: 20, color: 'var(--blue)' }}>
            {activeProject?.status || 'READY'}
          </div>
          <div className="stat-sub">Isolated Workspace</div>
        </div>

        <div className="stat-tile">
          <div className="stat-label">Last Run</div>
          <div className="stat-value mono" style={{ fontSize: 20, color: 'var(--text-bright)' }}>
            {lastRunDisplay}
          </div>
          <div className="stat-sub">{lastRun?.status || 'Completed'}</div>
        </div>

        <div className="stat-tile green">
          <div className="stat-label">Plan Status</div>
          <div className="stat-value mono" style={{ fontSize: 20, color: 'var(--green)' }}>
            {planVersion}
          </div>
          <div className="stat-sub">Verified Architecture</div>
        </div>

        <div className="stat-tile">
          <div className="stat-label">Tasks</div>
          <div className="stat-value mono" style={{ fontSize: 22, color: summary?.tasks > 0 ? 'var(--blue)' : 'var(--text-muted)' }}>
            {summary ? summary.tasks : 0}
          </div>
          <div className="stat-sub">Executable Units</div>
        </div>

        <div className="stat-tile red">
          <div className="stat-label">Findings</div>
          <div className="stat-value mono" style={{ fontSize: 22, color: summary?.findings > 0 ? 'var(--red)' : 'var(--text-muted)' }}>
            {summary ? summary.findings : 0}
          </div>
          <div className="stat-sub">Traceable Vulnerabilities</div>
        </div>

        <div className="stat-tile amber">
          <div className="stat-label">Evidence</div>
          <div className="stat-value mono" style={{ fontSize: 22, color: summary?.evidence > 0 ? 'var(--amber)' : 'var(--text-muted)' }}>
            {summary ? summary.evidence : 0}
          </div>
          <div className="stat-sub">Deterministic Artifacts</div>
        </div>
      </div>

      {/* ── Natural Direction & Intent Console ────────────────────────────────── */}
      <div className="panel" style={{ marginBottom: 20 }}>
        <div className="panel-header" style={{ padding: '12px 18px', background: 'var(--bg-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)' }}>
              NATURAL USER INTENT & DIRECTION
            </span>
            <span className="badge badge-ready" style={{ fontSize: 10 }}>STRUCTURED DISPATCH</span>
          </div>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Instruction is deterministically analyzed into goal, method, tool, and agent
          </span>
        </div>
        <div className="panel-body" style={{ padding: '16px 18px' }}>
          <div style={{ display: 'flex', gap: 10, marginBottom: interpretedAction ? 14 : 0 }}>
            <input
              type="text"
              className="form-control"
              placeholder="e.g., Verify DPE command dispatch logic and check mailbox error handling"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleInterpret() }}
              style={{ flex: 1, fontSize: 13 }}
            />
            <button
              className="btn btn-primary"
              onClick={handleInterpret}
              disabled={interpreting || !instruction.trim()}
              style={{ minWidth: 160 }}
            >
              {interpreting ? 'Interpreting...' : 'Interpret Intent'}
            </button>
          </div>

          {interpretedAction && (
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 4, padding: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--blue)' }}>
                  Interpreted Task Configuration
                </span>
                <span className="badge badge-ready">READY FOR EXECUTION</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, fontSize: 12, marginBottom: 12 }}>
                <div><span className="text-muted">Goal:</span> <strong>{interpretedAction.goal}</strong></div>
                <div><span className="text-muted">Method:</span> <span className="mono">{interpretedAction.method}</span></div>
                <div><span className="text-muted">Tool:</span> <span className="mono">{interpretedAction.tool}</span></div>
                <div><span className="text-muted">Agent:</span> <span className="mono">{interpretedAction.suggested_task?.agent || 'AGY'}</span></div>
              </div>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                <button className="btn btn-ghost btn-sm" onClick={() => setInterpretedAction(null)}>Cancel</button>
                <button className="btn btn-primary btn-sm" onClick={handleConfirmAction}>Dispatch Task</button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Recent Activity Stream (Scrollable Panel) ────────────────────────── */}
      <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 220 }}>
        <div className="panel-header" style={{ padding: '12px 18px', background: 'var(--bg-subtle)' }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)' }}>
            RECENT PROJECT ACTIVITY & AUDIT TRAIL
          </span>
          <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {activity.length} recent events
          </span>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', maxHeight: '320px', padding: 0 }}>
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: 140 }}>Timestamp</th>
                <th style={{ width: 160 }}>Event Type</th>
                <th>Description</th>
                <th style={{ width: 100 }}>Task / Run</th>
              </tr>
            </thead>
            <tbody>
              {activity.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)' }}>
                    No recent events logged for this project. Launch a task or execute a verification plan to generate activity.
                  </td>
                </tr>
              ) : (
                activity.map((ev, i) => (
                  <tr key={ev.event_id || i}>
                    <td className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      {fmt(ev.timestamp)}
                    </td>
                    <td>
                      <span className="badge badge-neutral" style={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}>
                        {ev.event_type}
                      </span>
                    </td>
                    <td style={{ fontSize: 12 }}>
                      {ev.payload?.message || ev.payload?.title || ev.payload?.objective || JSON.stringify(ev.payload || {})}
                    </td>
                    <td className="mono" style={{ fontSize: 11, color: 'var(--blue)' }}>
                      {ev.task_id || ev.run_id || '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
