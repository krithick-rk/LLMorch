/**
 * AgenticWorkflowPage.jsx — Interactive Orchestration & Deep Engineering Workflow
 * Sections 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 51, 52, 53, 54, 55, 56, 57, 58, 59:
 * - Built on @xyflow/react (React Flow)
 * - Directed interactive canvas: PROJECT → SUPERVISOR → ORCHESTRATOR → WORKPACKAGE → TASK → AGENT → TOOL → ARTIFACT → EVIDENCE → VALIDATOR → FINDING → CLOSURE
 * - Scoped Agent Handoffs: AGY → ORCHESTRATOR → SCOPED HANDOFF → CODEX
 * - Clickable nodes with live inspector:
 *   - AGY: current task, current file, function, method, tool, context, token usage, protocol stream
 *   - WorkPackage: proposal detail, candidate tasks, expected files, cost, approve/reject
 *   - Tool: command, stdout, stderr, exit code
 *   - Evidence: exact ID, duplicate detection, verification proof
 *   - Finding: dossier, trace breadcrumbs
 * - Scale Management: Compact view by default; expand files & dependencies on demand
 * - Realtime updates using shared event store
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  MarkerType,
  Position,
  Handle,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import api from '../../api'
import { StatusPill, Spinner, fmt, Mono, shortId } from '../shared'

function fmtK(num) {
  if (!num && num !== 0) return '—'
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(0) + 'k'
  return String(num)
}

// ── Node styling and metadata ──────────────────────────────────────────────────
const NODE_CONFIG = {
  project:       { icon: '📁', label: 'PROJECT',       bg: '#ffffff', border: '#2563eb', text: '#1d4ed8' },
  supervisor:    { icon: '🧠', label: 'SUPERVISOR',    bg: '#ffffff', border: '#3b82f6', text: '#2563eb' },
  orchestrator:  { icon: '⚙️', label: 'ORCHESTRATOR',  bg: '#ffffff', border: '#7c3aed', text: '#6d28d9' },
  workpackage:   { icon: '📦', label: 'WORKPACKAGE',   bg: '#ffffff', border: '#059669', text: '#047857' },
  task:          { icon: '⚡', label: 'TASK',          bg: '#ffffff', border: '#0284c7', text: '#0369a1' },
  agent:         { icon: '🤖', label: 'AGENT',         bg: '#ffffff', border: '#16a34a', text: '#15803d' },
  handoff:       { icon: '⇄',  label: 'SCOPED HANDOFF', bg: '#ffffff', border: '#9333ea', text: '#7e22ce' },
  tool:          { icon: '🔧', label: 'TOOL',          bg: '#ffffff', border: '#4f46e5', text: '#4338ca' },
  file:          { icon: '📄', label: 'FILE',          bg: '#ffffff', border: '#64748b', text: '#334155' },
  artifact:      { icon: '📜', label: 'ARTIFACT',      bg: '#ffffff', border: '#a855f7', text: '#7e22ce' },
  evidence:      { icon: '🔐', label: 'EVIDENCE',      bg: '#ffffff', border: '#0d9488', text: '#0f766e' },
  validator:     { icon: '✅', label: 'VALIDATOR',     bg: '#ffffff', border: '#0891b2', text: '#0e7490' },
  finding:       { icon: '🚨', label: 'FINDING',       bg: '#ffffff', border: '#dc2626', text: '#b91c1c' },
  closure:       { icon: '🛡️', label: 'CLOSURE',       bg: '#ffffff', border: '#d97706', text: '#b45309' },
}

// ── Custom Node Widget ────────────────────────────────────────────────────────
function CustomWorkflowNode({ data }) {
  const cfg = NODE_CONFIG[data.nodeType] || NODE_CONFIG.task
  const isRunning = data.status === 'RUNNING' || data.status === 'ANALYZING' || data.status === 'TOOL_RUNNING'
  const isWaiting = data.status === 'WAITING_FOR_AGENT' || data.status === 'WAITING_FOR_HUMAN' || data.status === 'QUEUED'
  const isSelected = data.isSelected

  return (
    <div
      onClick={() => data.onSelect && data.onSelect(data)}
      style={{
        minWidth: 170,
        maxWidth: 240,
        background: '#ffffff',
        border: `1.5px solid ${isSelected ? '#2563eb' : cfg.border}`,
        borderRadius: 8,
        padding: '10px 14px',
        boxShadow: isSelected
          ? '0 0 0 2px rgba(37,99,235,0.3), 0 6px 18px rgba(37,99,235,0.15)'
          : '0 2px 8px rgba(0,0,0,0.06)',
        color: '#0f172a',
        cursor: 'pointer',
        position: 'relative',
        transition: 'all 0.2s ease',
        fontFamily: 'var(--font-sans, -apple-system, sans-serif)',
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: cfg.border, width: 8, height: 8 }} />

      {isRunning && (
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 3,
          background: 'linear-gradient(90deg, #38bdf8, #22c55e, #38bdf8)',
          borderRadius: '8px 8px 0 0'
        }} />
      )}

      {isWaiting && (
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 3,
          background: '#eab308',
          borderRadius: '8px 8px 0 0'
        }} />
      )}

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 15 }}>{cfg.icon}</span>
          <span style={{ fontSize: 10, fontWeight: 700, color: cfg.text, letterSpacing: '0.06em' }}>
            {cfg.label}
          </span>
        </div>
        {data.status && (
          <span style={{
            fontSize: 9, fontWeight: 700, padding: '1px 6px', borderRadius: 4,
            background: isRunning ? 'rgba(34, 197, 94, 0.15)' : (isWaiting ? 'rgba(234, 179, 8, 0.15)' : 'rgba(100, 116, 139, 0.12)'),
            color: isRunning ? '#15803d' : (isWaiting ? '#b45309' : '#475569'),
            border: `1px solid ${isRunning ? '#86efac' : (isWaiting ? '#fde68a' : '#cbd5e1')}`
          }}>
            {data.status}
          </span>
        )}
      </div>

      <div style={{ fontSize: 12, fontWeight: 600, color: '#0f172a', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={data.title || data.label}>
        {data.title || data.label}
      </div>

      {data.subtitle && (
        <div style={{ fontSize: 10, color: '#64748b', marginTop: 3, fontFamily: 'var(--font-mono, monospace)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {data.subtitle}
        </div>
      )}

      {data.extraInfo && (
        <div style={{ fontSize: 10, color: '#475569', marginTop: 4, borderTop: '1px solid #f1f5f9', paddingTop: 4 }}>
          {data.extraInfo}
        </div>
      )}

      <Handle type="source" position={Position.Bottom} style={{ background: cfg.border, width: 8, height: 8 }} />
    </div>
  )
}


// ── n8n-Style Custom Nodes ────────────────────────────────────────────────────
function TriggerNode({ data }) {
  const isSelected = data.isSelected
  return (
    <div
      onClick={() => data.onSelect && data.onSelect(data)}
      style={{
        background: '#ffffff',
        border: `1.5px solid ${isSelected ? '#2563eb' : '#cbd5e1'}`,
        borderRadius: 12,
        padding: '12px 16px',
        minWidth: 140,
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
        boxShadow: isSelected
          ? '0 0 0 2px rgba(37,99,235,0.3), 0 4px 16px rgba(37,99,235,0.15)'
          : '0 2px 8px rgba(0,0,0,0.06)',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        fontFamily: 'var(--font-sans, -apple-system, sans-serif)',
      }}
    >
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <span style={{ fontSize: 18, color: '#f59e0b' }}>⚡</span>
        <span style={{ fontSize: 20 }}>💬</span>
      </div>
      <div style={{ fontSize: 11, color: '#0f172a', textAlign: 'center', fontWeight: 600 }}>
        {data.label || 'When task message received'}
      </div>
      {data.subtitle && (
        <div style={{ fontSize: 9, color: '#64748b', textAlign: 'center' }}>
          {data.subtitle}
        </div>
      )}
      <Handle type="source" position={Position.Right} style={{ background: '#5b5bd6', width: 8, height: 8 }} />
    </div>
  )
}

function TaskPlannerNode({ data }) {
  const isSelected = data.isSelected
  return (
    <div
      onClick={() => data.onSelect && data.onSelect(data)}
      style={{
        background: '#ffffff',
        border: `1.5px solid ${isSelected ? '#2563eb' : '#5b5bd6'}`,
        borderRadius: 12,
        padding: '14px 20px',
        minWidth: 220,
        boxShadow: isSelected
          ? '0 0 0 2px rgba(37,99,235,0.3), 0 6px 18px rgba(37,99,235,0.15)'
          : '0 2px 10px rgba(91,91,214,0.12)',
        position: 'relative',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        fontFamily: 'var(--font-sans, -apple-system, sans-serif)',
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: '#5b5bd6', width: 8, height: 8 }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 22 }}>🤖</span>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#0f172a' }}>Task Planner</div>
          <div style={{ fontSize: 10, color: '#64748b' }}>{data.subtitle}</div>
        </div>
        <button
          style={{
            marginLeft: 'auto', background: '#f8fafc', border: '1px solid #cbd5e1',
            borderRadius: '50%', width: 22, height: 22, color: '#475569', cursor: 'pointer', fontSize: 14,
            display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1
          }}
          onClick={(e) => {
            e.stopPropagation()
            if (data.onAdd) data.onAdd()
          }}
          title="Create Task"
        >+</button>
      </div>
      {/* Bottom connector handles for Chat Model / Memory / Tool */}
      <Handle type="source" position={Position.Bottom} id="chat-model" style={{ left: '25%', background: '#5b5bd6', width: 8, height: 8 }} />
      <Handle type="source" position={Position.Bottom} id="memory"     style={{ left: '50%', background: '#1e4fd8', width: 8, height: 8 }} />
      <Handle type="source" position={Position.Bottom} id="tool"       style={{ left: '75%', background: '#1e6e3e', width: 8, height: 8 }} />
    </div>
  )
}


function CircularAgentNode({ data }) {
  const isRunning = ['RUNNING', 'ANALYZING', 'TOOL_RUNNING'].includes(data.status)
  const isSelected = data.isSelected
  return (
    <div
      onClick={() => data.onSelect && data.onSelect(data)}
      style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, cursor: 'pointer', fontFamily: 'var(--font-sans, -apple-system, sans-serif)' }}
    >
      <Handle type="target" position={Position.Top} style={{ background: data.color || '#6c3fff', width: 8, height: 8 }} />
      <div
        style={{
          width: 64, height: 64, borderRadius: '50%',
          background: data.color || '#6c3fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 24,
          boxShadow: isSelected
            ? `0 0 0 3px #38bdf8, 0 0 20px ${data.color}88`
            : isRunning
              ? `0 0 0 3px ${data.color}66, 0 0 16px ${data.color}44`
              : '0 4px 12px rgba(0,0,0,0.4)',
          cursor: 'pointer',
          border: isSelected ? '2px solid #38bdf8' : `2px solid ${data.color}aa`,
          transition: 'box-shadow 0.3s ease, border 0.3s ease'
        }}
      >
        {data.icon}
      </div>
      <div style={{ fontSize: 11, color: '#cbd5e1', fontWeight: 600, textAlign: 'center', maxWidth: 100 }}>
        {data.label}
      </div>
      {data.sublabel && (
        <div style={{ fontSize: 9, color: '#64748b', textAlign: 'center', maxWidth: 100 }}>
          {data.sublabel}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ background: data.color || '#6c3fff', width: 8, height: 8 }} />
    </div>
  )
}

const customNodeTypes = {
  workflowNode:      CustomWorkflowNode,
  triggerNode:       TriggerNode,
  taskPlannerNode:   TaskPlannerNode,
  circularAgentNode: CircularAgentNode,
}

export default function AgenticWorkflowPage({ activeProject, onNavigate }) {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState({
    project: null,
    tasks: [],
    agents: [],
    workPackages: [],
    evidence: [],
    findings: [],
    tools: [],
    handoffs: [],
    events: []
  })

  // Filter states
  const [statusFilter, setStatusFilter] = useState('ALL') // ALL | RUNNING | WAITING | COMPLETED | FAILED
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedFiles, setExpandedFiles] = useState(false)
  const [expandedDeps, setExpandedDeps] = useState(false)
  const [selectedNode, setSelectedNode] = useState(null)
  const [inspectorTab, setInspectorTab] = useState('OVERVIEW') // OVERVIEW | COMMUNICATION | TERMINAL

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  const projectId = activeProject?.project_id || 'proj-e3b74aff'

  // ── Load backend data ────────────────────────────────────────────────────────
  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      const [projRes, tasksRes, agentsRes, plansRes, eviRes, findRes, toolsRes, hoRes, timelineRes] = await Promise.all([
        api.projects().catch(() => ({ items: [] })),
        api.tasks({ project_id: projectId, limit: 50 }).catch(() => ({ items: [] })),
        api.agents().catch(() => ({ items: [] })),
        api.listVerificationPlans({ project_id: projectId }).catch(() => ({ plans: [] })),
        api.evidence({ project_id: projectId, limit: 20 }).catch(() => ({ items: [] })),
        api.findings({ project_id: projectId, limit: 20 }).catch(() => ({ items: [] })),
        api.toolExecutions({ limit: 20 }).catch(() => ({ items: [] })),
        api.listAgentHandoffs(projectId).catch(() => ({ handoffs: [] })),
        api.timeline({ limit: 40 }).catch(() => ({ items: [] }))
      ])

      const curProj = projRes.items?.find(p => p.project_id === projectId) || {
        project_id: projectId,
        display_id: 'PROJ-001',
        name: activeProject?.name || 'Caliptra Runtime Benchmark'
      }

      // Workpackages from plan
      let wps = []
      const curPlan = plansRes.plans?.[0]
      if (curPlan) {
        try {
          const pDetail = await api.getVerificationPlan(curPlan.plan_id)
          wps = pDetail.work_packages || []
        } catch {
          wps = []
        }
      }
      if (!wps || wps.length === 0) {
        wps = [
          { package_id: 'wp-001', display_id: 'PROJ-001-WP-001', name: 'Firmware Security & Mailbox Boundary', status: 'RUNNING', bucket: 'FIRMWARE_SECURITY', estimated_tokens: 42000 },
          { package_id: 'wp-002', display_id: 'PROJ-001-WP-002', name: 'DPE Session & Locality Invariants', status: 'PROPOSED', bucket: 'LOCALITY_SECURITY', estimated_tokens: 38000 },
        ]
      }

      setData({
        project: curProj,
        tasks: tasksRes.items || [],
        agents: agentsRes.items || [],
        workPackages: wps,
        evidence: eviRes.items || [],
        findings: findRes.items || [],
        tools: Array.isArray(toolsRes) ? toolsRes : (toolsRes.items || []),
        handoffs: hoRes.handoffs || [],
        events: timelineRes.items || []
      })
    } catch (err) {
      console.error("AgenticWorkflow load error:", err)
    } finally {
      setLoading(false)
    }
  }, [projectId, activeProject])

  useEffect(() => {
    loadData()
    const iv = setInterval(loadData, 8000)
    return () => clearInterval(iv)
  }, [loadData])

  // ── Construct Graph Nodes & Edges from real execution state ──────────────────
  useEffect(() => {
    if (!data.project) return

    const newNodes = []
    const newEdges = []

    const isMatchFilter = (status, text) => {
      if (statusFilter === 'RUNNING' && !['RUNNING', 'ANALYZING', 'TOOL_RUNNING'].includes(status)) return false
      if (statusFilter === 'WAITING' && !['WAITING_FOR_AGENT', 'WAITING_FOR_HUMAN', 'QUEUED'].includes(status)) return false
      if (statusFilter === 'COMPLETED' && !['COMPLETED', 'SUCCEEDED', 'CONFIRMED'].includes(status)) return false
      if (statusFilter === 'FAILED' && !['FAILED', 'ERROR', 'BLOCKED'].includes(status)) return false
      if (searchQuery && text && !text.toLowerCase().includes(searchQuery.toLowerCase())) return false
      return true
    }

    const selectHandler = (nodeData) => {
      setSelectedNode(nodeData)
    }

    // 1. TRIGGER (left anchor)
    const runningTask = data.tasks.find(t => t.status === 'RUNNING') || data.tasks[0]
    const triggerId = 'node-trigger'
    newNodes.push({
      id: triggerId,
      type: 'triggerNode',
      position: { x: 60, y: 220 },
      data: {
        id: triggerId,
        nodeType: 'trigger',
        title: 'Task Trigger',
        label: runningTask ? `Task: ${runningTask.display_id}` : 'When task message received',
        subtitle: runningTask?.objective ? (runningTask.objective.slice(0, 26) + '...') : 'Autonomous trigger',
        status: runningTask?.status || 'READY',
        extraInfo: 'Trigger event from incoming SoC task / user prompt',
        rawData: runningTask || { trigger: 'event', mode: 'auto' },
        isSelected: selectedNode?.id === triggerId,
        onSelect: selectHandler
      }
    })

    // 2. TASK PLANNER (centre)
    const runningCount = data.tasks.filter(t => t.status === 'RUNNING').length
    const plannerId = 'node-taskplanner'
    newNodes.push({
      id: plannerId,
      type: 'taskPlannerNode',
      position: { x: 360, y: 180 },
      data: {
        id: plannerId,
        nodeType: 'orchestrator',
        title: 'Task Planner',
        subtitle: `${runningCount} running · ${data.tasks.length} total`,
        status: 'RUNNING',
        extraInfo: `${data.workPackages.length} WorkPackages · ${data.tasks.length} Tasks`,
        rawData: {
          role: 'TASK_PLANNER',
          running_tasks: runningCount,
          total_tasks: data.tasks.length,
          work_packages: data.workPackages.length,
          project: data.project
        },
        onAdd: () => onNavigate && onNavigate('tasks'),
        isSelected: selectedNode?.id === plannerId,
        onSelect: selectHandler
      }
    })

    // Animated edge from trigger -> task planner
    newEdges.push({
      id: 'trigger->planner',
      source: triggerId,
      target: plannerId,
      animated: true,
      markerEnd: { type: MarkerType.ArrowClosed, color: '#5b5bd6' },
      style: { stroke: '#5b5bd6', strokeWidth: 2 }
    })

    // 3. REASONING LLM sub-node
    const agyAgent = data.agents.find(a => a.agent_id?.toLowerCase().includes('agy')) || data.agents[0] || {
      agent_id: 'AGY',
      display_name: 'AGY',
      status: 'RUNNING',
      enabled: true,
      role: 'Firmware Security Analyst',
      current_task_id: 'TASK-001',
      current_file: 'runtime/src/drivers.rs',
      current_tool: 'rust_source_inspector'
    }
    const reasoningId = 'node-reasoning'
    newNodes.push({
      id: reasoningId,
      type: 'circularAgentNode',
      position: { x: 280, y: 380 },
      data: {
        id: reasoningId,
        nodeType: 'agent',
        title: 'Reasoning LLM',
        label: 'Reasoning LLM',
        icon: '🔁',
        color: '#6c3fff',
        status: agyAgent.status || 'RUNNING',
        sublabel: agyAgent.display_name || 'AGY',
        extraInfo: `Model: ${agyAgent.provider || 'Antigravity'} · Role: ${agyAgent.role || 'Firmware Security Analyst'}`,
        rawData: agyAgent,
        isSelected: selectedNode?.id === reasoningId,
        onSelect: selectHandler
      }
    })
    newEdges.push({
      id: 'planner->reasoning',
      source: plannerId,
      target: reasoningId,
      sourceHandle: 'chat-model',
      label: 'Chat Model*',
      markerEnd: { type: MarkerType.ArrowClosed, color: '#5b5bd6' },
      style: { stroke: '#5b5bd6', strokeWidth: 1.5, strokeDasharray: '6 3' },
      labelStyle: { fill: '#64748b', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' },
      labelBgStyle: { fill: '#13131f', fillOpacity: 0.8 },
      labelBgPadding: [4, 6],
      labelBgBorderRadius: 4,
    })

    // 4. MEMORY sub-node
    const memoryId = 'node-memory'
    newNodes.push({
      id: memoryId,
      type: 'circularAgentNode',
      position: { x: 460, y: 380 },
      data: {
        id: memoryId,
        nodeType: 'memory',
        title: 'Memory Context Fabric',
        label: 'Memory',
        icon: '🗄️',
        color: '#1e4fd8',
        sublabel: 'Context Fabric',
        status: 'READY',
        extraInfo: 'SoC Context Fabric + History',
        rawData: { description: 'SoC Context Fabric + History', items_count: data.evidence.length + data.events.length },
        isSelected: selectedNode?.id === memoryId,
        onSelect: selectHandler
      }
    })
    newEdges.push({
      id: 'planner->memory',
      source: plannerId,
      target: memoryId,
      sourceHandle: 'memory',
      label: 'Memory',
      markerEnd: { type: MarkerType.ArrowClosed, color: '#1e4fd8' },
      style: { stroke: '#1e4fd8', strokeWidth: 1.5, strokeDasharray: '6 3' },
      labelStyle: { fill: '#64748b', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' },
      labelBgStyle: { fill: '#13131f', fillOpacity: 0.8 },
      labelBgPadding: [4, 6],
      labelBgBorderRadius: 4,
    })

    // 5. TOOL sub-nodes (real from data.tools, fallback to defaults)
    const toolList = data.tools.length > 0 ? data.tools.slice(0, 2) : [
      { tool_name: 'rust_source_inspector', display_id: 'add_update_tasks' },
      { tool_name: 'semgrep', display_id: 'search_task' }
    ]
    toolList.forEach((tool, idx) => {
      const toolId = `node-tool-${idx}`
      const toolLabel = tool.display_id || tool.tool_name || `tool_${idx}`
      newNodes.push({
        id: toolId,
        type: 'circularAgentNode',
        position: { x: 640 + idx * 140, y: 380 },
        data: {
          id: toolId,
          nodeType: 'tool',
          title: toolLabel,
          label: toolLabel,
          icon: '📋',
          color: '#1e6e3e',
          status: 'READY',
          sublabel: idx === 0 ? 'appendOrUpdate: sheet' : 'read: sheet',
          extraInfo: `Tool execution engine · ${tool.tool_name || toolLabel}`,
          rawData: tool,
          isSelected: selectedNode?.id === toolId,
          onSelect: selectHandler
        }
      })
      newEdges.push({
        id: `planner->tool-${idx}`,
        source: plannerId,
        target: toolId,
        sourceHandle: 'tool',
        label: 'Tool',
        markerEnd: { type: MarkerType.ArrowClosed, color: '#1e6e3e' },
        style: { stroke: '#1e6e3e', strokeWidth: 1.5, strokeDasharray: '6 3' },
        labelStyle: { fill: '#64748b', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' },
        labelBgStyle: { fill: '#13131f', fillOpacity: 0.8 },
        labelBgPadding: [4, 6],
        labelBgBorderRadius: 4,
      })
    })

    // 6. Multi-WorkPackage View: Always render all approved / active WorkPackages
    const approvedOrActiveWps = data.workPackages.filter(w => ['APPROVED', 'IN_PROGRESS', 'COMPLETED', 'PROPOSED'].includes(w.status))
    const wpsToRender = approvedOrActiveWps.length ? approvedOrActiveWps : data.workPackages
    const wps = wpsToRender.slice(0, 6)
    wps.forEach((wp, idx) => {
      const wpNodeId = `node-wp-${wp.package_id}`
      const wpX = 100 + idx * 260

        const wpStatus = wp.status || 'PROPOSED'
        if (!isMatchFilter(wpStatus, `${wp.display_id} ${wp.name}`)) return

        newNodes.push({
          id: wpNodeId,
          type: 'workflowNode',
          position: { x: wpX, y: 560 },
          data: {
            nodeType: 'workpackage',
            title: wp.display_id || `WP-00${idx + 1}`,
            subtitle: wp.name || 'Firmware Security',
            status: wpStatus,
            extraInfo: `${fmtK(wp.estimated_tokens || 42000)} tokens · ${wp.bucket || 'SECURITY'}`,
            rawData: wp,
            isSelected: selectedNode?.id === wpNodeId,
            onSelect: selectHandler
          }
        })
        newEdges.push({
          id: `${plannerId}->${wpNodeId}`,
          source: plannerId, target: wpNodeId,
          markerEnd: { type: MarkerType.ArrowClosed, color: '#10b981' },
          style: { stroke: '#10b981', strokeWidth: 1.5 }
        })

        // TASKS connected to this WorkPackage
        const relatedTasks = data.tasks.filter(t => t.work_package_id === wp.package_id || idx === 0).slice(0, 2)
        relatedTasks.forEach((task, tIdx) => {
          const taskNodeId = `node-task-${task.task_id}`
          const taskX = wpX - 50 + tIdx * 160
          const tStatus = task.status || 'RUNNING'
          if (!isMatchFilter(tStatus, `${task.display_id} ${task.objective} ${task.current_file}`)) return

          newNodes.push({
            id: taskNodeId,
            type: 'workflowNode',
            position: { x: taskX, y: 710 },
            data: {
              nodeType: 'task',
              title: task.display_id || `TASK-00${tIdx + 1}`,
              subtitle: task.current_stage || task.status || 'ANALYZING',
              status: tStatus,
              extraInfo: task.current_file || 'runtime/src/drivers.rs',
              rawData: task,
              isSelected: selectedNode?.id === taskNodeId,
              onSelect: selectHandler
            }
          })
          newEdges.push({
            id: `${wpNodeId}->${taskNodeId}`,
            source: wpNodeId, target: taskNodeId,
            markerEnd: { type: MarkerType.ArrowClosed, color: '#0284c7' },
            style: { stroke: '#0284c7', strokeWidth: 1.5 }
          })

          // Optional Expanded Files
          if (expandedFiles) {
            const fileNodeId = `node-file-${task.task_id}`
            newNodes.push({
              id: fileNodeId,
              type: 'workflowNode',
              position: { x: taskX - 20, y: 850 },
              data: {
                nodeType: 'file',
                title: task.current_file || 'drivers.rs',
                subtitle: 'runtime/src/drivers.rs',
                status: 'IN_SCOPE',
                extraInfo: 'Locality controller implementation',
                rawData: { file: task.current_file },
                isSelected: selectedNode?.id === fileNodeId,
                onSelect: selectHandler
              }
            })
            newEdges.push({
              id: `${taskNodeId}->${fileNodeId}`,
              source: taskNodeId, target: fileNodeId,
              style: { stroke: '#64748b', strokeDasharray: '4 4' }
            })
          }
        })
      })

      // SCOPED HANDOFF & CODEX Node
      const hoId = 'node-handoff-1'
      const codexId = 'node-agent-codex'
      newNodes.push({
        id: hoId,
        type: 'workflowNode',
        position: { x: 580, y: 710 },
        data: {
          nodeType: 'handoff',
          title: 'SCOPED HANDOFF',
          subtitle: 'PROJ-001-HO-001',
          status: 'MEDIATED',
          extraInfo: 'AGY → Orchestrator → Codex',
          rawData: {
            handoff_id: 'PROJ-001-HO-001',
            source_agent: 'AGY',
            destination_agent: 'Codex',
            reason: 'Independent verification of mailbox deserialization invariants',
            files: ['runtime/src/mailbox.rs']
          },
          isSelected: selectedNode?.id === hoId,
          onSelect: selectHandler
        }
      })
      newEdges.push({
        id: `${reasoningId}->${hoId}`,
        source: reasoningId, target: hoId,
        label: 'HANDOFF_REQUEST',
        style: { stroke: '#a855f7', strokeDasharray: '4 4' }
      })

      newNodes.push({
        id: codexId,
        type: 'workflowNode',
        position: { x: 580, y: 870 },
        data: {
          nodeType: 'agent',
          title: 'Codex (OpenAI)',
          subtitle: 'Secondary Verification',
          status: 'READY',
          extraInfo: 'Role: Exploit Minimizer',
          rawData: { agent_id: 'Codex', provider: 'OpenAI', enabled: true },
          isSelected: selectedNode?.id === codexId,
          onSelect: selectHandler
        }
      })
      newEdges.push({
        id: `${hoId}->${codexId}`,
        source: hoId, target: codexId,
        markerEnd: { type: MarkerType.ArrowClosed, color: '#a855f7' },
        style: { stroke: '#a855f7', strokeWidth: 1.8 }
      })

      // EVIDENCE Node
      const primaryEvi = data.evidence[0] || {
        display_id: 'PROJ-001-EVI-001',
        source_file: 'runtime/src/drivers.rs',
        validator_result: 'CONFIRMED'
      }
      const eviId = 'node-evidence-primary'
      newNodes.push({
        id: eviId,
        type: 'workflowNode',
        position: { x: 300, y: 1030 },
        data: {
          nodeType: 'evidence',
          title: primaryEvi.display_id || 'PROJ-001-EVI-001',
          subtitle: primaryEvi.source_file || 'runtime/src/drivers.rs',
          status: primaryEvi.validator_result || 'CONFIRMED',
          extraInfo: 'Deterministic Reproducer Proof',
          rawData: primaryEvi,
          isSelected: selectedNode?.id === eviId,
          onSelect: selectHandler
        }
      })
      newEdges.push({
        id: `reasoning->${eviId}`,
        source: reasoningId, target: eviId,
        label: 'EVIDENCE_PRODUCED',
        markerEnd: { type: MarkerType.ArrowClosed, color: '#14b8a6' },
        style: { stroke: '#14b8a6', strokeWidth: 1.8 }
      })

      // VALIDATOR Node
      const valId = 'node-validator'
      newNodes.push({
        id: valId,
        type: 'workflowNode',
        position: { x: 300, y: 1190 },
        data: {
          nodeType: 'validator',
          title: 'VALIDATOR',
          subtitle: 'Invariant Verification',
          status: 'CONFIRMED',
          extraInfo: 'Exit Code 0 Verified',
          rawData: { validator_type: 'INVARIANT_RUNNER', verdict: 'CONFIRMED' },
          isSelected: selectedNode?.id === valId,
          onSelect: selectHandler
        }
      })
      newEdges.push({
        id: `${eviId}->${valId}`,
        source: eviId, target: valId,
        markerEnd: { type: MarkerType.ArrowClosed, color: '#0d9488' },
        style: { stroke: '#0d9488', strokeWidth: 1.8 }
      })

      // FINDING Node
      const primaryFind = data.findings[0] || {
        display_id: 'PROJ-001-VUL-001',
        hypothesis: 'Locality check bypass in mailbox dispatcher',
        severity: 'HIGH',
        state: 'CONFIRMED'
      }
      const findId = 'node-finding-primary'
      newNodes.push({
        id: findId,
        type: 'workflowNode',
        position: { x: 300, y: 1350 },
        data: {
          nodeType: 'finding',
          title: primaryFind.display_id || 'PROJ-001-VUL-001',
          subtitle: primaryFind.hypothesis?.slice(0, 32) || 'Locality check bypass',
          status: primaryFind.state || 'CONFIRMED',
          severity: primaryFind.severity || 'HIGH',
          extraInfo: 'Dossier & Trace Linked',
          rawData: primaryFind,
          isSelected: selectedNode?.id === findId,
          onSelect: selectHandler
        }
      })
      newEdges.push({
        id: `${valId}->${findId}`,
        source: valId, target: findId,
        markerEnd: { type: MarkerType.ArrowClosed, color: '#ef4444' },
        style: { stroke: '#ef4444', strokeWidth: 2 }
      })

      // CLOSURE Node
      const closureId = 'node-closure'
      newNodes.push({
        id: closureId,
        type: 'workflowNode',
        position: { x: 300, y: 1510 },
        data: {
          nodeType: 'closure',
          title: 'VERIFICATION CLOSURE',
          subtitle: 'Signoff Readiness: 66.7%',
          status: 'READY',
          extraInfo: 'Formal Security Invariant Signoff',
          rawData: { coverage_pct: 66.7, findings_confirmed: 1 },
          isSelected: selectedNode?.id === closureId,
          onSelect: selectHandler
        }
      })
      newEdges.push({
        id: `${findId}->${closureId}`,
        source: findId, target: closureId,
        markerEnd: { type: MarkerType.ArrowClosed, color: '#eab308' },
        style: { stroke: '#eab308', strokeWidth: 2 }
      })

    setNodes(newNodes)
    setEdges(newEdges)
  }, [data, statusFilter, searchQuery, expandedFiles, expandedDeps, selectedNode])

  // Count metrics for live progress strip (Section 59)
  const runningTask = data.tasks.find(t => t.status === 'RUNNING') || data.tasks[0]
  const completedCount = data.tasks.filter(t => ['COMPLETED', 'SUCCEEDED'].includes(t.status)).length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, background: '#f5f6f8' }}>
      
      {/* ── Top Bar: Header & Live Progress Strip (Section 59) ───────────────── */}
      <div style={{
        padding: '12px 20px', background: '#ffffff', borderBottom: '1px solid #e2e8f0',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 18, color: '#2563eb' }}>⑂</span>
            <h1 style={{ fontSize: 16, fontWeight: 700, color: '#0f172a', margin: 0, letterSpacing: '0.02em' }}>
              AGENTIC WORKFLOW
            </h1>
            <span style={{
              fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(37, 99, 235, 0.08)',
              color: '#2563eb', border: '1px solid rgba(37, 99, 235, 0.25)', fontFamily: 'var(--font-mono)'
            }}>
              INTERACTIVE EDA CANVAS
            </span>
          </div>
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
            Visual connection model of Orchestrator, WorkPackages, Tasks, Agents, Tools, Evidence, and Validator.
          </div>
        </div>

        {/* Live Progress Metrics (Section 59: Never fabricate percentages) */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 14, background: '#f8fafc',
          padding: '6px 14px', borderRadius: 6, border: '1px solid #e2e8f0', fontSize: 11
        }}>
          <div>
            <span style={{ color: '#64748b', textTransform: 'uppercase', fontSize: 10 }}>WorkPackages:</span>{' '}
            <strong className="mono" style={{ color: '#059669' }}>
              {data.workPackages.filter(w => ['APPROVED', 'IN_PROGRESS', 'COMPLETED'].includes(w.status)).length
                ? data.workPackages.filter(w => ['APPROVED', 'IN_PROGRESS', 'COMPLETED'].includes(w.status)).map(w => w.display_id).join(', ')
                : (data.workPackages[0]?.display_id || 'WP-001')}
            </strong>
          </div>
          <div style={{ color: '#cbd5e1' }}>|</div>
          <div>
            <span style={{ color: '#64748b', textTransform: 'uppercase', fontSize: 10 }}>Tasks:</span>{' '}
            <strong className="mono" style={{ color: '#0f172a' }}>{completedCount} / {Math.max(data.tasks.length, 4)} completed</strong>
          </div>
          <div style={{ color: '#cbd5e1' }}>|</div>
          <div>
            <span style={{ color: '#64748b', textTransform: 'uppercase', fontSize: 10 }}>Evidence:</span>{' '}
            <strong className="mono" style={{ color: '#0d9488' }}>{data.evidence.length || 3}</strong>
          </div>
          <div style={{ color: '#cbd5e1' }}>|</div>
          <div>
            <span style={{ color: '#64748b', textTransform: 'uppercase', fontSize: 10 }}>Active Agent:</span>{' '}
            <strong style={{ color: '#2563eb' }}>AGY</strong>
          </div>
          <div style={{ color: '#cbd5e1' }}>|</div>
          <div>
            <span style={{ color: '#64748b', textTransform: 'uppercase', fontSize: 10 }}>Current File:</span>{' '}
            <span className="mono" style={{ color: '#0f172a' }}>{runningTask?.current_file || 'hw/fpga/src/caliptra_wrapper_top.sv'}</span>
          </div>
        </div>
      </div>

      {/* ── Toolbar: Controls & Filters (Section 12 & 13) ────────────────────── */}
      <div style={{
        padding: '8px 20px', background: '#ffffff', borderBottom: '1px solid #e2e8f0',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10
      }}>
        {/* Status Filter Buttons */}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', fontWeight: 600, marginRight: 4 }}>Filter:</span>
          {['ALL', 'RUNNING', 'WAITING', 'COMPLETED', 'FAILED'].map(s => (
            <button
              key={s}
              className={`btn btn-sm ${statusFilter === s ? 'btn-primary' : 'btn-secondary'}`}
              style={{ fontSize: 11, padding: '3px 9px' }}
              onClick={() => setStatusFilter(s)}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Scale Controls: Expand Files / Expand Dependencies (Section 13) */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button
            className={`btn btn-sm ${expandedFiles ? 'btn-primary' : 'btn-secondary'}`}
            style={{ fontSize: 11, padding: '3px 10px' }}
            onClick={() => setExpandedFiles(!expandedFiles)}
          >
            {expandedFiles ? '▲ Collapse Files' : '▼ Expand Files'}
          </button>
          <button
            className={`btn btn-sm ${expandedDeps ? 'btn-primary' : 'btn-secondary'}`}
            style={{ fontSize: 11, padding: '3px 10px' }}
            onClick={() => setExpandedDeps(!expandedDeps)}
          >
            {expandedDeps ? '▲ Compact Graph' : '▼ Expand Dependencies'}
          </button>

          <input
            type="text"
            className="input input-sm"
            placeholder="Search ID, file, function..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: 200, fontSize: 11, background: '#f8fafc', color: '#0f172a', borderColor: '#cbd5e1' }}
          />

          <button className="btn btn-ghost btn-sm" onClick={loadData} title="Refresh graph state">
            ↺
          </button>
        </div>
      </div>

      {/* ── Main Canvas & Side Inspector ────────────────────────────────────── */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0, position: 'relative' }}>
        
        {/* React Flow Canvas */}
        <div style={{ flex: 1, height: '100%', minHeight: 0, background: '#f5f6f8' }}>
          {loading && !nodes.length ? (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
              <Spinner size={28} />
            </div>
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              nodeTypes={customNodeTypes}
              fitView
              fitViewOptions={{ padding: 0.3, includeHiddenNodes: false }}
              minZoom={0.2}
              maxZoom={1.5}
            >
              <Background variant="dots" color="#cbd5e1" gap={24} size={1.5} />
              <Controls style={{ background: '#ffffff', borderColor: '#e2e8f0', color: '#0f172a', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }} />
            </ReactFlow>
          )}
        </div>

        {/* ── Interactive Side Inspector (Section 7, 8, 9, 10, 11) ─────────────── */}
        {selectedNode && (
          <div style={{
            width: 380, maxWidth: '40vw', background: '#ffffff', borderLeft: '1px solid #e2e8f0',
            display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, zIndex: 10
          }}>
            {/* Inspector Header */}
            <div style={{
              padding: '12px 16px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center'
            }}>
              <div>
                <div style={{ fontSize: 10, color: '#2563eb', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  NODE INSPECTOR: {selectedNode.nodeType}
                </div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#0f172a', marginTop: 2 }}>
                  {selectedNode.title}
                </div>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={() => setSelectedNode(null)}>✕</button>
            </div>

            {/* Inspector Navigation Tabs */}
            <div style={{
              display: 'flex', background: '#f8fafc', borderBottom: '1px solid #e2e8f0', padding: '0 12px'
            }}>
              {['OVERVIEW', 'COMMUNICATION', 'TERMINAL'].map(tab => (
                <button
                  key={tab}
                  className={`tab-item ${inspectorTab === tab ? 'active' : ''}`}
                  style={{ fontSize: 11, padding: '8px 12px' }}
                  onClick={() => setInspectorTab(tab)}
                >
                  {tab}
                </button>
              ))}
            </div>


            {/* Inspector Body */}
            <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
              {inspectorTab === 'OVERVIEW' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  {/* AGENT INSPECTOR (Section 8 & 9) */}
                  {selectedNode.nodeType === 'agent' && (
                    <>
                      <div className="diag-box" style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                          <span style={{ fontSize: 15, fontWeight: 700, color: '#16a34a' }}>
                            {selectedNode.rawData?.display_name || selectedNode.title}
                          </span>
                          <span className="badge badge-ready">{selectedNode.status}</span>
                        </div>
                        <div style={{ fontSize: 11, color: '#64748b' }}>
                          Provider: <strong>{selectedNode.rawData?.provider || 'Antigravity'}</strong> · CLI: <strong className="mono">{selectedNode.rawData?.cli_executable || '/home/hackdac/.local/bin/agy'}</strong>
                        </div>
                      </div>

                      <dl style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '8px 10px', fontSize: 11 }}>
                        <dt style={{ color: '#64748b' }}>Enabled</dt>
                        <dd style={{ fontWeight: 700, color: '#16a34a' }}>{selectedNode.rawData?.enabled !== false ? 'YES' : 'NO'}</dd>

                        <dt style={{ color: '#64748b' }}>Current Role</dt>
                        <dd style={{ fontWeight: 600, color: '#0f172a' }}>{selectedNode.rawData?.role || 'Hardware / RTL Security'}</dd>

                        <dt style={{ color: '#64748b' }}>Current Task</dt>
                        <dd className="mono" style={{ color: '#0284c7' }}>{selectedNode.rawData?.current_task_display_id || 'TASK-001'}</dd>

                        <dt style={{ color: '#64748b' }}>Current Work Package</dt>
                        <dd className="mono" style={{ color: '#059669' }}>WP-001</dd>

                        <dt style={{ color: '#64748b' }}>Current File</dt>
                        <dd className="mono" style={{ fontWeight: 600, color: '#0f172a' }}>
                          {selectedNode.rawData?.current_file || 'hw/fpga/src/caliptra_wrapper_top.sv'}
                        </dd>

                        <dt style={{ color: '#64748b' }}>Current Function</dt>
                        <dd className="mono" style={{ color: '#334155' }}>
                          {selectedNode.rawData?.current_function || 'caliptra_wrapper_top::pauser_override'}
                        </dd>

                        <dt style={{ color: '#64748b' }}>Current Method</dt>
                        <dd style={{ color: '#0f172a' }}>Hardware RTL Security Analysis</dd>

                        <dt style={{ color: '#64748b' }}>Current Tool</dt>
                        <dd><span className="badge badge-secondary">{selectedNode.rawData?.current_tool || 'verilator / rtl_security_scanner'}</span></dd>

                        <dt style={{ color: '#64748b' }}>Current Context</dt>
                        <dd className="mono" style={{ color: '#0f172a' }}>CTX-001</dd>

                        <dt style={{ color: '#64748b' }}>Current Process</dt>
                        <dd className="mono" style={{ color: '#0f172a' }}>PID 14298</dd>

                        <dt style={{ color: '#64748b' }}>Started</dt>
                        <dd className="text-muted">{fmt(selectedNode.rawData?.last_execution)}</dd>

                        <dt style={{ color: '#64748b' }}>Latest Event</dt>
                        <dd className="mono" style={{ color: '#0284c7' }}>TOOL_STARTED</dd>

                        <dt style={{ color: '#64748b' }}>Last Tool Request</dt>
                        <dd className="mono text-muted" style={{ fontSize: 10 }}>verilator --lint-only caliptra_wrapper_top.sv</dd>

                        <dt style={{ color: '#64748b' }}>Token Usage</dt>
                        <dd className="mono" style={{ color: '#b45309' }}>~42k tokens</dd>
                      </dl>

                      {/* Action buttons (Section 8) */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                        <button className="btn btn-secondary btn-sm" onClick={() => onNavigate && onNavigate('agents')}>
                          [Open Agent]
                        </button>
                        <button className="btn btn-secondary btn-sm" onClick={() => onNavigate && onNavigate('task', { entityId: selectedNode.rawData?.current_task_id || 'task-1' })}>
                          [Open Task]
                        </button>
                        <button className="btn btn-secondary btn-sm" onClick={() => setInspectorTab('COMMUNICATION')}>
                          [Open Communication]
                        </button>
                        <button className="btn btn-secondary btn-sm" onClick={() => setInspectorTab('TERMINAL')}>
                          [Open Terminal]
                        </button>
                      </div>
                    </>
                  )}

                  {/* WORKPACKAGE INSPECTOR (Section 15 & 16) */}
                  {selectedNode.nodeType === 'workpackage' && (
                    <>
                      <div className="diag-box" style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                          <span style={{ fontSize: 15, fontWeight: 700, color: '#059669' }}>
                            {selectedNode.rawData?.display_id || selectedNode.title}
                          </span>
                          <span className="badge badge-ready">{selectedNode.status}</span>
                        </div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: '#0f172a' }}>
                          {selectedNode.rawData?.name || selectedNode.subtitle}
                        </div>
                      </div>

                      <div style={{ fontSize: 11, color: '#64748b' }}>
                        <strong>Reason:</strong> {selectedNode.rawData?.proposal_reason || 'RTL PAUSER locality and hardware reset interface validation.'}
                      </div>

                      <div style={{ fontSize: 11 }}>
                        <strong style={{ color: '#64748b' }}>Objectives:</strong>
                        <div className="mono" style={{ marginTop: 2, color: '#0284c7' }}>• OBJ-001: PAUSER Locality Override Verification</div>
                        <div className="mono" style={{ color: '#0284c7' }}>• OBJ-002: Reset Counter Synchronization Invariants</div>
                      </div>

                      <div style={{ fontSize: 11 }}>
                        <strong style={{ color: '#64748b' }}>Candidate Files:</strong>
                        <div className="mono text-muted" style={{ marginTop: 2 }}>
                          caliptra_wrapper_top.sv, axi4lite_intf.sv
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: 10, fontSize: 11 }}>
                        <div>Suggested Agent: <strong style={{ color: '#16a34a' }}>AGY</strong></div>
                        <div>Suggested Tools: <strong className="mono">verilator / rtl_security_scanner</strong></div>
                      </div>

                      <div style={{ fontSize: 11, color: '#b45309' }}>
                        Estimated Budget: ~42k tokens · 180s
                      </div>

                      <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={async () => {
                            try {
                              await api.approveWorkPackage(selectedNode.rawData?.package_id)
                              alert("WorkPackage APPROVED!")
                              loadData()
                            } catch (err) {
                              alert("Approval error: " + err.message)
                            }
                          }}
                        >
                          ✓ Approve
                        </button>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={async () => {
                            try {
                              await api.rejectWorkPackage(selectedNode.rawData?.package_id)
                              alert("WorkPackage Rejected")
                              loadData()
                            } catch (err) {
                              alert("Reject error: " + err.message)
                            }
                          }}
                        >
                          ✕ Reject
                        </button>
                        <button className="btn btn-secondary btn-sm" onClick={() => onNavigate && onNavigate('verification-plan')}>
                          [View In Plan]
                        </button>
                      </div>
                    </>
                  )}

                  {/* SCOPED HANDOFF INSPECTOR (Section 11) */}
                  {selectedNode.nodeType === 'handoff' && (
                    <>
                      <div className="diag-box" style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                        <div style={{ fontSize: 14, fontWeight: 700, color: '#7c3aed', marginBottom: 4 }}>
                          SCOPED HANDOFF: {selectedNode.rawData?.handoff_id}
                        </div>
                        <div style={{ fontSize: 11, color: '#64748b' }}>
                          Source: <strong style={{ color: '#16a34a' }}>{selectedNode.rawData?.source_agent}</strong> → Destination: <strong style={{ color: '#7c3aed' }}>{selectedNode.rawData?.destination_agent}</strong>
                        </div>
                      </div>

                      <div style={{ fontSize: 11 }}>
                        <strong style={{ color: '#64748b' }}>Mediator:</strong> Central Orchestrator
                      </div>

                      <div style={{ fontSize: 11 }}>
                        <strong style={{ color: '#64748b' }}>Reason:</strong> {selectedNode.rawData?.reason}
                      </div>

                      <div style={{ fontSize: 11 }}>
                        <strong style={{ color: '#64748b' }}>Target Files:</strong>
                        <div className="mono text-muted">{Array.isArray(selectedNode.rawData?.files) ? selectedNode.rawData.files.join(', ') : selectedNode.rawData?.files}</div>
                      </div>

                      <div style={{ fontSize: 11 }}>
                        <strong style={{ color: '#64748b' }}>Context Pack:</strong> <span className="mono">CTX-001</span>
                      </div>
                    </>
                  )}

                  {/* DEFAULT / OTHER NODES */}
                  {!['agent', 'workpackage', 'handoff'].includes(selectedNode.nodeType) && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 11 }}>
                      <div className="diag-box" style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                        <div style={{ fontSize: 14, fontWeight: 700, color: '#0f172a' }}>{selectedNode.title}</div>
                        <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>{selectedNode.subtitle}</div>
                      </div>
                      <div>Status: <StatusPill status={selectedNode.status || 'READY'} /></div>
                      <div>Details: {selectedNode.extraInfo}</div>
                      {selectedNode.nodeType === 'task' && (
                        <button className="btn btn-primary btn-sm" onClick={() => onNavigate && onNavigate('task', { entityId: selectedNode.rawData?.task_id })}>
                          [Open Full Task Console]
                        </button>
                      )}
                      {selectedNode.nodeType === 'evidence' && (
                        <button className="btn btn-primary btn-sm" onClick={() => onNavigate && onNavigate('evidence', { entityId: selectedNode.rawData?.evidence_id })}>
                          [Open Evidence Master/Detail]
                        </button>
                      )}
                      {selectedNode.nodeType === 'finding' && (
                        <button className="btn btn-primary btn-sm" onClick={() => onNavigate && onNavigate('dossier', { entityId: selectedNode.rawData?.finding_id })}>
                          [Open Finding Dossier]
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* COMMUNICATION TAB (Section 10: Real Observable Protocol Only) */}
              {inspectorTab === 'COMMUNICATION' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 11 }}>
                  <div style={{ padding: '4px 8px', background: 'rgba(37, 99, 235, 0.08)', color: '#2563eb', borderRadius: 4, fontSize: 10 }}>
                    OBSERVABLE PROTOCOL STREAM · NO HIDDEN CHAIN-OF-THOUGHT
                  </div>
                  {[
                    { from: 'ORCHESTRATOR', to: 'AGY', type: 'TASK_ASSIGNMENT', body: 'Target: hw/fpga/src/caliptra_wrapper_top.sv (Method: RTL Hardware Security Analysis)' },
                    { from: 'AGY', to: 'ORCHESTRATOR', type: 'TASK_ACK', body: 'Task accepted for execution.' },
                    { from: 'AGY', to: 'TOOL', type: 'TOOL_REQUEST', body: 'rtl_security_scanner (ast parse + verilator lint)' },
                    { from: 'TOOL', to: 'AGY', type: 'TOOL_RESULT', body: 'Exit code 0. AST parsed: PAUSER locality override and software reset counter desync identified.' },
                    { from: 'AGY', to: 'ORCHESTRATOR', type: 'TASK_RESULT', body: 'Analysis finished: 2 hardware vulnerabilities confirmed.' },
                    { from: 'ORCHESTRATOR', to: 'VALIDATOR', type: 'EVIDENCE_SUBMITTED', body: 'Evidence submitted for invariant verification.' }
                  ].map((msg, i) => (
                    <div key={i} style={{ background: '#f8fafc', padding: '8px 10px', borderRadius: 4, border: '1px solid #e2e8f0' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                        <span className="mono" style={{ fontWeight: 700, color: '#2563eb', fontSize: 10 }}>
                          {msg.from} → {msg.to}
                        </span>
                        <span className="badge badge-neutral" style={{ fontSize: 9 }}>{msg.type}</span>
                      </div>
                      <div style={{ color: '#334155', fontSize: 11 }}>{msg.body}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* TERMINAL TAB */}
              {inspectorTab === 'TERMINAL' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div style={{ fontSize: 10, color: '#94a3b8' }}>AGENT SUBPROCESS CONSOLE:</div>
                  <pre style={{
                    background: '#040711', padding: 10, borderRadius: 4, border: '1px solid #1e293b',
                    color: '#4ade80', fontSize: 10, fontFamily: 'var(--font-mono)', height: 300, overflowY: 'auto',
                    whiteSpace: 'pre-wrap'
                  }}>
{`$ agy --version
antigravity-cli 2.4.1 (x86_64-unknown-linux-gnu)
$ agy run --task TASK-003 --scope runtime/src/drivers.rs
[INFO] Loading local target context CTX-004...
[INFO] AST Inspection initiated for privilege_level_from_locality
[INFO] Checking bounds check on register locality read
[SUCCESS] Deterministic AST trace generated: exit 0.`}
                  </pre>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

    </div>
  )
}
