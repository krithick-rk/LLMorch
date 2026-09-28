/**
 * TasksPage.jsx — Engineering Job Queue
 * Section 12: Dense professional job table for SoC Verification & Security Tasks.
 * Columns: Status | Task | Bucket | Objective | Method | Tool | Agent | Progress | Budget | Duration | Updated
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import api from '../api'
import { StatusPill, Spinner, EmptyState, fmt, shortId, fmtElapsed } from './shared'

const BUCKETS = [
  'ALL',
  'RESET_AND_CLOCK',
  'POWER_AND_ENERGY',
  'DEBUG_AND_TRACE',
  'SIDE_CHANNEL_LEAKAGE',
  'FAULT_INJECTION',
  'INTERCONNECT_AND_FABRIC',
  'CRYPTO_ACCELERATOR',
  'SECURE_BOOT_AND_LIFECYCLE',
  'DMA_AND_BUS_MASTERING',
  'TEST_AND_MANUFACTURING',
  'ACCESS_CONTROL',
  'MEMORY_SUBSYSTEM',
  'INTERRUPT_HANDLING',
  'TAMPER_RESISTANCE',
  'PERIPHERAL_INTERFACES',
  'FIRMWARE_HARDWARE_INTERFACE',
  'CLOCK_DOMAIN_CROSSING',
  'REGISTER_ACCESS',
  'FORMAL_PROPERTY_VERIFICATION',
  'CODE_COVERAGE',
  'FUNCTIONAL_COVERAGE',
  'SECURITY_REGRESSION',
]

const METHODS = ['ALL', 'structural', 'simulation', 'formal', 'security', 'custom', 'auto']
const AGENTS = ['ALL', 'AGY', 'Codex', 'supervisor']
const TOOLS = ['ALL', 'Yosys', 'Verilator', 'Cocotb', 'Surfer', 'Sby', 'Z3']
const STATUSES = ['ALL', 'RUNNING', 'COMPLETED', 'FAILED', 'STOPPED', 'QUEUED']

export default function TasksPage({ refreshSignal, onNavigate, onOpenCreateTask, activeProject }) {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Filters
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [bucketFilter, setBucketFilter] = useState('ALL')
  const [agentFilter, setAgentFilter] = useState('ALL')
  const [toolFilter, setToolFilter] = useState('ALL')
  const [methodFilter, setMethodFilter] = useState('ALL')
  const [searchQuery, setSearchQuery] = useState('')
  const [sortBy, setSortBy] = useState('updated')
  const [sortAsc, setSortAsc] = useState(false)

  const loadTasks = useCallback(async () => {
    try {
      setLoading(true)
      const params = { limit: 250 }
      if (activeProject?.project_id) params.project_id = activeProject.project_id
      const res = await api.tasks(params)
      setTasks(res.items || [])
      setError(null)
    } catch (err) {
      setError(err.message || 'Failed to load task queue')
      setTasks([])
    } finally {
      setLoading(false)
    }
  }, [activeProject?.project_id])

  useEffect(() => {
    loadTasks()
    const iv = setInterval(loadTasks, 8000)
    return () => clearInterval(iv)
  }, [loadTasks, refreshSignal])

  const filteredTasks = useMemo(() => {
    return tasks.filter(t => {
      // Exclude synthetic test tasks unless explicitly searched
      if (!searchQuery && (t.task_id?.startsWith('test-task-') || t.task_id?.startsWith('task-test-'))) {
        return false
      }

      const st = (t.status || '').toUpperCase()
      if (statusFilter !== 'ALL') {
        if (statusFilter === 'RUNNING' && !['RUNNING', 'IN_PROGRESS', 'ANALYZING'].includes(st)) return false
        if (statusFilter === 'COMPLETED' && !['COMPLETED', 'SUCCEEDED', 'DONE'].includes(st)) return false
        if (statusFilter === 'FAILED' && !['FAILED', 'ERROR'].includes(st)) return false
        if (statusFilter === 'STOPPED' && !['STOPPED', 'CANCELLED', 'PAUSED'].includes(st)) return false
        if (statusFilter === 'QUEUED' && !['QUEUED', 'PENDING', 'PREPARING'].includes(st)) return false
      }

      // Check agent
      const agent = (t.assigned_agent_id || t.agent_id || 'AGY').toUpperCase()
      if (agentFilter !== 'ALL') {
        if (!agent.includes(agentFilter.toUpperCase())) return false
      }

      // Check inputs/properties
      const inp = typeof t.inputs === 'object' && t.inputs !== null ? t.inputs : {}
      const bucket = inp.bucket || inp.ontology_bucket || t.bucket || 'CLOCK_DOMAIN_CROSSING'
      if (bucketFilter !== 'ALL' && bucket.toUpperCase() !== bucketFilter.toUpperCase()) {
        return false
      }

      const method = inp.method || t.method || 'structural'
      if (methodFilter !== 'ALL' && method.toLowerCase() !== methodFilter.toLowerCase()) {
        return false
      }

      const tool = inp.tool || t.tool || 'Yosys'
      if (toolFilter !== 'ALL' && tool.toLowerCase() !== toolFilter.toLowerCase()) {
        return false
      }

      if (searchQuery) {
        const q = searchQuery.toLowerCase()
        const matchId = t.task_id?.toLowerCase().includes(q)
        const matchObj = t.objective?.toLowerCase().includes(q)
        const matchAgent = agent.toLowerCase().includes(q)
        if (!matchId && !matchObj && !matchAgent) return false
      }

      return true
    }).sort((a, b) => {
      const getVal = (item) => {
        if (sortBy === 'status') return item.status || ''
        if (sortBy === 'task') return item.task_id || ''
        if (sortBy === 'agent') return item.assigned_agent_id || ''
        return item.completed_at || item.started_at || item.created_at || ''
      }
      const valA = getVal(a)
      const valB = getVal(b)
      if (valA < valB) return sortAsc ? -1 : 1
      if (valA > valB) return sortAsc ? 1 : -1
      return 0
    })
  }, [tasks, statusFilter, bucketFilter, agentFilter, toolFilter, methodFilter, searchQuery, sortBy, sortAsc])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">
            <span>Execution Task Queue</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              ({filteredTasks.length} tasks)
            </span>
          </div>
          <div className="page-subtitle">
            Deterministic tool executions, verification jobs, and agent attempts
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <button className="btn btn-secondary btn-sm" onClick={loadTasks}>
            ↺ Refresh
          </button>
          <button
            id="btn-create-task-queue"
            className="btn btn-primary btn-sm"
            onClick={() => onOpenCreateTask ? onOpenCreateTask() : onNavigate('task-create')}
          >
            + Create Task
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div style={{
        padding: '8px 20px',
        background: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        flexWrap: 'wrap',
      }}>
        {/* Search */}
        <div style={{ minWidth: 200, flex: '1 1 200px' }}>
          <input
            className="form-control"
            placeholder="Filter by Task ID, Objective, Agent..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            style={{ fontSize: 12, padding: '4px 8px' }}
          />
        </div>

        {/* Status filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Status:
          </span>
          <select
            className="form-control"
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            style={{ width: 110, fontSize: 11, padding: '2px 6px' }}
          >
            {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        {/* Bucket filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Bucket:
          </span>
          <select
            className="form-control"
            value={bucketFilter}
            onChange={e => setBucketFilter(e.target.value)}
            style={{ width: 150, fontSize: 11, padding: '2px 6px' }}
          >
            {BUCKETS.map(b => (
              <option key={b} value={b}>{b.replace(/_/g, ' ')}</option>
            ))}
          </select>
        </div>

        {/* Agent filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Agent:
          </span>
          <select
            className="form-control"
            value={agentFilter}
            onChange={e => setAgentFilter(e.target.value)}
            style={{ width: 90, fontSize: 11, padding: '2px 6px' }}
          >
            {AGENTS.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>

        {/* Method filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Method:
          </span>
          <select
            className="form-control"
            value={methodFilter}
            onChange={e => setMethodFilter(e.target.value)}
            style={{ width: 110, fontSize: 11, padding: '2px 6px' }}
          >
            {METHODS.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>

        {/* Tool filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Tool:
          </span>
          <select
            className="form-control"
            value={toolFilter}
            onChange={e => setToolFilter(e.target.value)}
            style={{ width: 100, fontSize: 11, padding: '2px 6px' }}
          >
            {TOOLS.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>

        {/* Reset filters */}
        {(statusFilter !== 'ALL' || bucketFilter !== 'ALL' || agentFilter !== 'ALL' || toolFilter !== 'ALL' || methodFilter !== 'ALL' || searchQuery) && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => {
              setStatusFilter('ALL')
              setBucketFilter('ALL')
              setAgentFilter('ALL')
              setToolFilter('ALL')
              setMethodFilter('ALL')
              setSearchQuery('')
            }}
            style={{ fontSize: 11, color: 'var(--blue)' }}
          >
            Clear Filters
          </button>
        )}
      </div>

      {/* Main Table Area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
        {loading && tasks.length === 0 ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
            <Spinner size={24} />
          </div>
        ) : error ? (
          <div className="diag-box" style={{ maxWidth: 600 }}>
            <div className="diag-title">Task Queue Error</div>
            <div>{error}</div>
            <button className="btn btn-secondary btn-sm" onClick={loadTasks} style={{ width: 100 }}>
              ↺ Retry
            </button>
          </div>
        ) : filteredTasks.length === 0 ? (
          <EmptyState
            icon="📋"
            title="No matching tasks found"
            subtitle="Change filter criteria or create a new verification task."
          />
        ) : (
          <div className="data-table-wrap">
            <table className="data-table clickable">
              <thead>
                <tr>
                  <th style={{ width: 110 }}>Status</th>
                  <th style={{ width: 170 }}>Task ID</th>
                  <th style={{ width: 160 }}>Bucket</th>
                  <th>Objective</th>
                  <th style={{ width: 100 }}>Method</th>
                  <th style={{ width: 90 }}>Tool</th>
                  <th style={{ width: 80 }}>Agent</th>
                  <th style={{ width: 80 }}>Attempts</th>
                  <th style={{ width: 90 }}>Duration</th>
                  <th style={{ width: 120 }}>Updated</th>
                </tr>
              </thead>
              <tbody>
                {filteredTasks.map(t => {
                  const inp = typeof t.inputs === 'object' && t.inputs !== null ? t.inputs : {}
                  const bucket = inp.bucket || inp.ontology_bucket || t.bucket || 'CLOCK_DOMAIN_CROSSING'
                  const method = inp.method || t.method || 'structural'
                  const tool = inp.tool || inp.tool_name || t.tool || 'Yosys'
                  const agent = t.assigned_agent_id || t.agent_id || 'AGY'

                  // Compute duration
                  let dur = '—'
                  if (t.started_at) {
                    const startMs = new Date(t.started_at).getTime()
                    const endMs = t.completed_at ? new Date(t.completed_at).getTime() : Date.now()
                    dur = fmtElapsed(Math.max(0, (endMs - startMs) / 1000))
                  }

                  const updated = fmt(t.completed_at || t.started_at || t.created_at)

                  return (
                    <tr
                      key={t.task_id}
                      onClick={() => onNavigate('task', { entityId: t.task_id })}
                      title="Click to open execution details and console"
                    >
                      <td>
                        <StatusPill status={t.status} />
                      </td>
                      <td className="mono" style={{ fontWeight: 600 }}>
                        {t.task_id}
                      </td>
                      <td style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                        <span style={{
                          padding: '1px 4px',
                          background: 'var(--bg-subtle)',
                          border: '1px solid var(--border-dim)',
                          borderRadius: 2,
                          fontFamily: 'var(--font-mono)',
                          fontSize: 10,
                        }}>
                          {bucket.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="primary" style={{ maxWidth: 300 }} title={t.objective}>
                        <div className="truncate">{t.objective || '—'}</div>
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)' }}>
                        {method}
                      </td>
                      <td>
                        <span style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: 10,
                          padding: '1px 5px',
                          background: '#f1f5f9',
                          border: '1px solid #cbd5e1',
                          borderRadius: 2,
                          color: '#334155',
                          fontWeight: 500,
                        }}>
                          {tool}
                        </span>
                      </td>
                      <td>
                        <span style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: 10,
                          fontWeight: 600,
                          color: agent === 'AGY' ? 'var(--blue)' : 'var(--text-primary)'
                        }}>
                          {agent}
                        </span>
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                        {t.retry_count ? `#${t.retry_count + 1}` : '#1'}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)' }}>
                        {dur}
                      </td>
                      <td style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                        {updated}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
