/**
 * CommaAssistant.jsx — Autonomous Hardware Security & SoC Engineering Assistant
 * Authoritative COMMA Assistant powered exclusively by AGY CLI runtime.
 * Reads live SQLite database state, logs, tasks, verification plans, and token telemetry.
 * Zero Claude invocations (enterprise policy enforced).
 */

import React, { useState, useEffect, useRef, useCallback } from 'react'
import api from '../api'

function renderMarkdownText(text) {
  if (!text) return null

  // Split by line
  const lines = text.split('\n')
  const elements = []

  let inCodeBlock = false
  let codeBlockLines = []
  let codeBlockLang = ''

  lines.forEach((line, idx) => {
    // Code block toggle
    if (line.trim().startsWith('```')) {
      if (inCodeBlock) {
        // End code block
        elements.push(
          <pre
            key={`cb-${idx}`}
            style={{
              background: '#090d16',
              border: '1px solid var(--border-dim)',
              borderRadius: 4,
              padding: '10px 12px',
              margin: '8px 0',
              overflowX: 'auto',
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: '#38bdf8',
              lineHeight: 1.45,
            }}
          >
            <code>{codeBlockLines.join('\n')}</code>
          </pre>
        )
        codeBlockLines = []
        inCodeBlock = false
      } else {
        inCodeBlock = true
        codeBlockLang = line.trim().slice(3).trim()
      }
      return
    }

    if (inCodeBlock) {
      codeBlockLines.push(line)
      return
    }

    // Bullet point
    const bulletMatch = line.match(/^(\s*)[*•-]\s+(.*)$/)
    if (bulletMatch) {
      const indent = bulletMatch[1].length
      elements.push(
        <div
          key={`li-${idx}`}
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: 6,
            marginLeft: indent > 0 ? indent * 8 + 8 : 4,
            marginBottom: 4,
            fontSize: 12,
            lineHeight: 1.5,
          }}
        >
          <span style={{ color: 'var(--blue)', fontSize: 10 }}>●</span>
          <span>{formatInlineText(bulletMatch[2])}</span>
        </div>
      )
      return
    }

    // Headers
    if (line.startsWith('### ')) {
      elements.push(
        <h4 key={`h3-${idx}`} style={{ fontSize: 13, fontWeight: 700, margin: '12px 0 6px', color: 'var(--text-bright)' }}>
          {formatInlineText(line.slice(4))}
        </h4>
      )
      return
    }
    if (line.startsWith('## ') || line.startsWith('# ')) {
      elements.push(
        <h3 key={`h2-${idx}`} style={{ fontSize: 14, fontWeight: 700, margin: '14px 0 8px', color: 'var(--text-bright)', borderBottom: '1px solid var(--border-dim)', paddingBottom: 4 }}>
          {formatInlineText(line.replace(/^#+\s*/, ''))}
        </h3>
      )
      return
    }

    // Empty line
    if (!line.trim()) {
      elements.push(<div key={`sp-${idx}`} style={{ height: 6 }} />)
      return
    }

    // Regular line
    elements.push(
      <p key={`p-${idx}`} style={{ margin: '0 0 6px', fontSize: 12, lineHeight: 1.55 }}>
        {formatInlineText(line)}
      </p>
    )
  })

  // Flush open code block if any
  if (inCodeBlock && codeBlockLines.length > 0) {
    elements.push(
      <pre
        key="cb-end"
        style={{
          background: '#090d16',
          border: '1px solid var(--border-dim)',
          borderRadius: 4,
          padding: '10px 12px',
          margin: '8px 0',
          overflowX: 'auto',
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          color: '#38bdf8',
        }}
      >
        <code>{codeBlockLines.join('\n')}</code>
      </pre>
    )
  }

  return <div>{elements}</div>
}

function formatInlineText(text) {
  if (!text) return ''

  // Split by bold (**...**) and inline code (`...`)
  const parts = []
  const regex = /(\*\*.*?\*\*|`.*?`)/g
  let lastIdx = 0
  let match

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIdx) {
      parts.push(text.slice(lastIdx, match.index))
    }
    const token = match[0]
    if (token.startsWith('**') && token.endsWith('**')) {
      const boldContent = token.slice(2, -2)
      // Check for severity keywords
      let color = 'inherit'
      if (boldContent.includes('CRITICAL')) color = 'var(--red, #ef4444)'
      else if (boldContent.includes('HIGH')) color = '#f97316'
      else if (boldContent.includes('MEDIUM')) color = '#eab308'
      else if (boldContent.includes('LOW')) color = 'var(--blue, #38bdf8)'
      parts.push(
        <strong key={`b-${match.index}`} style={{ fontWeight: 700, color }}>
          {boldContent}
        </strong>
      )
    } else if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(
        <code
          key={`c-${match.index}`}
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.9em',
            background: 'var(--bg-subtle, #1e293b)',
            padding: '1px 5px',
            borderRadius: 3,
            color: '#38bdf8',
            border: '1px solid var(--border-dim, rgba(255,255,255,0.08))',
          }}
        >
          {token.slice(1, -1)}
        </code>
      )
    }
    lastIdx = regex.lastIndex
  }

  if (lastIdx < text.length) {
    parts.push(text.slice(lastIdx))
  }

  return parts
}

export default function CommaAssistant({
  isOpen,
  onClose,
  activeProject = null,
  currentPage = 'workspace',
  currentRun = null,
  onOpenCreateTask = null,
}) {
  const [messages, setMessages] = useState([])
  const [inputQuery, setInputQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [statusInfo, setStatusInfo] = useState(null)
  const [errorMsg, setErrorMsg] = useState('')
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Quick suggestion chips
  const SUGGESTIONS = [
    { label: '📊 Project Status & Findings', query: 'What is the current project status and confirmed findings?' },
    { label: '⚠️ Explain CRITICAL Finding', query: 'Explain the PAUSER Privilege Truncation critical vulnerability and its affected RTL files.' },
    { label: '🔍 Inspect Queued Tasks', query: 'Why are there queued tasks and what are their execution prerequisites?' },
    { label: '💰 Token Telemetry Audit', query: 'What is the token budget, consumption, and telemetry source accounting?' },
    { label: '⚡ Propose RTL Inspection Task', query: 'Create task to inspect caliptra_wrapper_top.sv for AXI privilege violations' },
  ]

  // Load status and history on open
  const loadHistory = useCallback(async () => {
    try {
      setLoading(true)
      const [hist, st] = await Promise.all([
        api.commaHistory(activeProject?.project_id, 50).catch(() => []),
        api.commaStatus().catch(() => null),
      ])
      setMessages(hist || [])
      setStatusInfo(st)
    } catch (err) {
      console.error('Failed to load COMMA history:', err)
    } finally {
      setLoading(false)
    }
  }, [activeProject?.project_id])

  useEffect(() => {
    if (isOpen) {
      loadHistory()
      setTimeout(() => inputRef.current?.focus(), 150)
    }
  }, [isOpen, loadHistory])

  // Scroll to bottom whenever messages change
  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isOpen, loading])

  // Submit query
  const handleSend = async (customQuery = null) => {
    const queryToSend = (customQuery !== null ? customQuery : inputQuery).trim()
    if (!queryToSend || loading) return

    setInputQuery('')
    setErrorMsg('')

    // Optimistically append user message
    const tempUserMsg = {
      message_id: `temp-${Date.now()}`,
      sender_type: 'USER',
      sender_name: 'Analyst',
      content: queryToSend,
      metadata: { page: currentPage },
      created_at: new Date().toISOString(),
    }
    setMessages(prev => [...prev, tempUserMsg])
    setLoading(true)

    try {
      const res = await api.commaQuery({
        query: queryToSend,
        project_id: activeProject?.project_id,
        current_page: currentPage,
        context: {
          run_id: currentRun?.run_id,
          project_name: activeProject?.name,
        },
      })

      const assistantMsg = {
        message_id: `comma-${Date.now()}`,
        sender_type: 'AGENT',
        sender_name: 'COMMA (AGY)',
        content: res.answer || 'Response received.',
        metadata: {
          tokens: res.token_usage,
          proposal: res.task_proposal,
          model: res.model,
          powered_by: res.powered_by,
        },
        created_at: res.timestamp || new Date().toISOString(),
      }

      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      console.error('COMMA query failed:', err)
      setErrorMsg(err.message || 'Failed to query COMMA assistant.')
      const errorMsgObj = {
        message_id: `err-${Date.now()}`,
        sender_type: 'AGENT',
        sender_name: 'COMMA (AGY)',
        content: `Error contacting COMMA assistant: ${err.message || 'Unknown network error'}. Please check backend logs.`,
        metadata: { isError: true },
        created_at: new Date().toISOString(),
      }
      setMessages(prev => [...prev, errorMsgObj])
    } finally {
      setLoading(false)
    }
  }

  // Clear conversation history
  const handleClearHistory = async () => {
    if (!window.confirm('Clear COMMA conversation history?')) return
    try {
      await api.clearCommaHistory(activeProject?.project_id)
      setMessages([])
    } catch (err) {
      console.error('Failed to clear COMMA history:', err)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  if (!isOpen) return null

  return (
    <div
      id="comma-assistant-backdrop"
      onClick={onClose}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        zIndex: 9999,
        background: 'rgba(0, 0, 0, 0.45)',
        backdropFilter: 'blur(3px)',
        display: 'flex',
        justifyContent: 'flex-end',
        transition: 'all 0.2s ease',
      }}
    >
      <div
        id="comma-assistant-drawer"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '600px',
          maxWidth: '92vw',
          height: '100vh',
          background: 'var(--bg-base)',
          borderLeft: '1px solid var(--border)',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '-10px 0 40px rgba(0, 0, 0, 0.5)',
          overflow: 'hidden',
        }}
      >
        {/* ── Top Header ──────────────────────────────────────────────────────── */}
        <div
          style={{
            padding: '14px 18px',
            background: 'var(--bg-surface)',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 6,
                background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
                fontSize: 16,
                fontWeight: 800,
                boxShadow: '0 0 12px rgba(2, 132, 199, 0.4)',
              }}
            >
              ⚡
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-bright)' }}>
                  COMMA Assistant
                </span>
                <span
                  className="badge badge-success mono"
                  style={{ fontSize: 10, padding: '1px 6px', fontWeight: 600 }}
                  title="Sole Autonomous Execution Engine: AGY CLI"
                >
                  AGY • Gemini 3.6 Low
                </span>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                Autonomous Hardware Vulnerability Research & Telemetry
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button
              className="btn btn-ghost btn-sm"
              onClick={handleClearHistory}
              title="Clear Conversation History"
              style={{ fontSize: 12, padding: '4px 8px' }}
            >
              🗑 Clear
            </button>
            <button
              className="btn btn-ghost btn-sm"
              onClick={loadHistory}
              title="Refresh Conversation"
              style={{ fontSize: 13, padding: '4px 8px' }}
            >
              ↺
            </button>
            <button
              className="btn btn-ghost btn-sm"
              onClick={onClose}
              title="Close COMMA Assistant"
              style={{ fontSize: 16, padding: '2px 8px', color: 'var(--text-muted)' }}
            >
              ✕
            </button>
          </div>
        </div>

        {/* ── Status & Active Context Bar ──────────────────────────────────────── */}
        <div
          style={{
            padding: '8px 18px',
            background: 'var(--bg-subtle)',
            borderBottom: '1px solid var(--border-dim)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: 11,
            fontFamily: 'var(--font-mono)',
            flexShrink: 0,
            flexWrap: 'wrap',
            gap: 6,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>PROJECT: </span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                {activeProject?.name || activeProject?.project_id || 'Active'}
              </span>
            </div>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>CONTEXT: </span>
              <span style={{ color: 'var(--blue)' }}>{currentPage}</span>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span
              style={{
                fontSize: 10,
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.25)',
                padding: '2px 6px',
                borderRadius: 3,
                color: '#f87171',
              }}
            >
              Claude: 0 Invocations (Enforced)
            </span>
          </div>
        </div>

        {/* ── Conversation Message Stream ──────────────────────────────────────── */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '16px 18px',
            display: 'flex',
            flexDirection: 'column',
            gap: 14,
          }}
        >
          {messages.length === 0 && !loading && (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '40px 20px',
                textAlign: 'center',
                color: 'var(--text-muted)',
              }}
            >
              <div
                style={{
                  width: 52,
                  height: 52,
                  borderRadius: '50%',
                  background: 'rgba(2, 132, 199, 0.1)',
                  border: '1px solid rgba(2, 132, 199, 0.25)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 24,
                  marginBottom: 14,
                  color: 'var(--blue)',
                }}
              >
                ⚡
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
                COMMA Engineering Assistant Ready
              </div>
              <p style={{ fontSize: 12, maxWidth: 380, lineHeight: 1.5, margin: 0 }}>
                Directly connected to SQLite backend state, verification plans, task DAGs, confirmed hardware findings, and AGY CLI.
              </p>
            </div>
          )}

          {messages.map((msg, index) => {
            const isUser = msg.sender_type === 'USER'
            const proposal = msg.metadata?.proposal
            const tokens = msg.metadata?.tokens

            return (
              <div
                key={msg.message_id || index}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: isUser ? 'flex-end' : 'flex-start',
                }}
              >
                {/* Sender Tag & Timestamp */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    fontSize: 10,
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--text-muted)',
                    marginBottom: 4,
                  }}
                >
                  <span style={{ fontWeight: 600, color: isUser ? '#38bdf8' : 'var(--amber, #f59e0b)' }}>
                    {isUser ? '👤 Analyst' : '⚡ COMMA (AGY)'}
                  </span>
                  <span>•</span>
                  <span>
                    {msg.created_at ? new Date(msg.created_at).toLocaleTimeString() : 'now'}
                  </span>
                </div>

                {/* Bubble Container */}
                <div
                  style={{
                    maxWidth: '92%',
                    background: isUser ? 'rgba(2, 132, 199, 0.12)' : 'var(--bg-surface)',
                    border: `1px solid ${isUser ? 'rgba(2, 132, 199, 0.35)' : 'var(--border)'}`,
                    borderRadius: isUser ? '8px 8px 2px 8px' : '8px 8px 8px 2px',
                    padding: '12px 14px',
                    color: 'var(--text-primary)',
                    boxShadow: isUser
                      ? '0 2px 8px rgba(2, 132, 199, 0.08)'
                      : '0 2px 8px rgba(0, 0, 0, 0.25)',
                  }}
                >
                  {/* Markdown or plain text content */}
                  {renderMarkdownText(msg.content)}

                  {/* Task Proposal Card (if generated) */}
                  {proposal && (
                    <div
                      style={{
                        marginTop: 12,
                        padding: 12,
                        background: 'rgba(2, 132, 199, 0.08)',
                        border: '1px solid rgba(2, 132, 199, 0.3)',
                        borderRadius: 6,
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          marginBottom: 8,
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ color: 'var(--blue)', fontSize: 13 }}>📋</span>
                          <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)' }}>
                            Synthesized Task Proposal
                          </span>
                        </div>
                        <span className="badge badge-info mono" style={{ fontSize: 9 }}>
                          {proposal.method || 'RTL Analysis'}
                        </span>
                      </div>

                      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 6 }}>
                        <strong>Objective:</strong> {proposal.objective}
                      </div>

                      {proposal.target_files && proposal.target_files.length > 0 && (
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>
                          <strong>Target Files:</strong>{' '}
                          <span className="mono" style={{ color: '#38bdf8' }}>
                            {proposal.target_files.join(', ')}
                          </span>
                        </div>
                      )}

                      <div
                        style={{
                          display: 'flex',
                          gap: 12,
                          fontSize: 10,
                          fontFamily: 'var(--font-mono)',
                          color: 'var(--text-muted)',
                          marginBottom: 10,
                        }}
                      >
                        <div>
                          Agent: <span style={{ color: 'var(--text-primary)' }}>{proposal.agent_id}</span>
                        </div>
                        <div>
                          Budget: <span style={{ color: 'var(--text-primary)' }}>{proposal.token_budget} tokens</span>
                        </div>
                      </div>

                      {onOpenCreateTask && (
                        <button
                          id="btn-comma-dispatch-task"
                          className="btn btn-primary btn-sm"
                          style={{
                            width: '100%',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: 6,
                            padding: '6px 12px',
                            fontWeight: 600,
                            fontSize: 11,
                          }}
                          onClick={() => onOpenCreateTask(proposal)}
                        >
                          <span>⚡ Review & Enqueue in Pipeline</span>
                        </button>
                      )}
                    </div>
                  )}

                  {/* Telemetry Footer */}
                  {tokens && (
                    <div
                      style={{
                        marginTop: 8,
                        paddingTop: 6,
                        borderTop: '1px solid var(--border-dim)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        fontSize: 10,
                        fontFamily: 'var(--font-mono)',
                        color: 'var(--text-muted)',
                      }}
                    >
                      <div style={{ display: 'flex', gap: 10 }}>
                        {tokens.total_tokens !== undefined && (
                          <span>Tokens: {tokens.total_tokens?.toLocaleString()}</span>
                        )}
                        {tokens.remaining !== undefined && (
                          <span>Remaining: {tokens.remaining?.toLocaleString()}</span>
                        )}
                      </div>
                      <span style={{ color: 'var(--blue)' }}>
                        {tokens.telemetry_source || 'ACTUAL'}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )
          })}

          {loading && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
              <div
                style={{
                  fontSize: 10,
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-muted)',
                  marginBottom: 4,
                }}
              >
                ⚡ COMMA (AGY) • Running...
              </div>
              <div
                style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border)',
                  borderRadius: '8px 8px 8px 2px',
                  padding: '12px 16px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  color: 'var(--text-secondary)',
                  fontSize: 12,
                }}
              >
                <div className="spinner" style={{ width: 14, height: 14 }} />
                <span>Compiling authoritative SQLite state and consulting AGY CLI runtime...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* ── Suggested Prompts Chips ─────────────────────────────────────────── */}
        <div
          style={{
            padding: '8px 18px',
            background: 'var(--bg-surface)',
            borderTop: '1px solid var(--border)',
            display: 'flex',
            gap: 6,
            overflowX: 'auto',
            whiteSpace: 'nowrap',
            flexShrink: 0,
          }}
        >
          {SUGGESTIONS.map((item, idx) => (
            <button
              key={idx}
              className="btn btn-secondary btn-sm"
              style={{
                fontSize: 11,
                padding: '4px 8px',
                borderRadius: 12,
                border: '1px solid var(--border)',
                background: 'var(--bg-subtle)',
                color: 'var(--text-secondary)',
                cursor: loading ? 'not-allowed' : 'pointer',
              }}
              disabled={loading}
              onClick={() => handleSend(item.query)}
            >
              {item.label}
            </button>
          ))}
        </div>

        {/* ── Query Input Area ────────────────────────────────────────────────── */}
        <div
          style={{
            padding: '12px 18px',
            background: 'var(--bg-surface)',
            borderTop: '1px solid var(--border-dim)',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
            <textarea
              ref={inputRef}
              id="comma-query-input"
              rows={2}
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
              placeholder="Ask COMMA about state, findings, tasks, or type 'create task to inspect...'"
              style={{
                flex: 1,
                background: 'var(--bg-base)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                padding: '8px 12px',
                color: 'var(--text-primary)',
                fontFamily: 'inherit',
                fontSize: 12,
                resize: 'none',
                outline: 'none',
                lineHeight: 1.4,
              }}
            />
            <button
              id="btn-comma-submit"
              className="btn btn-primary"
              onClick={() => handleSend()}
              disabled={loading || !inputQuery.trim()}
              style={{
                height: 48,
                padding: '0 16px',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontWeight: 600,
              }}
            >
              {loading ? (
                <div className="spinner" style={{ width: 14, height: 14 }} />
              ) : (
                <>
                  <span>Send</span>
                  <span>▶</span>
                </>
              )}
            </button>
          </div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 10,
              color: 'var(--text-muted)',
              marginTop: 6,
            }}
          >
            <span>Enter to send, Shift+Enter for new line</span>
            <span className="mono">Runtime: AGY CLI (Gemini 3.6 Low)</span>
          </div>
        </div>
      </div>
    </div>
  )
}
