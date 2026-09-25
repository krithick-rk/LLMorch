/**
 * WorkflowGraph.jsx — Phase 9.3
 * React Flow based dynamic graph for the analyst workflow visualizer.
 * Converts backend state (tasks, agents, findings, tools, evidence) into
 * a directed graph of typed nodes and edges.
 */
import { useCallback, useMemo, useEffect } from 'react'
import {
  ReactFlow, Background, Controls, MiniMap,
  useNodesState, useEdgesState, addEdge,
  MarkerType, Position, Panel,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { STATUS_COLOR, SEVERITY_COLOR, StatusPill, Mono, shortId } from '../shared'

// ── Node type definitions ─────────────────────────────────────────────────────

const NODE_META = {
  repository:   { icon:'🎯', label:'Repository',   bg:'#1e3a5f', border:'#2563eb', text:'#60a5fa' },
  orchestrator: { icon:'🧠', label:'Orchestrator', bg:'#1a1060', border:'#7c3aed', text:'#a78bfa' },
  agent:        { icon:'🤖', label:'Agent',        bg:'#0f2d1f', border:'#16a34a', text:'#4ade80' },
  task:         { icon:'📋', label:'Task',         bg:'#1c1917', border:'#78716c', text:'#a8a29e' },
  tool:         { icon:'🔧', label:'Tool',         bg:'#172033', border:'#0369a1', text:'#38bdf8' },
  evidence:     { icon:'🔐', label:'Evidence',     bg:'#1a2e1a', border:'#15803d', text:'#86efac' },
  hypothesis:   { icon:'💡', label:'Hypothesis',   bg:'#221c04', border:'#a16207', text:'#fbbf24' },
  critic:       { icon:'⚔️', label:'Critic',       bg:'#2d1515', border:'#991b1b', text:'#fca5a5' },
  correlator:   { icon:'🔗', label:'Correlator',   bg:'#1a1a2e', border:'#5b21b6', text:'#c4b5fd' },
  reproducer:   { icon:'⚡', label:'Reproducer',   bg:'#1e1e0f', border:'#854d0e', text:'#fde68a' },
  sandbox:      { icon:'📦', label:'Sandbox',      bg:'#1a1025', border:'#7e22ce', text:'#d8b4fe' },
  validator:    { icon:'✅', label:'Validator',    bg:'#0f1f1a', border:'#0f766e', text:'#5eead4' },
  finding:      { icon:'🚨', label:'Finding',      bg:'#1f0f0f', border:'#dc2626', text:'#fca5a5' },
  analysis_unit:{ icon:'📁', label:'AnalysisUnit', bg:'#0f1f2d', border:'#0369a1', text:'#93c5fd' },
}

// ── Custom Node renderer ──────────────────────────────────────────────────────

function WorkflowNodeWidget({ data }) {
  const meta = NODE_META[data.nodeType] || NODE_META.task
  const statusColor = data.status ? (STATUS_COLOR[data.status.toUpperCase()] || '#94a3b8') : null
  const isRunning = data.status === 'RUNNING' || data.status === 'IN_PROGRESS' || data.status === 'ANALYZING'

  return (
    <div
      onClick={() => data.onSelect && data.onSelect(data)}
      style={{
        minWidth: 140, maxWidth: 200,
        background: meta.bg,
        border: `1.5px solid ${data.selected ? '#38bdf8' : meta.border}`,
        borderRadius: 10,
        padding: '10px 12px',
        cursor: 'pointer',
        boxShadow: data.selected
          ? `0 0 0 2px #38bdf833, 0 4px 20px rgba(0,0,0,0.5)`
          : `0 2px 10px rgba(0,0,0,0.4)`,
        transition: 'all .2s',
        position: 'relative',
        overflow: 'hidden',
        fontFamily: 'inherit',
      }}
    >
      {/* Running pulse top bar */}
      {isRunning && (
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 2,
          background: `linear-gradient(90deg, transparent, ${statusColor || meta.border}, transparent)`,
          animation: 'shimmer 1.5s infinite',
        }} />
      )}
      {/* Completed/Failed top accent */}
      {!isRunning && statusColor && (
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 2,
          background: statusColor, borderRadius: '10px 10px 0 0',
        }} />
      )}

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
        <span style={{ fontSize: 16, flexShrink: 0 }}>{meta.icon}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 10, fontWeight: 700, color: meta.text,
            textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2,
          }}>{data.nodeType}</div>
          <div style={{
            fontSize: 12, fontWeight: 600, color: '#e2e8f0',
            lineHeight: 1.3, wordBreak: 'break-word',
          }}>{data.label || 'Unknown'}</div>
          {data.subtitle && (
            <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 3, lineHeight: 1.4 }}>
              {data.subtitle}
            </div>
          )}
          {data.status && (
            <div style={{ marginTop: 5 }}>
              <StatusPill status={data.status} style={{ fontSize: 9 }} />
            </div>
          )}
          {data.severity && (
            <div style={{ marginTop: 4, fontSize: 9, fontWeight: 700,
              color: SEVERITY_COLOR[data.severity] || '#94a3b8' }}>
              ⚠ {data.severity}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const nodeTypes = { workflowNode: WorkflowNodeWidget }

// ── Layout engine (simple layered layout) ─────────────────────────────────────

function computeLayout(graphData) {
  /**
   * Assigns positions using a topological layer approach.
   * Layers: repo → orchestrator → agents → tasks → tools → evidence → etc
   */
  const LAYER_X = {
    repository:    50,
    orchestrator:  50,
    analysis_unit: 50,
    agent:         50,
    task:          50,
    tool:          50,
    evidence:      50,
    hypothesis:    50,
    correlator:    50,
    critic:        50,
    reproducer:    50,
    sandbox:       50,
    validator:     50,
    finding:       50,
  }

  const LAYER_ORDER = [
    'repository', 'orchestrator', 'analysis_unit',
    'agent', 'task', 'tool', 'evidence',
    'hypothesis', 'correlator', 'critic',
    'reproducer', 'sandbox', 'validator', 'finding',
  ]

  // Group nodes by type
  const byLayer = {}
  LAYER_ORDER.forEach((l, i) => { byLayer[l] = { nodes: [], y: i * 180 } })

  graphData.nodes.forEach(n => {
    const t = n.data.nodeType
    if (!byLayer[t]) byLayer[t] = { nodes: [], y: LAYER_ORDER.length * 180 }
    byLayer[t].nodes.push(n)
  })

  const positioned = []
  const NODE_W = 220
  const NODE_GAP = 24

  LAYER_ORDER.forEach((type, layerIdx) => {
    const layer = byLayer[type]
    if (!layer || layer.nodes.length === 0) return
    const totalW = layer.nodes.length * NODE_W + (layer.nodes.length - 1) * NODE_GAP
    const startX = -totalW / 2
    layer.nodes.forEach((node, i) => {
      positioned.push({
        ...node,
        position: {
          x: startX + i * (NODE_W + NODE_GAP),
          y: layerIdx * 180,
        },
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
      })
    })
  })

  return positioned
}

// ── Graph builder from backend state ─────────────────────────────────────────

export function buildGraphFromState({ agents, tasks, findings, evidence, currentRepo, onSelect }) {
  const nodes = []
  const edges = []

  const makeNode = (id, nodeType, label, extra = {}) => ({
    id, type: 'workflowNode',
    data: { nodeType, label, onSelect: (d) => onSelect && onSelect(d), ...extra },
    position: { x: 0, y: 0 },
    sourcePosition: Position.Bottom,
    targetPosition: Position.Top,
  })

  const makeEdge = (source, target, opts = {}) => ({
    id: `${source}→${target}`,
    source, target,
    animated: opts.animated || false,
    style: {
      stroke: opts.color || '#334155',
      strokeWidth: opts.width || 1.5,
      strokeDasharray: opts.dashed ? '4 4' : undefined,
    },
    markerEnd: { type: MarkerType.ArrowClosed, color: opts.color || '#334155', width: 16, height: 16 },
    label: opts.label,
    labelStyle: { fill: '#94a3b8', fontSize: 9, fontWeight: 600 },
  })

  // Repository node
  const repoId = 'node-repo'
  const repoName = currentRepo
    ? (currentRepo.name || currentRepo.path?.split('/').pop() || 'Target')
    : 'No Repository'
  nodes.push(makeNode(repoId, 'repository', repoName, {
    subtitle: currentRepo?.path?.slice(0, 30) || 'Not selected',
    rawData: currentRepo,
  }))

  // Orchestrator node
  const orchId = 'node-orch'
  const orch = agents?.find(a => a.role === 'orchestrator' || a.name?.toLowerCase().includes('orchestrator'))
  nodes.push(makeNode(orchId, 'orchestrator', orch?.name || 'Orchestrator', {
    status: orch?.health,
    rawData: orch,
  }))
  edges.push(makeEdge(repoId, orchId, { color: '#2563eb', width: 2 }))

  // Agent nodes
  const agentIdMap = {}
  ;(agents || []).filter(a => a.role !== 'orchestrator' && !a.name?.toLowerCase().includes('orchestrator')).forEach(agent => {
    const nid = `node-agent-${agent.agent_id}`
    agentIdMap[agent.agent_id] = nid
    nodes.push(makeNode(nid, 'agent', agent.name || agent.agent_id, {
      subtitle: agent.role || '',
      status: agent.health,
      rawData: agent,
    }))
    edges.push(makeEdge(orchId, nid, {
      color: agent.health === 'AVAILABLE' ? '#16a34a' : '#64748b',
      animated: agent.health === 'AVAILABLE',
    }))
  })

  // Task nodes
  const taskIdMap = {}
  ;(tasks || []).forEach(task => {
    const nid = `node-task-${task.task_id}`
    taskIdMap[task.task_id] = nid
    const parentAgent = agentIdMap[task.agent_id]
    nodes.push(makeNode(nid, 'task', (task.name || task.task_name || 'Task').slice(0, 40), {
      subtitle: task.scope || task.role || '',
      status: task.status,
      rawData: task,
    }))
    if (parentAgent) {
      edges.push(makeEdge(parentAgent, nid, {
        color: STATUS_COLOR[task.status?.toUpperCase()] || '#334155',
        animated: task.status === 'RUNNING' || task.status === 'IN_PROGRESS',
      }))
    } else {
      edges.push(makeEdge(orchId, nid, { color: '#334155' }))
    }
  })

  // Evidence nodes (show up to 6, group the rest)
  const evList = evidence?.items || []
  const shownEvidence = evList.slice(0, 6)
  shownEvidence.forEach(ev => {
    const nid = `node-ev-${ev.evidence_id}`
    const parentTask = ev.task_id ? taskIdMap[ev.task_id] : null
    nodes.push(makeNode(nid, 'evidence', shortId(ev.evidence_id), {
      subtitle: ev.source_tool || '',
      rawData: ev,
    }))
    if (parentTask) {
      edges.push(makeEdge(parentTask, nid, { color: '#15803d', dashed: true }))
    }
  })

  // Findings nodes
  ;(findings || []).slice(0, 8).forEach(f => {
    const nid = `node-finding-${f.finding_id}`
    nodes.push(makeNode(nid, 'finding',
      (f.hypothesis || f.title || 'Finding').slice(0, 40), {
      severity: f.severity,
      status: f.state,
      rawData: f,
    }))
    if (f.task_id && taskIdMap[f.task_id]) {
      edges.push(makeEdge(taskIdMap[f.task_id], nid, {
        color: SEVERITY_COLOR[f.severity] || '#dc2626',
        width: 2,
      }))
    } else if (evList.length > 0) {
      const ev = evList.find(e => e.finding_id === f.finding_id)
      if (ev) {
        edges.push(makeEdge(`node-ev-${ev.evidence_id}`, nid, {
          color: SEVERITY_COLOR[f.severity] || '#dc2626',
          width: 2,
        }))
      }
    }
  })

  return { nodes, edges }
}

// ── WorkflowGraph main component ─────────────────────────────────────────────

export function WorkflowGraph({ agents, tasks, findings, evidence, currentRepo, onSelectNode }) {
  const raw = useMemo(() => buildGraphFromState({
    agents: agents?.items || agents || [],
    tasks: tasks?.items || tasks || [],
    findings: findings?.items || findings || [],
    evidence,
    currentRepo,
    onSelect: onSelectNode,
  }), [agents, tasks, findings, evidence, currentRepo, onSelectNode])

  const layouted = useMemo(() => computeLayout(raw), [raw])

  const [nodes, setNodes, onNodesChange] = useNodesState(layouted)
  const [edges, setEdges, onEdgesChange] = useEdgesState(raw.edges)

  useEffect(() => {
    setNodes(computeLayout(raw))
    setEdges(raw.edges)
  }, [raw, setNodes, setEdges])

  return (
    <div style={{ width: '100%', height: '100%', background: 'var(--bg-base)' }}>
      <style>{`
        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
        .react-flow__background { background: var(--bg-base) !important; }
        .react-flow__controls { background: var(--bg-elevated) !important; border: 1px solid var(--border) !important; }
        .react-flow__controls-button { background: var(--bg-panel) !important; border-bottom: 1px solid var(--border) !important; color: var(--text-secondary) !important; }
        .react-flow__controls-button svg { fill: var(--text-secondary) !important; }
        .react-flow__minimap { background: var(--bg-elevated) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; }
      `}</style>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
        style={{ background: 'var(--bg-base)' }}
      >
        <Background color="#1e293b" gap={20} size={1} />
        <Controls />
        <MiniMap
          nodeColor={n => {
            const meta = NODE_META[n.data?.nodeType]
            return meta?.border || '#334155'
          }}
          maskColor="rgba(11,15,25,0.8)"
          style={{ bottom: 48, right: 10 }}
        />
        <Panel position="top-right">
          <div style={{
            background: 'var(--bg-elevated)', border: '1px solid var(--border)',
            borderRadius: 8, padding: '8px 12px', fontSize: 10,
            color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: 4,
          }}>
            <div style={{ fontWeight: 700, marginBottom: 4, color: 'var(--text-secondary)' }}>Legend</div>
            {Object.entries(NODE_META).slice(0, 8).map(([t, m]) => (
              <div key={t} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: m.border, display: 'inline-block' }} />
                <span>{m.icon} {m.label}</span>
              </div>
            ))}
          </div>
        </Panel>
      </ReactFlow>
    </div>
  )
}
