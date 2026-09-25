/**
 * ToolsPage.jsx — Phase 9.3
 * Tool Registry page — shows all registered tools grouped by category.
 * Data comes entirely from the backend Tool Registry (/api/tools).
 */
import { useState, useEffect, useCallback } from 'react'
import api from '../../api'
import { fmt, shortId, Mono, StatusPill, SectionHeader, Btn, Spinner, EmptyState, STATUS_COLOR } from '../shared'

const CATEGORY_ORDER = [
  'RTL', 'Formal', 'Simulation', 'Static Analysis', 'Dynamic Analysis',
  'Fuzzing', 'Binary Analysis', 'Security Scanning', 'Repository Intelligence', 'General',
]

const CATEGORY_ICON = {
  'RTL': '🔌',
  'Formal': '🧮',
  'Simulation': '⚡',
  'Static Analysis': '🔍',
  'Dynamic Analysis': '🏃',
  'Fuzzing': '🎲',
  'Binary Analysis': '🔬',
  'Security Scanning': '🛡️',
  'Repository Intelligence': '🗺️',
  'General': '🔧',
}

// ── Tool Details panel ────────────────────────────────────────────────────────

function ToolDetailPanel({ tool, executions, onClose }) {
  if (!tool) return null

  const statusColor = STATUS_COLOR[tool.status?.toUpperCase()] || '#94a3b8'

  return (
    <div style={{
      width: 400, flexShrink: 0, background: 'var(--bg-panel)',
      border: '1px solid var(--border)', borderRadius: 10,
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      boxShadow: '0 0 40px rgba(0,0,0,0.4)',
    }}>
      {/* Header */}
      <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', background: 'var(--bg-elevated)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 2 }}>
            🔧 {tool.display_name || tool.tool_name}
          </div>
          <Mono style={{ color: 'var(--text-muted)' }}>v{tool.version || '—'}</Mono>
        </div>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 18, lineHeight: 1 }}>✕</button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Status / assignment */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <StatusPill status={tool.status} />
          {tool.health && <StatusPill status={tool.health} />}
          <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 999, background: 'var(--bg-elevated)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>
            {CATEGORY_ICON[tool.category] || '🔧'} {tool.category}
          </span>
        </div>

        {/* Description */}
        {tool.description && (
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>{tool.description}</p>
        )}

        {/* Capabilities */}
        {tool.capabilities?.length > 0 && (
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Capabilities</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {tool.capabilities.map(c => (
                <span key={c} style={{ padding: '2px 8px', borderRadius: 999, fontSize: 10, background: '#2563eb22', color: '#60a5fa', border: '1px solid #2563eb44' }}>
                  {c.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Assignment */}
        <dl style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: '5px 8px', fontSize: 12 }}>
          {tool.assigned_agent && <><dt style={{ color: 'var(--text-muted)' }}>Assigned Agent</dt><dd style={{ color: 'var(--text-secondary)' }}>{tool.assigned_agent}</dd></>}
          {tool.current_task && <><dt style={{ color: 'var(--text-muted)' }}>Current Task</dt><dd><Mono>{shortId(tool.current_task)}</Mono></dd></>}
          {tool.last_execution && <><dt style={{ color: 'var(--text-muted)' }}>Last Run</dt><dd style={{ color: 'var(--text-muted)' }}>{fmt(tool.last_execution)}</dd></>}
        </dl>

        {/* Evidence */}
        {tool.evidence_ids?.length > 0 && (
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Evidence Artifacts</div>
            {tool.evidence_ids.slice(0, 5).map(id => (
              <div key={id} style={{ padding: '4px 8px', background: 'var(--bg-base)', borderRadius: 4, fontSize: 11, color: '#86efac', fontFamily: 'var(--font-mono)', marginBottom: 3 }}>
                🔐 {id}
              </div>
            ))}
          </div>
        )}

        {/* Recent executions */}
        {executions && executions.length > 0 && (
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
              Recent Executions ({executions.length})
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 200, overflowY: 'auto' }}>
              {executions.slice(0, 8).map((ex, i) => (
                <div key={ex.execution_id || i} style={{
                  background: 'var(--bg-base)', borderRadius: 5, padding: '6px 10px',
                  border: '1px solid var(--border)', fontSize: 11,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                    <Mono style={{ color: 'var(--text-muted)' }}>{shortId(ex.execution_id)}</Mono>
                    <span style={{ color: ex.exit_code === 0 ? '#4ade80' : '#f87171', fontSize: 10, fontWeight: 700 }}>
                      exit:{ex.exit_code ?? '?'}
                    </span>
                  </div>
                  {ex.command && <div style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 10, marginBottom: 2 }}>{ex.command.slice(0, 100)}</div>}
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{fmt(ex.started_at)}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Tool card ─────────────────────────────────────────────────────────────────

function ToolCard({ tool, selected, onClick }) {
  const statusColor = STATUS_COLOR[tool.status?.toUpperCase()] || '#94a3b8'
  const isActive = tool.status === 'IN_USE' || tool.status === 'RUNNING'

  return (
    <div onClick={onClick} style={{
      background: 'var(--bg-panel)', border: `1.5px solid ${selected ? 'var(--accent-blue)' : 'var(--border)'}`,
      borderRadius: 10, padding: '12px 14px', cursor: 'pointer',
      boxShadow: selected ? '0 0 0 2px #2563eb33' : '0 1px 4px rgba(0,0,0,0.2)',
      transition: 'all .15s', position: 'relative', overflow: 'hidden',
    }}>
      {/* Top accent */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: statusColor }} />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginTop: 4 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 3 }}>
            {tool.display_name || tool.tool_name}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginBottom: 6 }}>
            v{tool.version || '—'}
          </div>
        </div>
        <StatusPill status={tool.status} />
      </div>

      {tool.description && (
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 8 }}>
          {tool.description.slice(0, 90)}{tool.description.length > 90 ? '…' : ''}
        </div>
      )}

      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        {(tool.capabilities || []).slice(0, 3).map(c => (
          <span key={c} style={{ padding: '1px 6px', borderRadius: 999, fontSize: 9, background: 'var(--bg-elevated)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
            {c.replace(/_/g, ' ')}
          </span>
        ))}
        {tool.capabilities?.length > 3 && (
          <span style={{ fontSize: 9, color: 'var(--text-muted)', padding: '1px 4px' }}>+{tool.capabilities.length - 3}</span>
        )}
      </div>

      {(tool.assigned_agent || tool.last_execution) && (
        <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid var(--border)', display: 'flex', gap: 8, fontSize: 10, color: 'var(--text-muted)' }}>
          {tool.assigned_agent && <span>🤖 {tool.assigned_agent}</span>}
          {tool.last_execution && <span>🕐 {fmt(tool.last_execution)}</span>}
        </div>
      )}
    </div>
  )
}

// ── Main Tools Page ───────────────────────────────────────────────────────────

export function ToolsPage({ refreshSignal }) {
  const [tools, setTools] = useState(null)
  const [selectedTool, setSelectedTool] = useState(null)
  const [executions, setExecutions] = useState([])
  const [categoryFilter, setCategoryFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.tools()
      setTools(Array.isArray(data) ? data : [])
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load, refreshSignal])

  const selectTool = async (tool) => {
    setSelectedTool(tool)
    try {
      const execs = await api.toolExecutions({ tool_name: tool.tool_name, limit: 20 })
      setExecutions(execs || [])
    } catch { setExecutions([]) }
  }

  if (!tools) return <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}><Spinner size={32} /></div>

  // Derive categories from live tools
  const categories = ['ALL', ...CATEGORY_ORDER.filter(c => tools.some(t => t.category === c))]
  const statuses = ['ALL', 'AVAILABLE', 'IN_USE', 'COMPLETED', 'FAILED', 'DISABLED']

  const filtered = tools.filter(t => {
    const catOk = categoryFilter === 'ALL' || t.category === categoryFilter
    const statOk = statusFilter === 'ALL' || t.status?.toUpperCase() === statusFilter
    const searchOk = !search || t.display_name?.toLowerCase().includes(search.toLowerCase()) ||
      t.tool_name?.toLowerCase().includes(search.toLowerCase()) ||
      t.capabilities?.some(c => c.toLowerCase().includes(search.toLowerCase()))
    return catOk && statOk && searchOk
  })

  // Group by category
  const byCategory = {}
  filtered.forEach(t => {
    if (!byCategory[t.category]) byCategory[t.category] = []
    byCategory[t.category].push(t)
  })

  const STAT_COUNTS = {
    AVAILABLE: tools.filter(t => t.status?.toUpperCase() === 'AVAILABLE').length,
    IN_USE: tools.filter(t => t.status?.toUpperCase() === 'IN_USE').length,
    COMPLETED: tools.filter(t => t.status?.toUpperCase() === 'COMPLETED').length,
    FAILED: tools.filter(t => t.status?.toUpperCase() === 'FAILED').length,
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <SectionHeader
        title="🔧 Tool Registry"
        subtitle="All registered analysis, synthesis, and security tools"
        actions={
          <>
            <Btn onClick={load} variant="secondary" size="sm" disabled={loading}>↺ Refresh</Btn>
          </>
        }
      />

      {/* Stats */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        {Object.entries(STAT_COUNTS).map(([s, count]) => {
          const color = STATUS_COLOR[s] || '#94a3b8'
          return (
            <div key={s} style={{
              background: color + '11', border: `1px solid ${color}33`,
              borderRadius: 8, padding: '6px 12px', display: 'flex', gap: 8, alignItems: 'center',
            }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, display: 'inline-block' }} />
              <span style={{ fontSize: 11, fontWeight: 700, color }}>{count}</span>
              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{s}</span>
            </div>
          )
        })}
        <div style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)', alignSelf: 'center' }}>
          {tools.length} tools registered
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search tools, capabilities…"
          style={{
            flex: 1, minWidth: 160, padding: '6px 10px', borderRadius: 7, fontSize: 11,
            background: 'var(--bg-base)', border: '1px solid var(--border)', color: 'var(--text-primary)',
          }}
        />
        <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          {categories.slice(0, 6).map(c => (
            <button key={c} onClick={() => setCategoryFilter(c)} style={{
              padding: '4px 10px', borderRadius: 6, cursor: 'pointer', fontSize: 10, fontWeight: 600,
              background: categoryFilter === c ? 'var(--accent-blue)' : 'var(--bg-elevated)',
              color: categoryFilter === c ? '#fff' : 'var(--text-muted)',
              border: `1px solid ${categoryFilter === c ? 'var(--accent-blue)' : 'var(--border)'}`,
              transition: 'all .15s',
            }}>
              {CATEGORY_ICON[c] || '🔧'} {c}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 3 }}>
          {statuses.map(s => (
            <button key={s} onClick={() => setStatusFilter(s)} style={{
              padding: '4px 9px', border: `1px solid ${statusFilter === s ? 'var(--accent-blue)' : 'var(--border)'}`,
              borderRadius: 6, cursor: 'pointer', fontSize: 9, fontWeight: 700,
              background: statusFilter === s ? 'var(--accent-blue)' : 'var(--bg-elevated)',
              color: statusFilter === s ? '#fff' : 'var(--text-muted)', transition: 'all .15s',
            }}>{s}</button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, display: 'flex', gap: 12, overflow: 'hidden', minHeight: 0 }}>
        {/* Tool list */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {filtered.length === 0 ? (
            <EmptyState icon="🔧" title="No tools match filter" subtitle="Try clearing the search or changing category/status filters" />
          ) : (
            CATEGORY_ORDER.filter(c => byCategory[c]).map(cat => (
              <div key={cat} style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span>{CATEGORY_ICON[cat] || '🔧'}</span>
                  <span>{cat}</span>
                  <span style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 400 }}>({byCategory[cat].length})</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 10 }}>
                  {byCategory[cat].map(tool => (
                    <ToolCard
                      key={tool.tool_name}
                      tool={tool}
                      selected={selectedTool?.tool_name === tool.tool_name}
                      onClick={() => selectTool(tool)}
                    />
                  ))}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Detail panel */}
        {selectedTool && (
          <ToolDetailPanel
            tool={selectedTool}
            executions={executions}
            onClose={() => setSelectedTool(null)}
          />
        )}
      </div>
    </div>
  )
}
