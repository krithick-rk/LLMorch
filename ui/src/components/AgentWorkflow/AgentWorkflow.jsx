/**
 * AgentWorkflow.jsx — Phase 9.3 (full rewrite)
 * Primary investigation workflow page.
 * - React Flow dynamic graph (repo → orch → agents → tasks → tools → evidence → findings)
 * - Empty state pre-investigation
 * - Agent Workroom side panel on node click
 * - Realtime graph updates via refreshSignal
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import api from '../../api'
import { WorkflowGraph } from './WorkflowGraph'
import { AgentWorkroom } from './AgentWorkroom'
import { StatusPill, Spinner, EmptyState, SectionHeader, Btn, shortId } from '../shared'

const FILTERS = ['ALL', 'ACTIVE', 'AGENTS', 'TASKS', 'TOOLS', 'EVIDENCE', 'FINDINGS', 'FAILED', 'COMPLETED']

export function AgentWorkflowPage({ refreshSignal, onNavigate }) {
  const [tasks, setTasks] = useState(null)
  const [agents, setAgents] = useState(null)
  const [findings, setFindings] = useState(null)
  const [evidence, setEvidence] = useState(null)
  const [currentRepo, setCurrentRepo] = useState(null)
  const [budgets, setBudgets] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('ALL')
  const [selectedNode, setSelectedNode] = useState(null)

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
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', gap: 0 }}>
      {/* Header */}
      <div style={{ flexShrink: 0, paddingBottom: 12 }}>
        <SectionHeader
          title="⚡ Agent Workflow"
          subtitle="Live orchestrator → agent → task → tool → evidence → finding pipeline"
          actions={
            <>
              {/* Filter pills */}
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
            </>
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
                🚀 Start Analysis
              </Btn>
            )}
          </div>
        </div>
      </div>

      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', gap: 12, overflow: 'hidden', minHeight: 0 }}>
        {/* Graph canvas */}
        <div style={{ flex: 1, border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden', minHeight: 0, position: 'relative' }}>
          {!hasAnyTasks ? (
            <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
              <div style={{ textAlign: 'center', maxWidth: 400 }}>
                <div style={{ fontSize: 48, marginBottom: 16 }}>🔬</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>
                  No Active Investigation
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.7, marginBottom: 20 }}>
                  {currentRepo ? (
                    <>
                      Repository selected: <strong style={{ color: 'var(--text-secondary)' }}>{currentRepo.name || currentRepo.path?.split('/').pop()}</strong>
                      <br />Analysis not yet started.
                    </>
                  ) : 'Select a target repository and start analysis to see the live agent workflow.'}
                </div>
                <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap' }}>
                  {onNavigate && (
                    <Btn onClick={() => onNavigate('target-repo')} variant="primary" size="md">
                      {currentRepo ? '🚀 Start Analysis' : '🎯 Select Repository'}
                    </Btn>
                  )}
                  <Btn onClick={load} variant="secondary" size="md">↺ Refresh</Btn>
                </div>

                {/* Quick status cards */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginTop: 24 }}>
                  {[
                    { label: 'Agents Available', value: (agents?.items || []).filter(a => a.health === 'AVAILABLE').length, icon: '🤖' },
                    { label: 'Tools Registered', value: '42+', icon: '🔧' },
                    { label: 'Analysis', value: hasAnyTasks ? 'Running' : 'Not started', icon: '📊' },
                  ].map(({ label, value, icon }) => (
                    <div key={label} style={{
                      background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                      borderRadius: 8, padding: '10px 12px', textAlign: 'center',
                    }}>
                      <div style={{ fontSize: 20, marginBottom: 4 }}>{icon}</div>
                      <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>{value}</div>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{label}</div>
                    </div>
                  ))}
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
        </div>

        {/* Workroom panel */}
        {selectedNode && (
          <AgentWorkroom
            selectedNode={selectedNode}
            agents={agents?.items || []}
            onClose={() => setSelectedNode(null)}
            onRefresh={load}
          />
        )}
      </div>
    </div>
  )
}
