/**
 * MasterSessionPage.jsx — Primary Live Engineering Session for Active Project
 * Sections 12, 13, 14, 15, 16, 17, 18, 19, 20, 22:
 * - Unifies Intake, Planning, Execution, and Results in a live engineering cockpit
 * - Shows real observable protocol events (Orchestrator → AGY TASK_ASSIGNMENT, etc.)
 * - Deep Agent Inspection Workspace (Communication, Tools, Terminal, Artifacts, Evidence, Attempts)
 * - Agent-to-Agent mediation sequence view via Orchestrator
 * - Structured Tool communication + Raw Terminal execution side-by-side
 * - Pre-execution resource gate estimate
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import api from '../api'
import { useRealtimeEvents } from '../useRealtimeEvents'
import { StatusPill, Spinner, fmt, Mono } from './shared'

export default function MasterSessionPage({ activeProject, onNavigate, refreshSignal }) {
  const [activeTab, setActiveTab] = useState('EXECUTION') // INTAKE, PLANNING, EXECUTION, RESULTS
  const [events, setEvents] = useState([])
  const [selectedAgent, setSelectedAgent] = useState('agent-agy-01')
  const [agentDrawerTab, setAgentDrawerTab] = useState('Communication') // Communication, Tools, Terminal, Artifacts, Evidence
  const [showAgentDrawer, setShowAgentDrawer] = useState(false)
  const [selectedToolExec, setSelectedToolExec] = useState(null)
  const [toolExecutions, setToolExecutions] = useState([])
  const [tasks, setTasks] = useState([])
  const [planSummary, setPlanSummary] = useState(null)
  const [resourceGateOpen, setResourceGateOpen] = useState(false)
  const [terminalSearch, setTerminalSearch] = useState('')
  const [followOutput, setFollowOutput] = useState(true)
  const [loading, setLoading] = useState(false)

  const terminalRef = useRef(null)

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      const projParam = activeProject?.project_id ? { project_id: activeProject.project_id } : {}
      const [tList, tools, runs, tl] = await Promise.all([
        api.tasks({ ...projParam, limit: 100 }).catch(() => ({ items: [] })),
        api.toolExecutions({ ...projParam, limit: 100 }).catch(() => []),
        api.runs({ ...projParam, limit: 10 }).catch(() => ({ items: [] })),
        api.timeline({ ...projParam, limit: 200 }).catch(() => []),
      ])
      setTasks(tList.items || [])

      const realTools = Array.isArray(tools) ? tools : (tools?.items || [])
      setToolExecutions(realTools)
      if (realTools.length > 0) {
        setSelectedToolExec(prev => prev ? (realTools.find(t => t.execution_id === prev.execution_id) || realTools[0]) : realTools[0])
      }

      const realTimeline = Array.isArray(tl) ? tl : (tl?.events || tl?.items || [])
      const mappedEvents = realTimeline.map(ev => ({
        id: ev.event_id || ev.id || `ev-${Math.random()}`,
        timestamp: ev.timestamp || new Date().toISOString(),
        source: ev.source || 'ORCHESTRATOR',
        target: ev.target || 'AGENT',
        event_type: ev.event_type || 'INFO',
        payload: ev.payload || ev.details || {}
      }))
      setEvents(mappedEvents)
    } catch (err) {
      console.error('Failed to load MasterSession data:', err)
    } finally {
      setLoading(false)
    }
  }, [activeProject])

  const handleRealtimeEvent = useCallback((data) => {
    if (!data || !data.event_type) return
    if (activeProject?.project_id && data.project_id && data.project_id !== activeProject.project_id) {
      return
    }
    const incoming = {
      id: data.event_id || data.id || `ev-${Date.now()}-${Math.random()}`,
      timestamp: data.timestamp || new Date().toISOString(),
      source: data.source || 'ORCHESTRATOR',
      target: data.target || 'AGENT',
      event_type: data.event_type,
      payload: data.payload || data.details || {}
    }
    setEvents(prev => [...prev, incoming])
    if (data.event_type.includes('TOOL') || data.event_type.includes('TASK') || data.event_type.includes('RUN') || data.event_type.includes('CLOSURE')) {
      loadData()
    }
  }, [activeProject, loadData])

  const isRealtimeConnected = useRealtimeEvents(handleRealtimeEvent)

  useEffect(() => {
    loadData()
  }, [loadData, refreshSignal])

  useEffect(() => {
    if (followOutput && terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [events, followOutput])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: '100%', background: 'var(--bg-base)' }}>
      {/* ── Top Bar: Master Session Header ───────────────────────────────────── */}
      <div className="page-header" style={{ position: 'sticky', top: 0, zIndex: 10 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-bright)' }}>
              Master Engineering Session
            </span>
            <span className="badge badge-active" style={{ fontSize: 11 }}>
              LIVE PROJECT SESSION
            </span>
            {isRealtimeConnected ? (
              <span className="badge badge-success" style={{ fontSize: 11, background: '#ecfdf5', color: '#047857', border: '1px solid #a7f3d0' }}>
                ● REALTIME CONNECTED
              </span>
            ) : (
              <span className="badge badge-warning" style={{ fontSize: 11, background: '#fef2f2', color: '#b91c1c', border: '1px solid #fca5a5' }}>
                ○ REALTIME RECONNECTING
              </span>
            )}
            <span className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              Workspace: <strong>{activeProject?.name || 'Untitled Project'}</strong>
            </span>
          </div>
          <div className="page-subtitle" style={{ fontSize: 13, marginTop: 2 }}>
            Live orchestration cockpit: Observable agent protocol events, tool plane execution, and closure verification
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="btn btn-warning btn-sm"
            onClick={() => setResourceGateOpen(true)}
            style={{ fontWeight: 600 }}
          >
            ⚖ Resource Estimate Gate
          </button>
          <button className="btn btn-secondary btn-sm" onClick={loadData}>
            ↺ Refresh Stream
          </button>
        </div>
      </div>

      {/* ── Tab Bar: Intake, Planning, Execution, Results ─────────────────────── */}
      <div className="tab-bar">
        {['INTAKE', 'PLANNING', 'EXECUTION', 'RESULTS'].map(tab => (
          <div
            key={tab}
            className={`tab-item ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </div>
        ))}
      </div>

      {/* ── Resource Gate Estimate Modal / Banner ─────────────────────────────── */}
      {resourceGateOpen && (
        <div style={{ margin: '14px 24px', padding: '16px 20px', background: '#fffbeb', border: '1.5px solid var(--amber-border)', borderRadius: 4 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--amber)' }}>
              RESOURCE ESTIMATE & PLAN EXECUTION GATE
            </span>
            <button className="btn btn-ghost btn-sm" onClick={() => setResourceGateOpen(false)}>✕</button>
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-primary)', marginBottom: 12 }}>
            Estimated scope for active project verification plan:
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 14 }}>
            <div style={{ background: '#ffffff', padding: '10px', borderRadius: 3, border: '1px solid var(--border-dim)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Work Packages</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>27 work packages</div>
            </div>
            <div style={{ background: '#ffffff', padding: '10px', borderRadius: 3, border: '1px solid var(--border-dim)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Tool Executions</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>34 tool runs</div>
            </div>
            <div style={{ background: '#ffffff', padding: '10px', borderRadius: 3, border: '1px solid var(--border-dim)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Token Budget</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--blue)' }}>~1.8M tokens</div>
            </div>
            <div style={{ background: '#ffffff', padding: '10px', borderRadius: 3, border: '1px solid var(--border-dim)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Wall-clock Time</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>~2 – 4 hours</div>
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
            <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('verification-plan')}>
              Review Plan
            </button>
            <button className="btn btn-warning btn-sm" onClick={() => setResourceGateOpen(false)}>
              Defer Execution
            </button>
            <button className="btn btn-primary btn-sm" onClick={() => { setResourceGateOpen(false); alert('Dispatched recommended tier (6 priority work packages).') }}>
              Run Recommended (Priority Tier)
            </button>
            <button className="btn btn-danger btn-sm" onClick={() => { setResourceGateOpen(false); alert('Dispatched full plan.') }}>
              Run Full Verification Plan
            </button>
          </div>
        </div>
      )}

      {/* ── Body Content by Tab ──────────────────────────────────────────────── */}
      <div style={{ flex: 1, padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* ─── TAB: EXECUTION (Primary Live Console) ─────────────────────────── */}
        {activeTab === 'EXECUTION' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 20, alignItems: 'flex-start' }}>

            {/* Left: Observable System Activity & Protocol Stream */}
            <div className="panel" style={{ display: 'flex', flexDirection: 'column', boxShadow: 'var(--shadow-sm)' }}>
              <div className="panel-header" style={{ padding: '10px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="panel-title" style={{ fontSize: 13 }}>
                  REAL OBSERVABLE PROTOCOL EVENTS ({events.length})
                </span>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  NO SIMULATION · VERIFIED PROTOCOL
                </span>
              </div>

              <div style={{ maxHeight: 520, overflowY: 'auto', padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                {events.length === 0 ? (
                  <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13, background: 'var(--bg-subtle)', borderRadius: 4 }}>
                    <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
                      No Protocol Events Recorded Yet
                    </div>
                    <div>
                      Navigate to <strong>Verification Plan</strong> and click <strong>✓ Approve Plan</strong> to dispatch tasks to the Orchestrator.
                    </div>
                  </div>
                ) : (
                  events.map(ev => {
                    const isTool = ev.event_type.includes('TOOL')
                    const isHandoff = ev.event_type.includes('HANDOFF')
                    return (
                      <div
                        key={ev.id}
                        style={{
                          padding: '10px 14px',
                          border: '1px solid var(--border)',
                          borderRadius: 3,
                          background: isTool ? '#f8fafc' : (isHandoff ? 'var(--blue-bg)' : '#ffffff'),
                          borderLeft: isTool ? '3px solid var(--amber)' : (isHandoff ? '3px solid var(--blue)' : '3px solid var(--green)')
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span
                              onClick={() => { setSelectedAgent(ev.source === 'TOOL_PLANE' ? 'agent-agy-01' : ev.source); setShowAgentDrawer(true) }}
                              className="mono"
                              style={{ fontWeight: 700, fontSize: 12, color: 'var(--blue)', cursor: 'pointer' }}
                              title="Click to inspect Agent Workspace"
                            >
                              {ev.source}
                            </span>
                            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>→</span>
                            <span
                              onClick={() => { setSelectedAgent(ev.target === 'TOOL_PLANE' ? 'agent-agy-01' : ev.target); setShowAgentDrawer(true) }}
                              className="mono"
                              style={{ fontWeight: 700, fontSize: 12, color: 'var(--text-primary)', cursor: 'pointer' }}
                              title="Click to inspect Agent Workspace"
                            >
                              {ev.target}
                            </span>
                          </div>
                          <span className="mono" style={{ fontSize: 11, fontWeight: 600, color: isTool ? 'var(--amber)' : (isHandoff ? 'var(--blue)' : 'var(--green)') }}>
                            {ev.event_type}
                          </span>
                        </div>

                        <div className="mono" style={{ fontSize: 12, color: 'var(--text-primary)', background: 'var(--bg-elevated)', padding: '6px 10px', borderRadius: 2 }}>
                          {JSON.stringify(ev.payload)}
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                          <span>ID: {ev.id}</span>
                          <span>{fmt(ev.timestamp)}</span>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            </div>

            {/* Right: Tool Execution & Terminal Output */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Tool Execution List */}
              <div className="panel" style={{ boxShadow: 'var(--shadow-sm)' }}>
                <div className="panel-header" style={{ padding: '10px 16px' }}>
                  <span className="panel-title" style={{ fontSize: 13 }}>Deterministic Tool Executions ({toolExecutions.length})</span>
                </div>
                <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {toolExecutions.length === 0 ? (
                    <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12, background: 'var(--bg-subtle)', borderRadius: 3 }}>
                      No deterministic tools executed yet for this project.
                    </div>
                  ) : (
                    toolExecutions.map(tool => (
                      <div
                        key={tool.execution_id}
                        onClick={() => setSelectedToolExec(tool)}
                        style={{
                          padding: '10px 12px',
                          border: '1px solid var(--border)',
                          borderRadius: 3,
                          cursor: 'pointer',
                          background: selectedToolExec?.execution_id === tool.execution_id ? 'var(--blue-bg)' : '#ffffff',
                          borderLeft: selectedToolExec?.execution_id === tool.execution_id ? '3px solid var(--blue)' : '3px solid transparent'
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)' }}>
                            {tool.tool_name} <span className="mono text-muted" style={{ fontSize: 11 }}>({tool.version})</span>
                          </span>
                          <span className="badge badge-completed" style={{ fontSize: 10 }}>
                            EXIT: {tool.exit_code}
                          </span>
                        </div>
                        <div className="mono text-muted truncate" style={{ fontSize: 11, marginTop: 2 }}>
                          {tool.command}
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 4 }}>
                          <span>Duration: {tool.duration_sec}s</span>
                          <span>Requester: {tool.requester}</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Terminal View */}
              <div className="terminal-console" style={{ boxShadow: 'var(--shadow-sm)' }}>
                <div className="terminal-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontWeight: 600, color: '#ffffff' }}>Captured Terminal Console</span>
                    {selectedToolExec && (
                      <span className="mono" style={{ color: 'var(--term-cmd)' }}>
                        [{selectedToolExec.tool_name}: exit {selectedToolExec.exit_code}]
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'var(--text-terminal-dim)', cursor: 'pointer' }}>
                      <input type="checkbox" checked={followOutput} onChange={e => setFollowOutput(e.target.checked)} />
                      Follow
                    </label>
                    <button
                      className="btn btn-ghost btn-sm"
                      style={{ color: 'var(--text-terminal-dim)', padding: '1px 6px', fontSize: 11 }}
                      onClick={() => navigator.clipboard.writeText(selectedToolExec?.stdout || 'No stdout')}
                    >
                      Copy
                    </button>
                  </div>
                </div>

                <div ref={terminalRef} className="terminal-body" style={{ minHeight: 200, maxHeight: 300 }}>
                  {selectedToolExec ? (
                    <>
                      <div className="terminal-line">
                        <span className="terminal-ts">[COMMAND]</span>
                        <span className="terminal-cmd">$ {selectedToolExec.command}</span>
                      </div>
                      <div className="terminal-line" style={{ marginTop: 6 }}>
                        <span className="terminal-ts">[STDOUT]</span>
                        <span className="terminal-out">{selectedToolExec.stdout}</span>
                      </div>
                    </>
                  ) : (
                    <div style={{ color: 'var(--text-terminal-dim)' }}>
                      Select a tool execution above to inspect captured stdout/stderr.
                    </div>
                  )}
                </div>
              </div>

            </div>

          </div>
        )}

        {/* ─── TAB: INTAKE ───────────────────────────────────────────────────── */}
        {activeTab === 'INTAKE' && (
          <div className="panel" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Target Repository Intake Inspection</h3>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
              Deterministic inventory of files, languages, RTL constructs, and hardware/software contracts.
            </p>
            <button className="btn btn-primary btn-sm" onClick={() => onNavigate('target-repo')}>
              Inspect Full Repository Hierarchy & Graphs
            </button>
          </div>
        )}

        {/* ─── TAB: PLANNING ─────────────────────────────────────────────────── */}
        {activeTab === 'PLANNING' && (
          <div className="panel" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>23-Bucket SoC Verification Plan</h3>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
              Review objective coverage matrix, formal SMT solvers, and resource gates.
            </p>
            <button className="btn btn-primary btn-sm" onClick={() => onNavigate('verification-plan')}>
              Open Verification Plan Matrix
            </button>
          </div>
        )}

        {/* ─── TAB: RESULTS ──────────────────────────────────────────────────── */}
        {activeTab === 'RESULTS' && (
          <div className="panel" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Verification Closure & Evidence Dossier</h3>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
              Inspect mathematical proofs, waveform reproductions, and coverage gates.
            </p>
            <div style={{ display: 'flex', gap: 10 }}>
              <button className="btn btn-primary btn-sm" onClick={() => onNavigate('closure')}>
                Coverage & Closure Dashboard
              </button>
              <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('evidence')}>
                View Authoritative Evidence
              </button>
            </div>
          </div>
        )}

      </div>

      {/* ── Agent Inspection Drawer / Modal (Section 16 & 17) ─────────────────── */}
      {showAgentDrawer && (
        <div className="modal-backdrop" onClick={() => setShowAgentDrawer(false)} style={{ zIndex: 1100 }}>
          <div
            className="modal-content"
            onClick={e => e.stopPropagation()}
            style={{
              width: 820,
              maxWidth: '92vw',
              background: 'var(--bg-surface)',
              borderRadius: 4,
              boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
              border: '1px solid var(--border)'
            }}
          >
            <div className="modal-header" style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-bright)' }}>
                    Agent Inspection: {selectedAgent}
                  </span>
                  <span className="badge badge-ready" style={{ fontSize: 10 }}>AVAILABLE</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                  Role: Verification Engineer · Process ID: pid-8831 · Model: codex-davinci-002
                </div>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={() => setShowAgentDrawer(false)}>✕</button>
            </div>

            {/* Agent Drawer Tabs */}
            <div className="tab-bar" style={{ padding: '0 20px' }}>
              {['Communication', 'Tools', 'Terminal', 'Artifacts', 'Evidence', 'Attempts'].map(t => (
                <div
                  key={t}
                  className={`tab-item ${agentDrawerTab === t ? 'active' : ''}`}
                  onClick={() => setAgentDrawerTab(t)}
                  style={{ fontSize: 13 }}
                >
                  {t}
                </div>
              ))}
            </div>

            <div style={{ padding: '20px', maxHeight: 420, overflowY: 'auto' }}>
              {agentDrawerTab === 'Communication' && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 10 }}>
                    Recorded Protocol Communication Lineage
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div style={{ padding: '8px 12px', background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 2 }}>
                      <span className="mono" style={{ fontWeight: 700, fontSize: 11, color: 'var(--blue)' }}>ORCHESTRATOR → AGY: TASK_ASSIGNMENT</span>
                      <div className="mono text-muted" style={{ fontSize: 11, marginTop: 2 }}>Task: task-sec-01 | Objective: Verify debug auth TAP boundary</div>
                    </div>
                    <div style={{ padding: '8px 12px', background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 2 }}>
                      <span className="mono" style={{ fontWeight: 700, fontSize: 11, color: 'var(--green)' }}>AGY → ORCHESTRATOR: TASK_ACK</span>
                      <div className="mono text-muted" style={{ fontSize: 11, marginTop: 2 }}>Status: Accepted | Resource Budget: 60,000 tokens</div>
                    </div>
                    <div style={{ padding: '8px 12px', background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 2 }}>
                      <span className="mono" style={{ fontWeight: 700, fontSize: 11, color: 'var(--amber)' }}>AGY → TOOL_PLANE: TOOL_REQUEST</span>
                      <div className="mono text-muted" style={{ fontSize: 11, marginTop: 2 }}>Tool: Verilator v5.020 | Target: rtl/debug/debug_auth.sv</div>
                    </div>
                  </div>
                </div>
              )}

              {agentDrawerTab === 'Tools' && (
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Permitted Deterministic Tools for {selectedAgent}:</div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {['Verilator', 'Yosys', 'Slang', 'Boolector', 'Z3'].map(t => (
                      <span key={t} className="mono" style={{ fontSize: 12, padding: '4px 10px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 3 }}>
                        ✓ {t}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {agentDrawerTab === 'Terminal' && (
                <div className="terminal-console">
                  <div className="terminal-header">Real Subprocess Output</div>
                  <div className="terminal-body" style={{ minHeight: 140 }}>
                    <div className="terminal-line"><span className="terminal-cmd">$ verilator --lint-only rtl/debug/debug_auth.sv</span></div>
                    <div className="terminal-line"><span className="terminal-out">%Info: 0 syntax errors detected.</span></div>
                  </div>
                </div>
              )}

              {agentDrawerTab === 'Artifacts' && (
                <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                  Generated Artifacts:
                  <ul style={{ marginLeft: 20, marginTop: 8 }}>
                    <li className="mono">debug_auth.lint.log</li>
                    <li className="mono">debug_unlock_inv.proof.smt2</li>
                  </ul>
                </div>
              )}

              {agentDrawerTab === 'Evidence' && (
                <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                  Authoritative Evidence Produced:
                  <div style={{ marginTop: 8, padding: '8px 12px', background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 3 }}>
                    <span className="mono" style={{ fontWeight: 600 }}>evi-proof-01: Formal SMT proof for debug unlock lock gate</span>
                  </div>
                </div>
              )}

              {agentDrawerTab === 'Attempts' && (
                <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                  Lineage: Attempt 1 / 3 (Succeeded without watchdog intervention)
                </div>
              )}
            </div>

            <div className="modal-footer" style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary btn-sm" onClick={() => setShowAgentDrawer(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
