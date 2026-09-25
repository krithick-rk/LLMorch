import { useState, useEffect, useRef } from 'react'
import api from '../../api'
import { fmt, shortId, StatusPill } from '../shared'

/**
 * AgentActivityStream.jsx — Phase 9.5
 * Located on the RIGHT side of the investigation workflow.
 * Exposes transparent operational activity ONLY:
 * - Tool invocations & completions
 * - Observations & hypotheses
 * - Evidence created
 * - Task state changes
 * - Stall warnings & questions
 * (NEVER exposes private chain-of-thought)
 */
export function AgentActivityStream({ runId, refreshSignal, onSelectEntity }) {
  const [activities, setActivities] = useState([])
  const [filter, setFilter] = useState('ALL')
  const streamEndRef = useRef(null)

  const loadActivities = async () => {
    try {
      const [eventsRes, toolExecs] = await Promise.all([
        api.timeline({ limit: 100 }).catch(() => ({ items: [] })),
        api.toolExecutions({ limit: 50 }).catch(() => ({ items: [] })),
      ])
      
      const combined = []
      
      // Add tool executions
      const execList = Array.isArray(toolExecs) ? toolExecs : (toolExecs?.items || [])
      for (const t of execList) {
        combined.push({
          id: t.execution_id || `tool-${Math.random()}`,
          timestamp: t.started_at || t.created_at,
          type: 'TOOL',
          agent: t.agent_id || 'Antigravity / AGY',
          title: `Tool: ${t.tool_name}`,
          description: t.command ? `${t.command} ${Array.isArray(t.args) ? t.args.join(' ') : ''}` : 'Tool execution completed',
          status: t.status || 'COMPLETED',
          evidence_ids: t.evidence_ids || [],
          exit_code: t.exit_code,
          duration: t.duration_seconds,
          entityId: t.execution_id,
          entityType: 'tool',
        })
      }

      // Add timeline items
      const eventList = eventsRes.items || []
      for (const e of eventList) {
        let type = 'EVENT'
        if (e.event_type?.includes('HYPOTHESIS')) type = 'HYPOTHESIS'
        else if (e.event_type?.includes('EVIDENCE')) type = 'EVIDENCE'
        else if (e.event_type?.includes('QUESTION')) type = 'QUESTION'
        else if (e.event_type?.includes('STALL')) type = 'STALL'
        else if (e.event_type?.includes('TASK')) type = 'TASK'

        combined.push({
          id: e.event_id || `evt-${Math.random()}`,
          timestamp: e.created_at || e.timestamp,
          type,
          agent: e.agent_id || 'System Orchestrator',
          title: e.event_type?.replace(/_/g, ' ') || 'State Event',
          description: e.message || e.payload?.message || JSON.stringify(e.payload || {}),
          status: e.status || 'INFO',
          entityId: e.entity_id,
          entityType: e.entity_type,
        })
      }

      // Sort by timestamp descending
      combined.sort((a, b) => new Date(b.timestamp || 0) - new Date(a.timestamp || 0))
      setActivities(combined.slice(0, 100))
    } catch (err) {
      console.error('Failed to load agent activities:', err)
    }
  }

  useEffect(() => {
    loadActivities()
  }, [runId, refreshSignal])

  const filteredActivities = activities.filter(a => {
    if (filter === 'ALL') return true
    if (filter === 'TOOLS') return a.type === 'TOOL'
    if (filter === 'EVIDENCE') return a.type === 'EVIDENCE' || a.type === 'HYPOTHESIS'
    if (filter === 'QUESTIONS') return a.type === 'QUESTION' || a.type === 'STALL'
    return true
  })

  return (
    <div style={{
      width: '320px',
      minWidth: '280px',
      maxWidth: '360px',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--bg-panel)',
      borderLeft: '1px solid var(--border)',
      borderTop: '1px solid var(--border)',
      borderBottom: '1px solid var(--border)',
      borderRadius: '8px',
      overflow: 'hidden',
    }}>
      {/* Stream Header */}
      <div style={{
        padding: '10px 14px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
        background: 'var(--bg-elevated)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
            AGENT ACTIVITY STREAM
          </div>
          <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
            {filteredActivities.length} items
          </span>
        </div>
        
        {/* Stream Filter Pills */}
        <div style={{ display: 'flex', gap: '4px' }}>
          {['ALL', 'TOOLS', 'EVIDENCE', 'QUESTIONS'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                background: filter === f ? 'var(--accent-blue)' : 'transparent',
                color: filter === f ? '#fff' : 'var(--text-muted)',
                border: '1px solid var(--border)',
                borderRadius: '4px',
                padding: '2px 6px',
                fontSize: '9px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Activity List */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '8px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
      }}>
        {filteredActivities.length === 0 ? (
          <div style={{ padding: '24px 12px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '11px' }}>
            No agent activity recorded yet. Activities will stream live during execution.
          </div>
        ) : (
          filteredActivities.map(item => (
            <div
              key={item.id}
              onClick={() => onSelectEntity && onSelectEntity(item.entityType, item.entityId)}
              style={{
                padding: '8px 10px',
                background: 'var(--bg-card)',
                border: '1px solid var(--border)',
                borderRadius: '6px',
                fontSize: '11px',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
                cursor: onSelectEntity ? 'pointer' : 'default',
                transition: 'border-color 0.15s ease',
              }}
              className="hover:border-accent"
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{
                  fontSize: '9px',
                  fontWeight: 700,
                  padding: '1px 5px',
                  borderRadius: '3px',
                  background: item.type === 'TOOL' ? '#3b82f622' : item.type === 'EVIDENCE' ? '#10b98122' : item.type === 'QUESTION' ? '#f59e0b22' : '#64748b22',
                  color: item.type === 'TOOL' ? '#60a5fa' : item.type === 'EVIDENCE' ? '#34d399' : item.type === 'QUESTION' ? '#fbbf24' : '#94a3b8',
                }}>
                  {item.type}
                </span>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : ''}
                </span>
              </div>

              <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '11px' }}>
                {item.title}
              </div>

              <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>
                {item.agent && <span style={{ color: 'var(--text-secondary)' }}>[{item.agent}] </span>}
                {item.description}
              </div>

              {item.evidence_ids && item.evidence_ids.length > 0 && (
                <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '2px' }}>
                  {item.evidence_ids.map(eid => (
                    <span
                      key={eid}
                      style={{
                        fontSize: '9px',
                        padding: '1px 4px',
                        background: '#10b98122',
                        color: '#34d399',
                        borderRadius: '3px',
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      {eid}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
        <div ref={streamEndRef} />
      </div>
    </div>
  )
}
