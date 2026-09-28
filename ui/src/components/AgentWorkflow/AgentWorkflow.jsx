import { useState, useEffect, useCallback, useRef } from 'react'
import api from '../../api'
import { WorkflowGraph } from './WorkflowGraph'
import { AgentWorkroom } from './AgentWorkroom'
import { AgentActivityStream } from './AgentActivityStream'
import { AnalystDecisionInbox } from './AnalystDecisionInbox'
import { StatusPill, Spinner, SectionHeader, Btn } from '../shared'

const FILTERS = ['ALL', 'ACTIVE', 'AGENTS', 'TASKS', 'TOOLS', 'EVIDENCE', 'FINDINGS', 'FAILED', 'COMPLETED']

export function AgentWorkflowPage({ refreshSignal, onNavigate, currentRun }) {
  const [tasks, setTasks] = useState(null)
  const [agents, setAgents] = useState(null)
  const [findings, setFindings] = useState(null)
  const [evidence, setEvidence] = useState(null)
  const [currentRepo, setCurrentRepo] = useState(null)
  const [budgets, setBudgets] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('ALL')
  const [selectedNode, setSelectedNode] = useState(null)

  // Resizable Right Activity Stream state
  const [activityWidth, setActivityWidth] = useState(() => {
    const saved = localStorage.getItem('llmorch_activity_width')
    return saved ? Math.max(240, Math.min(480, parseInt(saved, 10))) : 320
  })

  // Resizable Bottom Decision Inbox state
  const [decisionHeight, setDecisionHeight] = useState(() => {
    const saved = localStorage.getItem('llmorch_decision_height')
    return saved ? Math.max(80, Math.min(420, parseInt(saved, 10))) : 160
  })

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [t, a, f, ev, r, b] = await Promise.all([
        api.tasks({ limit: 200 }),
        api.agents({ limit: 50 }),
        api.findings({ limit: 100 }),
        api.evidence({ limit: 50 }),
        api.currentRepository().catch(() => null),
        api.budgets({ limit: 10 }).catch(() => ({ items: [] })),
      ])
      setTasks(t); setAgents(a); setFindings(f)
      setEvidence(ev); setBudgets(b)
      if (r?.repository) setCurrentRepo(r.repository)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load, refreshSignal])

  const handleSelectNode = useCallback((nodeData) => {
    setSelectedNode({ data: nodeData, id: nodeData.label })
  }, [])

  // Activity Stream vertical splitter drag
  const handleActivityResizeStart = (e) => {
    e.preventDefault()
    const startX = e.clientX
    const startW = activityWidth
    const onMouseMove = (moveEvt) => {
      // Dragging left increases right panel width: startW - (moveEvt.clientX - startX)
      const newW = Math.max(240, Math.min(480, startW - (moveEvt.clientX - startX)))
      setActivityWidth(newW)
      localStorage.setItem('llmorch_activity_width', newW.toString())
    }
    const onMouseUp = () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }

  // Decision Inbox horizontal splitter drag
  const handleDecisionResizeStart = (e) => {
    e.preventDefault()
    const startY = e.clientY
    const startH = decisionHeight
    const onMouseMove = (moveEvt) => {
      // Dragging up increases bottom panel height: startH - (moveEvt.clientY - startY)
      const newH = Math.max(80, Math.min(420, startH - (moveEvt.clientY - startY)))
      setDecisionHeight(newH)
      localStorage.setItem('llmorch_decision_height', newH.toString())
    }
    const onMouseUp = () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }

  const hasActiveTasks = (tasks?.items || []).some(t =>
    ['RUNNING', 'IN_PROGRESS', 'ANALYZING', 'PENDING'].includes(t.status?.toUpperCase()))

  const hasAnyTasks = (tasks?.items || []).length > 0

  if (loading && !tasks) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 400 }}>
      <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
        <Spinner size={32} />
        <div style={{ marginTop: 12 }}>Loading agent workflow…</div>
      </div>
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', gap: 6 }}>
      {/* Header */}
      <div style={{ flexShrink: 0 }}>
        <SectionHeader
          title="⚡ Agent Workflow"
          subtitle="Live orchestrator → agent → task → tool → evidence → finding pipeline"
          actions={
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: 3, background: 'var(--bg-base)', padding: 3, borderRadius: 8, border: '1px solid var(--border)', flexWrap: 'wrap' }}>
                {FILTERS.map(f => (
                  <button key={f} onClick={() => setFilter(f)} style={{
                    padding: '3px 9px', border: 'none', borderRadius: 5, cursor: 'pointer',
                    fontSize: 10, fontWeight: 600,
                    background: filter === f ? 'var(--accent-blue)' : 'transparent',
                    color: filter === f ? '#fff' : 'var(--text-muted)', transition: 'all .15s',
                  }}>{f}</button>
                ))}
              </div>
              <Btn onClick={load} variant="secondary" size="sm">↺ Refresh</Btn>
            </div>
          }
        />

        {/* Status bar */}
        <div style={{
          display: 'flex', gap: 10, padding: '8px 12px', background: 'var(--bg-elevated)',
          border: '1px solid var(--border)', borderRadius: 8, flexWrap: 'wrap', alignItems: 'center',
        }}>
          {currentRepo ? (
            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
              🎯 <strong>{currentRepo.name || currentRepo.path?.split('/').pop()}</strong>
            </span>
          ) : (
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>🎯 No target repository</span>
          )}
          <span style={{ color: 'var(--border)', fontSize: 12 }}>|</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            🤖 {(agents?.items || []).filter(a => a.health === 'AVAILABLE').length} agents available
          </span>
          <span style={{ color: 'var(--border)', fontSize: 12 }}>|</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            📋 {(tasks?.items || []).length} tasks
          </span>
          <span style={{ color: 'var(--border)', fontSize: 12 }}>|</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            🚨 {(findings?.items || []).length} findings
          </span>
          {hasActiveTasks && (
            <>
              <span style={{ color: 'var(--border)', fontSize: 12 }}>|</span>
              <span style={{ fontSize: 11, color: '#38bdf8', display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#38bdf8', animation: 'pulse 1.5s infinite', display: 'inline-block' }} />
                ACTIVE
              </span>
            </>
          )}
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            {!currentRepo && onNavigate && (
              <Btn onClick={() => onNavigate('target-repo')} variant="primary" size="sm">
                🎯 Select Repository
              </Btn>
            )}
            {currentRepo && !hasAnyTasks && onNavigate && (
              <Btn onClick={() => onNavigate('target-repo')} variant="success" size="sm">
                🚀 Start Security Analysis
              </Btn>
            )}
          </div>
        </div>
      </div>

      {/* Main split view: Workflow Graph (Left/Center) + Draggable Splitter + Agent Activity Stream (RIGHT) */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>
        {/* Dynamic graph canvas */}
        <div style={{ flex: 1, border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden', minHeight: 0, position: 'relative' }}>
          {!hasAnyTasks ? (
            <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
              <div style={{ textAlign: 'center', maxWidth: 420 }}>
                <div style={{ fontSize: 44, marginBottom: 12 }}>🔬</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>
                  Investigation Not Started
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: 18 }}>
                  {currentRepo ? (
                    <>
                      Repository selected: <strong style={{ color: 'var(--text-secondary)' }}>{currentRepo.name || currentRepo.path?.split('/').pop()}</strong>.
                      <br />Configure assignment and click Start Security Analysis to begin.
                    </>
                  ) : 'Select a target repository to initialize repository intelligence and begin security analysis.'}
                </div>
                <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
                  {onNavigate && (
                    <Btn onClick={() => onNavigate('target-repo')} variant="primary" size="md">
                      {currentRepo ? '🚀 Target Repository Lifecycle' : '🎯 Select Repository'}
                    </Btn>
                  )}
                  <Btn onClick={load} variant="secondary" size="md">↺ Refresh</Btn>
                </div>
              </div>
            </div>
          ) : (
            <WorkflowGraph
              agents={agents?.items || []}
              tasks={tasks?.items || []}
              findings={findings?.items || []}
              evidence={evidence}
              currentRepo={currentRepo}
              onSelectNode={handleSelectNode}
            />
          )}

          {/* Node detail / workroom drawer */}
          {selectedNode && (
            <AgentWorkroom
              selectedNode={selectedNode}
              agents={agents?.items || []}
              onClose={() => setSelectedNode(null)}
              onRefresh={load}
            />
          )}
        </div>

        {/* Draggable Vertical Splitter between workflow graph and activity panel */}
        <div
          onMouseDown={handleActivityResizeStart}
          title="Drag to resize activity stream"
          style={{
            width: 8,
            cursor: 'col-resize',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            userSelect: 'none',
            flexShrink: 0,
          }}
          className="splitter-v"
        >
          <div style={{ width: 2, height: 32, background: 'var(--border)', borderRadius: 1 }} />
        </div>

        {/* Agent Activity Stream (RIGHT side) */}
        <AgentActivityStream
          width={activityWidth}
          runId={currentRun?.run_id}
          refreshSignal={refreshSignal}
          onSelectEntity={(type, id) => {
            if (type === 'finding' && onNavigate) onNavigate('dossier')
            else if (type === 'evidence' && onNavigate) onNavigate('evidence')
            else if (type === 'tool' && onNavigate) onNavigate('tools')
          }}
        />
      </div>

      {/* Draggable Horizontal Splitter above Decision Inbox */}
      <div
        onMouseDown={handleDecisionResizeStart}
        title="Drag to resize decision inbox"
        style={{
          height: 8,
          cursor: 'row-resize',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          userSelect: 'none',
          flexShrink: 0,
        }}
        className="splitter-h"
      >
        <div style={{ height: 2, width: 48, background: 'var(--border)', borderRadius: 1 }} />
      </div>

      {/* Human-in-the-Loop Analyst Decisions / Decision Inbox (BOTTOM) */}
      <div style={{
        height: `${decisionHeight}px`,
        minHeight: '80px',
        maxHeight: '420px',
        overflowY: 'auto',
        flexShrink: 0,
      }}>
        <AnalystDecisionInbox
          runId={currentRun?.run_id}
          refreshSignal={refreshSignal}
          onDecisionHandled={() => load()}
        />
      </div>
    </div>
  )
}
