import { useState, useEffect, useRef } from 'react'
import api from '../../api'
import { fmt, shortId, StatusPill, Btn } from '../shared'

/**
 * AgentActivityStream.jsx — Phase 9.6
 * Located on the RIGHT side of the investigation workflow.
 * Exposes:
 * 1. Operational Activity Stream (Tool invocations, Observations, Hypotheses, Evidence)
 * 2. General Investigation Chat (Authoritative communication with LLMorch Orchestrator)
 * (NEVER exposes private chain-of-thought)
 */
export function AgentActivityStream({ runId, refreshSignal, onSelectEntity, width = 320 }) {
  const [activeTab, setActiveTab] = useState('STREAM') // 'STREAM' | 'CHAT'
  const [activities, setActivities] = useState([])
  const [filter, setFilter] = useState('ALL')
  const streamEndRef = useRef(null)

  // General Investigation Chat state
  const [chatMessages, setChatMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [sendingChat, setSendingChat] = useState(false)
  const chatEndRef = useRef(null)

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
          timestamp: e.timestamp || e.created_at,
          type: type,
          agent: e.agent_id || 'LLMorch Orchestrator',
          title: e.event_type || 'System Event',
          description: e.summary || e.description || JSON.stringify(e.payload || {}),
          status: 'LOGGED',
          evidence_ids: e.evidence_id ? [e.evidence_id] : [],
          entityId: e.evidence_id || e.finding_id || e.task_id,
          entityType: e.evidence_id ? 'evidence' : e.finding_id ? 'finding' : 'task',
        })
      }

      // Sort chronological descending
      combined.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
      setActivities(combined)
    } catch (err) {
      console.error('Failed to load activity stream:', err)
    }
  }

  const loadChat = async () => {
    try {
      const res = await api.investigationChatHistory(runId)
      const list = Array.isArray(res) ? res : (res?.items || [])
      setChatMessages(list)
    } catch {
      setChatMessages([])
    }
  }

  useEffect(() => {
    loadActivities()
    loadChat()
  }, [runId, refreshSignal])

  useEffect(() => {
    if (activeTab === 'CHAT') {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [chatMessages, activeTab])

  const handleSendChat = async (textToSend) => {
    const text = (textToSend || chatInput).trim()
    if (!text || sendingChat) return
    setSendingChat(true)
    try {
      await api.sendInvestigationQuery({ message: text }, runId)
      setChatInput('')
      await loadChat()
    } catch (err) {
      console.error('Failed to send investigation query:', err)
    } finally {
      setSendingChat(false)
    }
  }

  const filteredActivities = activities.filter(a => {
    if (filter === 'ALL') return true
    if (filter === 'TOOLS') return a.type === 'TOOL'
    if (filter === 'EVIDENCE') return a.type === 'EVIDENCE' || a.type === 'HYPOTHESIS'
    if (filter === 'QUESTIONS') return a.type === 'QUESTION' || a.type === 'STALL'
    return true
  })

  const SUGGESTIONS = [
    'What agents are currently working?',
    'What tools are available?',
    'What findings have been validated?',
    'What is the current run state?',
  ]

  return (
    <div style={{
      width: `${width}px`,
      minWidth: '240px',
      maxWidth: '520px',
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
      {/* Stream Header & Tab Controls */}
      <div style={{
        padding: '10px 14px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        background: 'var(--bg-elevated)',
      }}>
        {/* Main Tab Switcher */}
        <div style={{ display: 'flex', background: 'var(--bg-base)', padding: '2px', borderRadius: '6px', border: '1px solid var(--border)' }}>
          <button
            onClick={() => setActiveTab('STREAM')}
            style={{
              flex: 1,
              padding: '4px 8px',
              border: 'none',
              borderRadius: '4px',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer',
              background: activeTab === 'STREAM' ? 'var(--accent-blue)' : 'transparent',
              color: activeTab === 'STREAM' ? '#fff' : 'var(--text-muted)',
              transition: 'all 0.15s ease',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '5px',
            }}
          >
            <span>⚡</span>
            <span>Activity Stream</span>
          </button>
          <button
            onClick={() => setActiveTab('CHAT')}
            style={{
              flex: 1,
              padding: '4px 8px',
              border: 'none',
              borderRadius: '4px',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer',
              background: activeTab === 'CHAT' ? 'var(--accent-blue)' : 'transparent',
              color: activeTab === 'CHAT' ? '#fff' : 'var(--text-muted)',
              transition: 'all 0.15s ease',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '5px',
            }}
          >
            <span>💬</span>
            <span>Investigation Chat</span>
          </button>
        </div>

        {activeTab === 'STREAM' ? (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
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
            <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
              {filteredActivities.length} items
            </span>
          </div>
        ) : (
          <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
            Authoritative query interface — Ask LLMorch Orchestrator
          </div>
        )}
      </div>

      {/* View 1: Activity Stream List */}
      {activeTab === 'STREAM' && (
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
      )}

      {/* View 2: General Investigation Chat */}
      {activeTab === 'CHAT' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Quick Suggestion Chips */}
          <div style={{
            padding: '8px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            gap: '4px',
            flexWrap: 'wrap',
            background: 'var(--bg-base)',
          }}>
            {SUGGESTIONS.map(s => (
              <button
                key={s}
                onClick={() => handleSendChat(s)}
                disabled={sendingChat}
                style={{
                  fontSize: '9px',
                  background: 'var(--bg-elevated)',
                  color: 'var(--text-secondary)',
                  border: '1px solid var(--border)',
                  borderRadius: '4px',
                  padding: '2px 6px',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                + {s}
              </button>
            ))}
          </div>

          {/* Conversation history */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: '10px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
          }}>
            {chatMessages.length === 0 ? (
              <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '11px', padding: '24px 12px' }}>
                <div style={{ fontSize: '24px', marginBottom: '8px' }}>🤖</div>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                  General Investigation Chat
                </div>
                Ask the LLMorch Orchestrator anything about current agents, tools, run state, or findings.
              </div>
            ) : (
              chatMessages.map(msg => {
                const isUser = msg.sender_role === 'ANALYST'
                return (
                  <div
                    key={msg.message_id}
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: isUser ? 'flex-end' : 'flex-start',
                      gap: '3px',
                    }}
                  >
                    <div style={{ display: 'flex', gap: '6px', alignItems: 'center', fontSize: '9px', color: 'var(--text-muted)' }}>
                      <span style={{ fontWeight: 700, color: isUser ? 'var(--accent-blue)' : '#4ade80' }}>
                        {isUser ? 'Analyst' : 'LLMorch Orchestrator'}
                      </span>
                      <span>{msg.created_at ? new Date(msg.created_at).toLocaleTimeString() : ''}</span>
                    </div>

                    <div style={{
                      maxWidth: '90%',
                      padding: '8px 10px',
                      borderRadius: '6px',
                      fontSize: '11px',
                      lineHeight: '1.4',
                      background: isUser ? 'rgba(56, 189, 248, 0.15)' : 'var(--bg-card)',
                      border: isUser ? '1px solid rgba(56, 189, 248, 0.3)' : '1px solid var(--border)',
                      color: 'var(--text-primary)',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}>
                      {msg.content}
                    </div>
                  </div>
                )
              })
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Chat input box */}
          <div style={{
            padding: '8px',
            borderTop: '1px solid var(--border)',
            background: 'var(--bg-elevated)',
            display: 'flex',
            gap: '6px',
          }}>
            <input
              type="text"
              placeholder="Ask Orchestrator…"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSendChat()
              }}
              disabled={sendingChat}
              style={{
                flex: 1,
                background: 'var(--bg-base)',
                border: '1px solid var(--border)',
                borderRadius: '5px',
                padding: '6px 8px',
                fontSize: '11px',
                color: 'var(--text-primary)',
              }}
            />
            <Btn
              onClick={() => handleSendChat()}
              variant="primary"
              size="xs"
              disabled={sendingChat || !chatInput.trim()}
            >
              {sendingChat ? '…' : 'Send'}
            </Btn>
          </div>
        </div>
      )}
    </div>
  )
}
