import { useState, useEffect, useCallback, useRef } from 'react'
import api from './api'
import { useRealtimeEvents } from './useRealtimeEvents'
import './index.css'
import { AgentSwitchModal, ModelSwitchModal, RepoEstimateModal } from './components/Modals'
import { TokenDashboard } from './components/TokenDashboard'
import { TaskDAGVisualizer } from './components/TaskDAGVisualizer'
import { RepositoryGraphVisualizer } from './components/RepositoryGraphVisualizer'
import { SettingsPage } from './components/SettingsPage'

// ─── Helpers ─────────────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  const s = (status || 'unknown').toLowerCase().replace(/ /g, '_')
  return <span className={`badge badge-${s}`}>{status || '—'}</span>
}

function VerdictBadge({ verdict }) {
  if (!verdict) return <span className="text-muted">—</span>
  const v = verdict.toLowerCase()
  return <span className={`badge badge-${v}`}>{verdict}</span>
}

function Spinner() { return <div className="spinner" /> }

function EmptyState({ icon = '🔍', msg = 'No data found' }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon}</div>
      <p>{msg}</p>
    </div>
  )
}

function Mono({ children }) {
  return <span className="mono">{children}</span>
}

function fmt(dt) {
  if (!dt) return '—'
  try { return new Date(dt).toLocaleString() } catch { return dt }
}

function shortId(id) {
  if (!id) return '—'
  return id.length > 20 ? id.slice(0, 12) + '…' : id
}

// ─── Page: Run Overview ───────────────────────────────────────────────────────

function RunOverviewPage({ refreshSignal }) {
  const [tasks, setTasks] = useState(null)
  const [agents, setAgents] = useState(null)
  const [findings, setFindings] = useState(null)
  const [isEstimateModalOpen, setIsEstimateModalOpen] = useState(false)

  const load = useCallback(async () => {
    const [t, a, f] = await Promise.all([
      api.tasks({ limit: 200 }),
      api.agents({ limit: 50 }),
      api.findings({ limit: 200 }),
    ])
    setTasks(t); setAgents(a); setFindings(f)
  }, [])

  useEffect(() => { load() }, [load, refreshSignal])

  if (!tasks) return <Spinner />

  const byStatus = (s) => tasks.items.filter(t => t.status === s).length
  const agentAvail = agents ? agents.items.filter(a => a.health === 'AVAILABLE').length : 0
  const agentTotal = agents ? agents.total : 0
  const findingByState = (s) => findings ? findings.items.filter(f => f.state === s).length : 0

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">🚀 Run Overview</div>
          <div className="page-subtitle">Live investigation status, token accounting, and agent operations</div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-primary btn-sm" onClick={() => setIsEstimateModalOpen(true)}>
            📊 Estimate Repo Tokens
          </button>
          <button className="btn btn-secondary btn-sm" onClick={load}>↺ Refresh</button>
        </div>
      </div>

      {/* Authoritative Token Accounting & Budget Dashboard */}
      <TokenDashboard
        refreshSignal={refreshSignal}
        onOpenEstimateModal={() => setIsEstimateModalOpen(true)}
      />

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Total Tasks</div>
          <div className="stat-value">{tasks.total}</div>
          <div className="stat-sub">all time</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Running</div>
          <div className="stat-value text-blue">{byStatus('RUNNING')}</div>
          <div className="stat-sub">active now</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Completed</div>
          <div className="stat-value text-green">{byStatus('COMPLETED') + byStatus('SUCCEEDED')}</div>
          <div className="stat-sub">finished</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Failed</div>
          <div className="stat-value text-red">{byStatus('FAILED')}</div>
          <div className="stat-sub">need attention</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Agents</div>
          <div className="stat-value">{agentAvail} / {agentTotal}</div>
          <div className="stat-sub">available</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Findings</div>
          <div className="stat-value text-amber">{findings?.total || 0}</div>
          <div className="stat-sub">{findingByState('CONFIRMED')} confirmed</div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">⚡ Recent Tasks</div>
        </div>
        {tasks.items.length === 0
          ? <EmptyState msg="No tasks yet" />
          : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Task ID</th><th>Objective</th><th>Status</th><th>Agent</th><th>Created</th>
                </tr>
              </thead>
              <tbody>
                {tasks.items.slice(0, 20).map(t => (
                  <tr key={t.task_id}>
                    <td><Mono>{shortId(t.task_id)}</Mono></td>
                    <td style={{maxWidth:'260px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{t.objective}</td>
                    <td><StatusBadge status={t.status} /></td>
                    <td><Mono>{t.assigned_agent_id ? shortId(t.assigned_agent_id) : '—'}</Mono></td>
                    <td className="text-muted">{fmt(t.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        }
      </div>

      <RepoEstimateModal
        isOpen={isEstimateModalOpen}
        onClose={() => setIsEstimateModalOpen(false)}
        onBudgetSet={() => load()}
      />
    </div>
  )
}

// ─── Page: Task DAG ───────────────────────────────────────────────────────────

function TaskDAGPage({ refreshSignal }) {
  const [tasks, setTasks] = useState(null)
  const [agents, setAgents] = useState([])
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [taskSwitches, setTaskSwitches] = useState([])
  const [isSwitchModalOpen, setIsSwitchModalOpen] = useState(false)

  const load = useCallback(async () => {
    const [t, a] = await Promise.all([
      api.tasks({ limit: 100 }),
      api.agents({ limit: 50 }).catch(() => ({ items: [] })),
    ])
    setTasks(t)
    setAgents(a?.items || [])
  }, [])

  useEffect(() => { load() }, [load, refreshSignal])

  const selectTask = async (task) => {
    setSelected(task.task_id)
    const [d, sw] = await Promise.all([
      api.task(task.task_id),
      api.switches({ task_id: task.task_id }).catch(() => ({ items: [] })),
    ])
    setDetail(d)
    setTaskSwitches(sw?.items || [])
  }

  if (!tasks) return <Spinner />

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">🔗 Task DAG & Dependency Graph</div>
          <div className="page-subtitle">Interactive topological dependency visualization — click any task node to inspect</div>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={load}>↺ Refresh</button>
      </div>

      <div className="panel-row">
        <div style={{ flex: 2 }}>
          <TaskDAGVisualizer
            tasks={tasks.items || []}
            selectedTaskId={selected}
            onSelectTask={selectTask}
            onSwitchAgentClick={() => setIsSwitchModalOpen(true)}
          />
        </div>

        {detail && (
          <div style={{ flex: 1 }}>
            <div className="card">
              <div className="card-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div className="card-title">📋 Task Inspector</div>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => setIsSwitchModalOpen(true)}
                  >
                    ⇄ Switch Agent
                  </button>
                  <button className="btn btn-secondary btn-sm" onClick={() => { setSelected(null); setDetail(null) }}>✕</button>
                </div>
              </div>

              <dl style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '6px 12px', fontSize: '12px' }}>
                <dt className="text-muted">Task ID</dt><dd><Mono>{detail.task_id}</Mono></dd>
                <dt className="text-muted">Status</dt><dd><StatusBadge status={detail.status} /></dd>
                <dt className="text-muted">Assigned Agent</dt><dd><Mono>{detail.assigned_agent_id || '—'}</Mono></dd>
                <dt className="text-muted">Active Model</dt><dd><Mono>{detail.active_model_id || 'auto'}</Mono></dd>
                <dt className="text-muted">Risk Level</dt><dd>{detail.risk_level || '—'}</dd>
                <dt className="text-muted">Retries</dt><dd>{detail.retry_count}</dd>
                <dt className="text-muted">Dependencies</dt><dd>{(detail.dependencies || []).length} tasks</dd>
                <dt className="text-muted">Tokens Consumed</dt><dd><span className="text-blue font-semibold">{detail.tokens_consumed?.toLocaleString() || 0}</span></dd>
              </dl>

              <hr className="divider" />
              <div className="card-title mb-8">Objective</div>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{detail.objective}</p>

              {/* Switches for this task */}
              {taskSwitches.length > 0 && (
                <>
                  <hr className="divider" />
                  <div className="card-title mb-8">Agent Switch Audit Trail ({taskSwitches.length})</div>
                  {taskSwitches.map(sw => (
                    <div key={sw.switch_id} style={{ marginBottom: '6px', padding: '6px 10px', background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.2)', borderRadius: '4px', fontSize: '11px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span className={`badge badge-${(sw.switch_type || 'switch').toLowerCase()}`}>{sw.switch_type}</span>
                        <span className="text-muted">{fmt(sw.created_at)}</span>
                      </div>
                      <div style={{ marginTop: '4px' }}>
                        <Mono>{sw.previous_agent_id}</Mono> ➔ <Mono>{sw.new_agent_id}</Mono>
                      </div>
                      <div style={{ color: 'var(--text-secondary)', marginTop: '2px' }}>{sw.reason}</div>
                    </div>
                  ))}
                </>
              )}

              <hr className="divider" />
              <div className="card-title mb-8">Runs History ({(detail.runs || []).length})</div>
              {(detail.runs || []).map(r => (
                <div key={r.run_id} style={{ marginBottom: '6px', padding: '6px 8px', background: 'var(--bg-base)', borderRadius: '4px', fontSize: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Mono>{shortId(r.run_id)}</Mono>
                    <StatusBadge status={r.status} />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px', color: 'var(--text-muted)', fontSize: '11px' }}>
                    <span>Agent: {r.agent_id}</span>
                    {r.parent_run_id && <span>Parent: {shortId(r.parent_run_id)}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <AgentSwitchModal
        isOpen={isSwitchModalOpen}
        onClose={() => setIsSwitchModalOpen(false)}
        task={detail || (tasks.items || [])[0]}
        agents={agents}
        onSuccess={() => {
          load()
          if (detail) selectTask(detail)
        }}
      />
    </div>
  )
}

// ─── Page: Repository Graph ───────────────────────────────────────────────────

function RepositoryGraphPage({ refreshSignal }) {
  const [snapshots, setSnapshots] = useState(null)
  const [units, setUnits] = useState(null)
  const [selectedNode, setSelectedNode] = useState(null)
  const [surface, setSurface] = useState(null)

  const load = useCallback(async () => {
    const [s, u] = await Promise.all([
      api.repositories({ limit: 20 }),
      api.analysisUnits({ limit: 100 }),
    ])
    setSnapshots(s)
    setUnits(u)
  }, [])

  useEffect(() => { load() }, [load, refreshSignal])

  const handleSelectNode = async (node) => {
    setSelectedNode(node)
    if (node.type === 'analysis_unit' && node.data?.unit_id) {
      try {
        const sf = await api.securitySurface(node.data.unit_id)
        setSurface(sf)
      } catch {
        setSurface(null)
      }
    } else {
      setSurface(null)
    }
  }

  if (!snapshots || !units) return <Spinner />

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">🗺️ Security-Aware Repository Graph</div>
          <div className="page-subtitle">Interactive graph visualization of components, files, registers, and security boundaries</div>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={load}>↺ Refresh</button>
      </div>

      {/* Real Interactive Graph Visualizer */}
      <div className="card" style={{ marginBottom: '16px' }}>
        <RepositoryGraphVisualizer
          units={units.items || []}
          snapshots={snapshots.items || []}
          onSelectNode={handleSelectNode}
          selectedNodeId={selectedNode?.id}
        />
      </div>

      {/* Selected Node Details */}
      {selectedNode && (
        <div className="card" style={{ marginBottom: '16px', border: '1px solid var(--accent-blue)' }}>
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="card-title">
              🔍 Node Details: <Mono>{selectedNode.label}</Mono> ({selectedNode.type})
            </div>
            <button className="btn btn-secondary btn-sm" onClick={() => setSelectedNode(null)}>✕</button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
            {selectedNode.type === 'analysis_unit' && selectedNode.data && (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '6px 12px' }}>
                  <span className="text-muted">Domain:</span><span>{selectedNode.data.domain}</span>
                  <span className="text-muted">Unit Type:</span><span>{selectedNode.data.unit_type}</span>
                  <span className="text-muted">Criticality:</span><span>{selectedNode.data.security_critical ? '⚠️ High Security Critical' : 'Normal'}</span>
                  <span className="text-muted">Files ({selectedNode.data.files?.length || 0}):</span>
                  <div>
                    {(selectedNode.data.files || []).map(f => (
                      <div key={f}><Mono style={{ fontSize: '11px' }}>{f}</Mono></div>
                    ))}
                  </div>
                </div>

                {surface && (
                  <div className="stat-grid" style={{ gridTemplateColumns: '1fr 1fr 1fr 1fr', marginTop: '10px' }}>
                    <div className="stat-card"><div className="stat-label">Entry Points</div><div className="stat-value">{surface.entry_point_count}</div></div>
                    <div className="stat-card"><div className="stat-label">Assets</div><div className="stat-value">{surface.asset_count}</div></div>
                    <div className="stat-card"><div className="stat-label">Boundaries</div><div className="stat-value">{surface.boundary_count}</div></div>
                    <div className="stat-card"><div className="stat-label">Countermeasures</div><div className="stat-value">{surface.countermeasure_count}</div></div>
                  </div>
                )}
              </>
            )}

            {selectedNode.type === 'file' && (
              <div>Path: <Mono>{selectedNode.data?.path || selectedNode.label}</Mono></div>
            )}

            {selectedNode.type === 'register' && (
              <div>Register Address: <Mono>{selectedNode.data?.address || '0x40000000'}</Mono> (Memory-Mapped Hardware Register)</div>
            )}
          </div>
        </div>
      )}

      {/* Snapshot List Table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">📦 Repository Snapshots ({snapshots.total})</div>
        </div>
        {snapshots.items.length === 0 ? (
          <EmptyState icon="📁" msg="No repository snapshots yet. Run an investigation to populate." />
        ) : (
          <table className="data-table">
            <thead>
              <tr><th>Snapshot ID</th><th>Path</th><th>Commit</th><th>Family</th><th>Files</th><th>Created</th></tr>
            </thead>
            <tbody>
              {snapshots.items.map(s => (
                <tr key={s.snapshot_id}>
                  <td><Mono>{shortId(s.snapshot_id)}</Mono></td>
                  <td style={{ fontSize: '12px' }}>{s.repo_path}</td>
                  <td><Mono>{s.commit_hash ? s.commit_hash.slice(0, 8) : '—'}</Mono></td>
                  <td>{s.family || 'Hardware/Software'}</td>
                  <td>{s.total_files}</td>
                  <td className="text-muted">{fmt(s.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

// ─── Page: Agent Panel ────────────────────────────────────────────────────────

// ─── Page: Agent Panel ────────────────────────────────────────────────────────

function AgentPanelPage({ refreshSignal }) {
  const [agents, setAgents] = useState(null)
  const [tasks, setTasks] = useState([])
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [selectedTask, setSelectedTask] = useState(null)
  const [isSwitchModalOpen, setIsSwitchModalOpen] = useState(false)
  const [isModelModalOpen, setIsModelModalOpen] = useState(false)

  const load = useCallback(async () => {
    const [a, t] = await Promise.all([
      api.agents({ limit: 50 }),
      api.tasks({ limit: 100 }).catch(() => ({ items: [] })),
    ])
    setAgents(a)
    setTasks(t?.items || [])
  }, [])

  useEffect(() => { load() }, [load, refreshSignal])

  if (!agents) return <Spinner />

  const available = agents.items.filter(a => a.health === 'AVAILABLE' && a.enabled !== false).length

  const handleOpenSwitch = (agent) => {
    setSelectedAgent(agent)
    // Find active or recent task assigned to this agent
    const activeTask = tasks.find(t => t.assigned_agent_id === agent.agent_id && (t.status === 'RUNNING' || t.status === 'QUEUED')) ||
                       tasks.find(t => t.assigned_agent_id === agent.agent_id) ||
                       tasks[0] ||
                       { task_id: 'task-active', assigned_agent_id: agent.agent_id }
    setSelectedTask(activeTask)
    setIsSwitchModalOpen(true)
  }

  const handleOpenModel = (agent) => {
    setSelectedAgent(agent)
    setIsModelModalOpen(true)
  }

  const toggleAgentState = async (agent) => {
    try {
      const newEnabled = agent.enabled === false
      await api.updateSettings({
        agents: {
          allowed_agents: agents.items.map(a => a.agent_id === agent.agent_id ? { ...a, enabled: newEnabled } : a)
        }
      }).catch(() => null)
      agent.enabled = newEnabled
      setAgents({ ...agents })
    } catch {
      // Best effort toggle
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">🤖 Agent Panel & Control Plane</div>
          <div className="page-subtitle">
            {available} / {agents.total} agents available · Elastic 1–4 agent architecture · Dynamic model binding
          </div>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={load}>↺ Refresh</button>
      </div>

      {agents.items.length === 0 ? (
        <EmptyState icon="🤖" msg="No agents registered. Run an investigation to populate the registry." />
      ) : (
        <div className="grid-3">
          {agents.items.map(a => {
            const isAvail = a.health === 'AVAILABLE' && a.enabled !== false
            return (
              <div key={a.agent_id} className={`agent-card ${isAvail ? 'available' : 'unavailable'}`}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div className="agent-name">{a.agent_id}</div>
                    <div className="agent-provider">{a.provider} · {a.interface} · {a.role || 'general_analysis'}</div>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
                    <StatusBadge status={a.health} />
                    {a.executable === false ? (
                      <span className="badge badge-paused" style={{ fontSize: '10px' }} title={a.execution_disabled_reason || 'Execution Disabled'}>
                        EXECUTION DISABLED
                      </span>
                    ) : (
                      <span className="badge badge-running" style={{ fontSize: '10px' }}>
                        EXECUTABLE
                      </span>
                    )}
                  </div>
                </div>

                {/* Active Model & Supported Models */}
                <div style={{ padding: '8px 10px', background: 'var(--bg-card)', borderRadius: '6px', border: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Active Model:</span>
                    <Mono style={{ fontSize: '12px', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                      {a.current_model_id || a.model || 'auto'}
                    </Mono>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '3px' }}>
                    {(a.supported_models || []).slice(0, 3).map(m => (
                      <span key={m} className="cap-tag" style={{ fontSize: '9px' }}>{m}</span>
                    ))}
                    {(a.supported_models || []).length > 3 && (
                      <span className="cap-tag" style={{ fontSize: '9px' }}>+{a.supported_models.length - 3}</span>
                    )}
                  </div>
                </div>

                {/* Capabilities */}
                <div className="agent-caps">
                  {(a.capabilities || []).slice(0, 4).map(c => (
                    <span key={c} className="cap-tag">{c.replace(/_/g, ' ')}</span>
                  ))}
                  {(a.capabilities || []).length > 4 && (
                    <span className="cap-tag">+{a.capabilities.length - 4}</span>
                  )}
                </div>

                {/* Metrics: Switch & Failover Counters */}
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)', paddingTop: '4px', borderTop: '1px solid var(--border)' }}>
                  <span>Switches: <strong className="text-primary">{a.switch_count || 0}</strong></span>
                  <span>Failovers: <strong className="text-amber">{a.failover_count || 0}</strong></span>
                  <span>Limit: <strong className="text-primary">{a.concurrency_limit || 1}</strong></span>
                </div>

                {/* Action Buttons */}
                <div style={{ display: 'flex', gap: '6px', marginTop: '4px' }}>
                  <button
                    className={`btn ${a.executable === false ? 'btn-secondary' : 'btn-primary'} btn-sm`}
                    style={{ flex: 1, opacity: a.executable === false ? 0.6 : 1 }}
                    disabled={a.executable === false}
                    title={a.executable === false ? (a.execution_disabled_reason || 'Execution disabled by policy') : 'Switch assigned agent'}
                    onClick={() => handleOpenSwitch(a)}
                  >
                    ⇄ Switch
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    style={{ flex: 1 }}
                    onClick={() => handleOpenModel(a)}
                  >
                    ⚙ Model
                  </button>
                  <button
                    className={`btn btn-sm ${a.enabled !== false ? 'btn-secondary' : 'btn-danger'}`}
                    onClick={() => toggleAgentState(a)}
                    title={a.enabled !== false ? 'Disable agent' : 'Enable agent'}
                  >
                    {a.enabled !== false ? '●' : '○'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <div className="card" style={{ marginTop: '16px' }}>
        <div className="card-header">
          <div className="card-title">ℹ️ Elastic Agent Architecture Invariants</div>
        </div>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
          LLMorch supports <strong>1–4 agents elastically</strong> (1→1, 2→2, 3→3, 4→4, 0→BLOCKED).
          Agent identity is strictly isolated from model identity.
          When switches or failovers occur, tasks checkpoint progress to prevent duplicate execution, and parent lineage is preserved.
        </p>
      </div>

      <AgentSwitchModal
        isOpen={isSwitchModalOpen}
        onClose={() => setIsSwitchModalOpen(false)}
        task={selectedTask}
        agents={agents.items || []}
        onSuccess={() => load()}
      />

      <ModelSwitchModal
        isOpen={isModelModalOpen}
        onClose={() => setIsModelModalOpen(false)}
        agent={selectedAgent}
        onSuccess={() => load()}
      />
    </div>
  )
}

// ─── Page: Hypothesis Panel ───────────────────────────────────────────────────

function HypothesisPanelPage({ refreshSignal }) {
  const [findings, setFindings] = useState(null)
  const [selected, setSelected] = useState(null)
  const [evidence, setEvidence] = useState(null)
  const [filter, setFilter] = useState('ALL')

  const load = useCallback(async () => {
    const f = await api.findings({ limit: 100 })
    setFindings(f)
  }, [])

  useEffect(() => { load() }, [load, refreshSignal])

  const selectFinding = async (f) => {
    setSelected(f)
    if (f.evidence_ids && f.evidence_ids.length > 0) {
      const ev = await api.evidence({ finding_id: f.finding_id, limit: 10 })
      setEvidence(ev)
    } else {
      setEvidence(null)
    }
  }

  const states = ['ALL', 'OPEN', 'CONFIRMED', 'REJECTED', 'INCONCLUSIVE']
  const displayed = findings ? findings.items.filter(f => filter === 'ALL' || f.state === filter) : []

  if (!findings) return <Spinner />

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">💡 Hypothesis Panel</div>
          <div className="page-subtitle">Investigation hypotheses and supporting evidence</div>
        </div>
        <div className="flex gap-8">
          {states.map(s => (
            <button key={s} className={`btn btn-sm ${filter === s ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setFilter(s)}>{s}</button>
          ))}
        </div>
      </div>

      <div className="panel-row">
        <div style={{flex:2}}>
          {displayed.length === 0
            ? <EmptyState icon="💡" msg="No hypotheses match the current filter." />
            : displayed.map(f => (
              <div
                key={f.finding_id}
                className="card"
                style={{cursor:'pointer',borderColor:selected?.finding_id === f.finding_id ? 'var(--accent-blue)' : 'var(--border)',marginBottom:'8px'}}
                onClick={() => selectFinding(f)}
              >
                <div className="flex-center gap-8 mb-8">
                  <VerdictBadge verdict={f.state} />
                  <Mono style={{fontSize:'11px'}}>{shortId(f.finding_id)}</Mono>
                  {f.severity && <span className="text-amber">{f.severity}</span>}
                </div>
                <div style={{fontSize:'13px',color:'var(--text-primary)',lineHeight:'1.5'}}>
                  <span className="trust-llm">▶ HYPOTHESIS</span>{' '}
                  {f.hypothesis?.slice(0, 180)}
                </div>
                {f.task_id && <div className="text-muted mt-8" style={{fontSize:'11px'}}>Task: <Mono>{shortId(f.task_id)}</Mono></div>}
              </div>
            ))
          }
        </div>

        {selected && (
          <div style={{flex:1}}>
            <div className="card">
              <div className="card-header">
                <div className="card-title">Trust Levels</div>
                <button className="btn btn-secondary btn-sm" onClick={() => { setSelected(null); setEvidence(null) }}>✕</button>
              </div>
              <div style={{fontSize:'12px',lineHeight:'2'}}>
                <div><span className="trust-llm">■ HYPOTHESIS</span><span className="text-muted"> = Model/agent claim (not verified)</span></div>
                <div><span className="trust-observation">■ OBSERVATION</span><span className="text-muted"> = Deterministic tool result</span></div>
                <div><span className="trust-evidence">■ EVIDENCE</span><span className="text-muted"> = Recorded execution artifact</span></div>
                <div><span className="trust-critic">■ CRITIC</span><span className="text-muted"> = Challenge to hypothesis</span></div>
                <div><span className="trust-validation">■ VALIDATION</span><span className="text-muted"> = Authoritative decision</span></div>
              </div>
              <hr className="divider" />
              <div className="card-title mb-8">Current State</div>
              <VerdictBadge verdict={selected.state} />
              {evidence && evidence.items.length > 0 && (
                <>
                  <hr className="divider" />
                  <div className="card-title mb-8">Evidence ({evidence.total})</div>
                  {evidence.items.map(e => (
                    <div key={e.evidence_id} style={{padding:'6px 8px',background:'var(--bg-base)',borderRadius:'4px',marginBottom:'4px',fontSize:'12px'}}>
                      <span className="trust-evidence">■</span>{' '}
                      <Mono>{shortId(e.evidence_id)}</Mono>
                      <span className="text-muted" style={{marginLeft:'6px'}}>{e.source_tool || '—'}</span>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Page: Evidence Viewer ────────────────────────────────────────────────────

function EvidenceViewerPage({ refreshSignal }) {
  const [list, setList] = useState(null)
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)

  const load = useCallback(async () => {
    const e = await api.evidence({ limit: 50 })
    setList(e)
  }, [])

  useEffect(() => { load() }, [load, refreshSignal])

  const selectEvidence = async (e) => {
    setSelected(e.evidence_id)
    const d = await api.evidenceItem(e.evidence_id)
    setDetail(d)
  }

  if (!list) return <Spinner />

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">🔐 Evidence Viewer</div>
          <div className="page-subtitle">Execution artifacts — canonical hashes, provenance, sandbox traces</div>
        </div>
      </div>

      <div className="panel-row">
        <div style={{flex:2}}>
          <div className="card">
            <div className="card-header"><div className="card-title">Evidence Records</div></div>
            {list.items.length === 0
              ? <EmptyState icon="🔐" msg="No evidence records yet." />
              : (
                <table className="data-table">
                  <thead><tr><th>Evidence ID</th><th>Source Tool</th><th>Finding</th><th>Timestamp</th></tr></thead>
                  <tbody>
                    {list.items.map(e => (
                      <tr key={e.evidence_id} onClick={() => selectEvidence(e)} style={{cursor:'pointer'}}>
                        <td><Mono>{shortId(e.evidence_id)}</Mono></td>
                        <td>{e.source_tool || '—'}</td>
                        <td><Mono>{e.finding_id ? shortId(e.finding_id) : '—'}</Mono></td>
                        <td className="text-muted">{fmt(e.timestamp)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            }
          </div>
        </div>

        {detail && (
          <div style={{flex:1}}>
            <div className="card">
              <div className="card-header">
                <div className="card-title">Evidence Detail</div>
                <button className="btn btn-secondary btn-sm" onClick={() => { setSelected(null); setDetail(null) }}>✕</button>
              </div>
              <div style={{marginBottom:'12px'}}>
                <div className="card-title mb-8" style={{fontSize:'11px',color:'var(--text-muted)'}}>IDENTITY HASHES</div>
                <div className="hash-display"><span className="hash-label">Raw Hash</span><span>{detail.raw_hash || '—'}</span></div>
                <div className="hash-display"><span className="hash-label">Canonical Hash</span><span>{detail.canonical_hash || '—'}</span></div>
                <div className="hash-display"><span className="hash-label">Semantic ID</span><span>{detail.semantic_identity || '—'}</span></div>
              </div>
              <hr className="divider" />
              <dl style={{display:'grid',gridTemplateColumns:'110px 1fr',gap:'5px 10px',fontSize:'12px'}}>
                <dt className="text-muted">Tool</dt><dd>{detail.source_tool || '—'}</dd>
                <dt className="text-muted">Version</dt><dd>{detail.tool_version || '—'}</dd>
                <dt className="text-muted">Exit Code</dt><dd>{detail.exit_code ?? '—'}</dd>
                <dt className="text-muted">Sandbox</dt><dd><Mono>{detail.sandbox_id || '—'}</Mono></dd>
                <dt className="text-muted">Env FP</dt><dd><Mono style={{fontSize:'10px'}}>{detail.environment_fingerprint || '—'}</Mono></dd>
              </dl>
              {detail.command && (
                <>
                  <hr className="divider" />
                  <div className="card-title mb-8">Command</div>
                  <div className="evidence-stdout">{detail.command}</div>
                </>
              )}
              {detail.stdout && (
                <>
                  <div className="card-title mb-8" style={{marginTop:'8px'}}>stdout</div>
                  <div className="evidence-stdout">{detail.stdout.slice(0, 500)}</div>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Page: Timeline ───────────────────────────────────────────────────────────

function TimelinePage({ refreshSignal }) {
  const [events, setEvents] = useState(null)
  const [filter, setFilter] = useState('')

  const load = useCallback(async () => {
    const params = { limit: 100 }
    if (filter) params.event_type = filter
    const e = await api.timeline(params)
    setEvents(e)
  }, [filter])

  useEffect(() => { load() }, [load, refreshSignal])

  const EVENT_TYPES = [
    '', 'AGENT_SWITCH_COMPLETED', 'AGENT_FAILOVER_COMPLETED', 'MODEL_SWITCH_COMPLETED',
    'TOKEN_USAGE_RECORDED', 'TOKEN_BUDGET_EXHAUSTED', 'BUDGET_UPDATED',
    'TASK_CREATED', 'TASK_STARTED', 'TASK_COMPLETED', 'TASK_FAILED',
    'AGENT_STARTED', 'AGENT_FAILED', 'TOOL_EXECUTED', 'HYPOTHESIS_CREATED',
    'FINDING_STATE_CHANGED', 'VALIDATOR_COMPLETED', 'ANALYST_ACTION', 'FEEDBACK_SUBMITTED'
  ]

  if (!events) return <Spinner />

  const DOT_COLORS = {
    AGENT_SWITCH_COMPLETED: 'var(--accent-purple)',
    AGENT_FAILOVER_COMPLETED: 'var(--accent-amber)',
    MODEL_SWITCH_COMPLETED: 'var(--accent-cyan)',
    TOKEN_USAGE_RECORDED: 'var(--accent-blue)',
    TOKEN_BUDGET_EXHAUSTED: 'var(--accent-red)',
    BUDGET_UPDATED: 'var(--accent-green)',
    TASK_COMPLETED: 'var(--accent-green)', TASK_FAILED: 'var(--accent-red)',
    TASK_STARTED: 'var(--accent-blue)', AGENT_FAILED: 'var(--accent-red)',
    FINDING_STATE_CHANGED: 'var(--accent-amber)', ANALYST_ACTION: 'var(--accent-purple)',
    FEEDBACK_SUBMITTED: 'var(--accent-cyan)',
  }

  const getBadgeClass = (type) => {
    if (type.includes('SWITCH')) return 'badge-manual_switch'
    if (type.includes('FAILOVER')) return 'badge-failover'
    if (type.includes('TOKEN') || type.includes('BUDGET')) return 'badge-low'
    return 'badge-queued'
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">📅 Timeline & Audit Trail</div>
          <div className="page-subtitle">Chronological audit log of operations, switches, model changes, and events</div>
        </div>
        <select className="input" value={filter} onChange={e => setFilter(e.target.value)}>
          {EVENT_TYPES.map(t => <option key={t} value={t}>{t ? t.replace(/_/g, ' ') : '— All Events —'}</option>)}
        </select>
      </div>

      <div className="card">
        {events.items.length === 0
          ? <EmptyState icon="📅" msg="No events recorded yet." />
          : (
            <div className="timeline-list">
              {events.items.map(e => (
                <div key={e.event_id} className="timeline-entry">
                  <div className="timeline-dot" style={{background: DOT_COLORS[e.event_type] || 'var(--accent-blue)'}} />
                  <div style={{flex:1}}>
                    <div className="timeline-summary" style={{ fontWeight: e.event_type.includes('SWITCH') || e.event_type.includes('FAILOVER') ? 600 : 400 }}>
                      {e.summary || e.event_type}
                    </div>
                    <div className="timeline-meta">
                      {fmt(e.timestamp)}{e.actor ? ` · Actor: ${e.actor}` : ''}{e.entity_id ? ` · Ref: ${shortId(e.entity_id)}` : ''}
                    </div>
                  </div>
                  <span className={`badge ${getBadgeClass(e.event_type)}`} style={{fontSize:'10px',flexShrink:0}}>
                    {e.event_type}
                  </span>
                </div>
              ))}
            </div>
          )
        }
      </div>
    </div>
  )
}

// ─── Page: Finding Dossier ────────────────────────────────────────────────────

function FindingDossierPage({ refreshSignal }) {
  const [findings, setFindings] = useState(null)
  const [selected, setSelected] = useState(null)
  const [evidence, setEvidence] = useState(null)
  const [validations, setValidations] = useState(null)
  const [reproducers, setReproducers] = useState(null)
  const [feedbackLabel, setFeedbackLabel] = useState('')
  const [feedbackComment, setFeedbackComment] = useState('')
  const [feedbackMsg, setFeedbackMsg] = useState('')

  const load = useCallback(async () => {
    const f = await api.findings({ limit: 50 })
    setFindings(f)
  }, [])

  useEffect(() => { load() }, [load, refreshSignal])

  const openDossier = async (f) => {
    setSelected(f)
    setFeedbackMsg('')
    const [ev, val, rep] = await Promise.all([
      api.evidence({ finding_id: f.finding_id, limit: 10 }),
      api.validations({ finding_id: f.finding_id, limit: 5 }),
      api.reproducers({ finding_id: f.finding_id, limit: 5 }),
    ])
    setEvidence(ev); setValidations(val); setReproducers(rep)
  }

  const submitFeedback = async () => {
    if (!feedbackLabel) return
    try {
      const r = await api.feedback({ finding_id: selected.finding_id, label: feedbackLabel, comment: feedbackComment })
      setFeedbackMsg(r.message)
    } catch (e) {
      setFeedbackMsg('Error: ' + e.message)
    }
  }

  const FEEDBACK_LABELS = [
    'CONFIRMED','FALSE_POSITIVE','MISSED_VULNERABILITY','PARTIALLY_CORRECT',
    'WRONG_LOCALIZATION','WRONG_ATTACK_PATH','WRONG_SECURITY_PROPERTY',
    'INSUFFICIENT_EVIDENCE','CORRECT_REASONING_WRONG_CONCLUSION'
  ]

  const VERDICT_STYLES = {
    CONFIRMED: {background:'rgba(16,185,129,0.15)',color:'var(--accent-green)'},
    REJECTED:  {background:'rgba(239,68,68,0.15)', color:'var(--accent-red)'},
    INCONCLUSIVE: {background:'rgba(245,158,11,0.15)',color:'var(--accent-amber)'},
  }

  if (!findings) return <Spinner />

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">📂 Finding Dossier</div>
          <div className="page-subtitle">Complete finding records with evidence, validation, and reproducers</div>
        </div>
      </div>

      {!selected ? (
        <>
          {findings.items.length === 0
            ? <EmptyState icon="📂" msg="No findings yet." />
            : (
              <table className="data-table" style={{background:'var(--bg-card)',borderRadius:'var(--radius-lg)'}}>
                <thead><tr><th>Finding ID</th><th>Hypothesis</th><th>State</th><th>Severity</th><th>Created</th></tr></thead>
                <tbody>
                  {findings.items.map(f => (
                    <tr key={f.finding_id} onClick={() => openDossier(f)} style={{cursor:'pointer'}}>
                      <td><Mono>{shortId(f.finding_id)}</Mono></td>
                      <td style={{maxWidth:'300px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{f.hypothesis}</td>
                      <td><VerdictBadge verdict={f.state} /></td>
                      <td>{f.severity || '—'}</td>
                      <td className="text-muted">{fmt(f.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
          }
        </>
      ) : (
        <div>
          <div className="flex-center gap-8 mb-16">
            <button className="btn btn-secondary btn-sm" onClick={() => setSelected(null)}>← All Findings</button>
            <Mono>{selected.finding_id}</Mono>
          </div>

          <div className="panel-row">
            <div style={{flex:2}}>
              {/* Verdict */}
              <div className="dossier-verdict" style={VERDICT_STYLES[selected.state] || {background:'var(--bg-card)',color:'var(--text-primary)'}}>
                {selected.state}
              </div>
              <p style={{textAlign:'center',fontSize:'11px',color:'var(--text-muted)',marginBottom:'16px'}}>
                Final state is authoritative — determined by the validator, not the browser
              </p>

              <div className="card">
                <div className="card-header"><div className="card-title">💡 Hypothesis</div></div>
                <p style={{fontSize:'13px',color:'var(--text-secondary)',lineHeight:'1.6'}}>{selected.hypothesis}</p>
              </div>

              {/* Evidence */}
              {evidence && (
                <div className="card">
                  <div className="card-header"><div className="card-title">🔐 Evidence ({evidence.total})</div></div>
                  {evidence.items.length === 0
                    ? <div className="text-muted">No evidence records linked.</div>
                    : evidence.items.map(e => (
                      <div key={e.evidence_id} className="evidence-block">
                        <div className="flex-center gap-8 mb-8">
                          <span className="trust-evidence">■ EVIDENCE</span>
                          <Mono>{shortId(e.evidence_id)}</Mono>
                          <span className="text-muted">{e.source_tool || '—'}</span>
                        </div>
                        <div className="hash-display"><span className="hash-label">Canonical</span>{e.canonical_hash || '—'}</div>
                      </div>
                    ))
                  }
                </div>
              )}

              {/* Reproducers */}
              {reproducers && reproducers.items.length > 0 && (
                <div className="card">
                  <div className="card-header"><div className="card-title">🔄 Reproducers ({reproducers.total})</div></div>
                  {reproducers.items.map(r => (
                    <div key={r.reproducer_id} style={{marginBottom:'6px',padding:'8px',background:'var(--bg-base)',borderRadius:'4px',fontSize:'12px'}}>
                      <Mono>{shortId(r.reproducer_id)}</Mono>
                      <StatusBadge status={r.status} />
                      {r.manifest_hash && <div className="text-muted" style={{marginTop:'4px',fontSize:'11px'}}>Manifest: {r.manifest_hash.slice(0,16)}…</div>}
                    </div>
                  ))}
                </div>
              )}

              {/* Validations */}
              {validations && validations.items.length > 0 && (
                <div className="card">
                  <div className="card-header"><div className="card-title">✅ Validations ({validations.total})</div></div>
                  {validations.items.map(v => (
                    <div key={v.validation_id} style={{marginBottom:'6px',padding:'8px',background:'var(--bg-base)',borderRadius:'4px',fontSize:'12px'}}>
                      <span className="trust-validation">■ VALIDATION</span>{' '}
                      <VerdictBadge verdict={v.verdict} />{' '}
                      <span className="text-muted">{v.validator_name || '—'} · {v.replay_count} replays · {v.determinism || '—'}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Analyst feedback */}
            <div style={{flex:1}}>
              <div className="card">
                <div className="card-header"><div className="card-title">🗣️ Analyst Feedback</div></div>
                <p style={{fontSize:'12px',color:'var(--text-muted)',marginBottom:'10px'}}>
                  Submit structured feedback. Does not modify the finding state — creates an auditable record only.
                </p>
                <select className="input" style={{width:'100%',marginBottom:'8px'}} value={feedbackLabel} onChange={e => setFeedbackLabel(e.target.value)}>
                  <option value="">— Select label —</option>
                  {FEEDBACK_LABELS.map(l => <option key={l} value={l}>{l.replace(/_/g,' ')}</option>)}
                </select>
                <textarea
                  className="input"
                  placeholder="Optional comment…"
                  value={feedbackComment}
                  onChange={e => setFeedbackComment(e.target.value)}
                  style={{width:'100%',minHeight:'80px',resize:'vertical',marginBottom:'8px'}}
                />
                <button className="btn btn-primary" style={{width:'100%'}} onClick={submitFeedback} disabled={!feedbackLabel}>Submit Feedback</button>
                {feedbackMsg && <div style={{marginTop:'8px',fontSize:'12px',color:'var(--accent-green)'}}>{feedbackMsg}</div>}
              </div>

              <div className="card">
                <div className="card-header"><div className="card-title">ℹ️ Trust Model</div></div>
                <div style={{fontSize:'12px',lineHeight:'2'}}>
                  <div><span className="trust-llm">HYPOTHESIS</span> = agent claim</div>
                  <div><span className="trust-observation">OBSERVATION</span> = tool result</div>
                  <div><span className="trust-evidence">EVIDENCE</span> = execution artifact</div>
                  <div><span className="trust-critic">CRITIC</span> = challenge</div>
                  <div><span className="trust-validation">VALIDATION</span> = authoritative</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Page: Global Intelligence ────────────────────────────────────────────────

function GlobalIntelligencePage({ refreshSignal }) {
  const [patterns, setPatterns] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    try {
      // Global patterns come from the timeline events with relevant types
      const t = await api.timeline({ event_type: 'HYPOTHESIS_CREATED', limit: 50 })
      setPatterns(t)
    } catch (e) {
      setError(e.message)
    }
  }, [])

  useEffect(() => { load() }, [load, refreshSignal])

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">🌐 Global Intelligence</div>
          <div className="page-subtitle">Historical patterns, security invariants, and investigation guidance</div>
        </div>
      </div>

      <div className="card" style={{background:'rgba(245,158,11,0.05)',borderColor:'rgba(245,158,11,0.2)'}}>
        <div className="card-title text-amber">⚠ Intelligence Trust Notice</div>
        <p style={{fontSize:'13px',color:'var(--text-secondary)',marginTop:'8px',lineHeight:'1.6'}}>
          Retrieved intelligence is <strong>candidate guidance</strong>, not confirmed truth.
          Always distinguish: <span className="text-muted">historical · generalized · candidate</span> vs.{' '}
          <span className="trust-validation">validated evidence</span>.
        </p>
      </div>

      {error && <div className="card" style={{color:'var(--accent-red)'}}>{error}</div>}
      {!patterns && !error && <Spinner />}
      {patterns && (
        <div className="card">
          <div className="card-header"><div className="card-title">📊 Recent Hypothesis Events ({patterns.total})</div></div>
          {patterns.items.length === 0
            ? <EmptyState icon="🌐" msg="No intelligence data yet. Run investigations to build the knowledge base." />
            : (
              <div className="timeline-list">
                {patterns.items.map(e => (
                  <div key={e.event_id} className="timeline-entry">
                    <div className="timeline-dot" style={{background:'var(--accent-purple)'}} />
                    <div>
                      <div className="timeline-summary">{e.summary}</div>
                      <div className="timeline-meta">{fmt(e.timestamp)}</div>
                    </div>
                    <span className="badge" style={{background:'rgba(139,92,246,0.15)',color:'#a78bfa',border:'1px solid rgba(139,92,246,0.3)',fontSize:'10px'}}>
                      CANDIDATE GUIDANCE
                    </span>
                  </div>
                ))}
              </div>
            )
          }
        </div>
      )}
    </div>
  )
}

// ─── App Shell ────────────────────────────────────────────────────────────────

const PAGES = [
  { id: 'overview',    label: 'Run Overview',        icon: '🚀' },
  { id: 'dag',         label: 'Task DAG',            icon: '🔗' },
  { id: 'repo',        label: 'Repository Graph',    icon: '🗺️' },
  { id: 'agents',      label: 'Agent Panel',         icon: '🤖' },
  { id: 'hypothesis',  label: 'Hypotheses',          icon: '💡' },
  { id: 'evidence',    label: 'Evidence Viewer',     icon: '🔐' },
  { id: 'timeline',    label: 'Timeline',            icon: '📅' },
  { id: 'dossier',     label: 'Finding Dossier',     icon: '📂' },
  { id: 'intel',       label: 'Global Intelligence', icon: '🌐' },
  { id: 'settings',    label: 'Settings & Policy',   icon: '⚙️' },
]

export default function App() {
  const [page, setPage] = useState('overview')
  const [refreshSignal, setRefreshSignal] = useState(0)
  const [wsConnected, setWsConnected] = useState(false)
  const [eventLog, setEventLog] = useState([])

  const handleEvent = useCallback((evt) => {
    if (evt.type === 'RESYNC' || evt.event_type === 'RESYNC') {
      // Client must refresh authoritative state from API
      setRefreshSignal(s => s + 1)
      return
    }
    if (evt.type === 'GAP_DETECTED') {
      // Sequence gap — refresh
      setRefreshSignal(s => s + 1)
      return
    }
    setEventLog(prev => [evt, ...prev].slice(0, 50))
    // Trigger refresh on task/finding state changes
    if (['TASK_STATUS_CHANGED','FINDING_STATE_CHANGED','VALIDATOR_COMPLETED','ANALYST_ACTION','AGENT_SWITCH_COMPLETED','AGENT_FAILOVER_COMPLETED','MODEL_SWITCH_COMPLETED','TOKEN_USAGE_RECORDED','TOKEN_BUDGET_EXHAUSTED'].includes(evt.event_type)) {
      setRefreshSignal(s => s + 1)
    }
  }, [])

  const isConnected = useRealtimeEvents(handleEvent)

  useEffect(() => { setWsConnected(isConnected) }, [isConnected])

  const renderPage = () => {
    const props = { refreshSignal }
    switch (page) {
      case 'overview':   return <RunOverviewPage {...props} />
      case 'dag':        return <TaskDAGPage {...props} />
      case 'repo':       return <RepositoryGraphPage {...props} />
      case 'agents':     return <AgentPanelPage {...props} />
      case 'hypothesis': return <HypothesisPanelPage {...props} />
      case 'evidence':   return <EvidenceViewerPage {...props} />
      case 'timeline':   return <TimelinePage {...props} />
      case 'dossier':    return <FindingDossierPage {...props} />
      case 'intel':      return <GlobalIntelligencePage {...props} />
      case 'settings':   return <SettingsPage {...props} />
      default:           return <RunOverviewPage {...props} />
    }
  }

  return (
    <div id="root">
      {/* Header */}
      <header className="app-header">
        <div className="logo">
          🔬 LLMorch <span>Analyst Console v9.1</span>
        </div>
        <div className="header-status">
          {eventLog.length > 0 && (
            <span style={{fontSize:'11px',color:'var(--text-muted)'}}>
              {eventLog[0].event_type || 'event'}
            </span>
          )}
          <div className={`status-dot ${wsConnected ? '' : 'offline'}`} title={wsConnected ? 'Realtime connected' : 'Realtime disconnected'} />
          <span style={{fontSize:'11px',color:'var(--text-secondary)'}}>
            {wsConnected ? 'Live' : 'Reconnecting…'}
          </span>
        </div>
      </header>

      <div className="app-body">
        {/* Sidebar */}
        <nav className="sidebar">
          <div className="sidebar-section">
            <div className="sidebar-label">Investigation</div>
            {PAGES.slice(0,4).map(p => (
              <div key={p.id} className={`nav-item ${page === p.id ? 'active' : ''}`} onClick={() => setPage(p.id)}>
                <span className="icon">{p.icon}</span>
                {p.label}
              </div>
            ))}
          </div>
          <div className="sidebar-section">
            <div className="sidebar-label">Analysis</div>
            {PAGES.slice(4,8).map(p => (
              <div key={p.id} className={`nav-item ${page === p.id ? 'active' : ''}`} onClick={() => setPage(p.id)}>
                <span className="icon">{p.icon}</span>
                {p.label}
              </div>
            ))}
          </div>
          <div className="sidebar-section">
            <div className="sidebar-label">Intelligence</div>
            {PAGES.slice(8,9).map(p => (
              <div key={p.id} className={`nav-item ${page === p.id ? 'active' : ''}`} onClick={() => setPage(p.id)}>
                <span className="icon">{p.icon}</span>
                {p.label}
              </div>
            ))}
          </div>
          <div className="sidebar-section">
            <div className="sidebar-label">Control Plane</div>
            <div className={`nav-item ${page === 'settings' ? 'active' : ''}`} onClick={() => setPage('settings')}>
              <span className="icon">⚙️</span>
              Settings & Policy
            </div>
          </div>
        </nav>

        {/* Main content */}
        <main className="main-content">
          {renderPage()}
        </main>
      </div>
    </div>
  )
}
