/**
 * AgentWorkroom.jsx — Phase 9.3
 * Detail panel shown when an Agent or Task node is clicked.
 */
import { useState, useEffect, useCallback } from 'react'
import api from '../../api'
import { fmt, shortId, Mono, StatusPill, SeverityBadge, Btn, Spinner } from '../shared'

// ── Analyst Instruction Panel ─────────────────────────────────────────────────

export function AnalystInstructionPanel({ taskId, attempts, onSubmit }) {
  const [text, setText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)

  const submit = async () => {
    if (!text.trim()) return
    setSubmitting(true); setError(null); setSuccess(false)
    try {
      await api.submitAnalystInstruction({ task_id: taskId, instruction: text.trim() })
      setText(''); setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
      onSubmit && onSubmit()
    } catch (e) { setError(e.message) }
    finally { setSubmitting(false) }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6 }}>
        Submitting an instruction creates a new attempt. Previous attempt output is immutable.
      </div>
      <textarea
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder="e.g. Focus on the AXI4-Lite write-response path. Check if valid is held high without checking ready…&#10;&#10;Ctrl+Enter to submit"
        style={{
          width: '100%', minHeight: 90, resize: 'vertical',
          background: 'var(--bg-base)', border: `1px solid ${success ? '#4ade80' : error ? '#f87171' : 'var(--border)'}`,
          borderRadius: 6, padding: '8px 10px', fontSize: 12,
          color: 'var(--text-primary)', fontFamily: 'inherit', lineHeight: 1.5,
          boxSizing: 'border-box', transition: 'border-color .2s',
        }}
        onKeyDown={e => { if (e.ctrlKey && e.key === 'Enter') submit() }}
      />
      {error && <div style={{ color: '#f87171', fontSize: 11 }}>⚠ {error}</div>}
      {success && <div style={{ color: '#4ade80', fontSize: 11 }}>✓ Instruction submitted — new attempt created</div>}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        {text && <Btn onClick={() => setText('')} variant="ghost" size="xs">Clear</Btn>}
        <Btn onClick={submit} disabled={submitting || !text.trim()} variant="primary" size="sm">
          {submitting ? '…' : '⏎ Submit  (Ctrl+↩)'}
        </Btn>
      </div>

      {/* Attempt lineage */}
      {attempts && attempts.length > 0 && (
        <div style={{ marginTop: 4 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
            Attempt Lineage ({attempts.length})
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 260, overflowY: 'auto' }}>
            {attempts.map((a, i) => (
              <div key={a.attempt_id || i} style={{
                background: 'var(--bg-base)', borderRadius: 6, padding: '8px 10px',
                border: '1px solid var(--border)', fontSize: 11,
                borderLeft: `3px solid ${a.attempt_number === attempts.length ? 'var(--accent-blue)' : 'var(--border)'}`,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontWeight: 700, color: 'var(--text-secondary)' }}>
                    Attempt #{a.attempt_number || (i + 1)}
                  </span>
                  <StatusPill status={a.status} />
                </div>
                {a.instruction_text && (
                  <div style={{ color: 'var(--text-muted)', lineHeight: 1.5, fontStyle: 'italic', fontSize: 10 }}>
                    "{a.instruction_text.slice(0, 150)}{a.instruction_text.length > 150 ? '…' : ''}"
                  </div>
                )}
                {a.approach && !a.instruction_text && (
                  <div style={{ color: 'var(--text-muted)', fontSize: 10 }}>{a.approach.slice(0, 120)}</div>
                )}
                <div style={{ color: 'var(--text-muted)', marginTop: 4, fontSize: 10 }}>
                  {fmt(a.started_at)} {a.agent_id ? `• ${a.agent_id}` : ''}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Tool Feed ─────────────────────────────────────────────────────────────────

export function ToolExecutionFeed({ tools }) {
  if (!tools || tools.length === 0) {
    return <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '12px 0' }}>No tool executions recorded yet.</div>
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 300, overflowY: 'auto' }}>
      {tools.map((t, i) => (
        <div key={t.execution_id || i} style={{
          background: 'var(--bg-base)', borderRadius: 6, padding: '8px 10px',
          border: '1px solid var(--border)', fontSize: 11,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontWeight: 700, color: 'var(--text-secondary)' }}>🔧 {t.tool_name || '—'}</span>
            <span style={{
              padding: '1px 6px', borderRadius: 4, fontSize: 10, fontWeight: 700,
              background: t.exit_code === 0 ? '#4ade8022' : '#f8717122',
              color: t.exit_code === 0 ? '#4ade80' : '#f87171',
            }}>exit:{t.exit_code ?? '?'}</span>
          </div>
          {t.command && (
            <div style={{
              color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 10,
              marginBottom: 4, wordBreak: 'break-all', lineHeight: 1.4,
            }}>{t.command.slice(0, 180)}</div>
          )}
          {t.execution_result && (
            <div style={{ color: 'var(--text-muted)', fontSize: 10, lineHeight: 1.4, marginBottom: 4 }}>
              {t.execution_result.slice(0, 120)}
            </div>
          )}
          <div style={{ display: 'flex', gap: 10, fontSize: 10, color: 'var(--text-muted)' }}>
            <span>{fmt(t.started_at)}</span>
            {t.duration_ms && <span>{t.duration_ms}ms</span>}
            {t.evidence_ids?.length > 0 && (
              <span style={{ color: '#4ade80' }}>📎 {t.evidence_ids.length} evidence</span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── PoC Lifecycle Panel ───────────────────────────────────────────────────────

export function PoCLifecyclePanel({ finding, onRefresh }) {
  const [poc, setPoc] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const generatePoC = async () => {
    setLoading(true); setError(null)
    try { setPoc(await api.generatePoC({ finding_id: finding.finding_id })) }
    catch (e) { setError(e.message) } finally { setLoading(false) }
  }
  const executePoC = async () => {
    setLoading(true); setError(null)
    try { setPoc(await api.executePoC({ reproducer_id: poc.reproducer_id })) }
    catch (e) { setError(e.message) } finally { setLoading(false) }
  }
  const validatePoC = async () => {
    setLoading(true); setError(null)
    try { setPoc(await api.validatePoC({ reproducer_id: poc.reproducer_id })); onRefresh && onRefresh() }
    catch (e) { setError(e.message) } finally { setLoading(false) }
  }

  const STATE_STEP = { DRAFT: 0, REPRODUCED: 1, VALIDATED: 2, REJECTED: -1 }
  const step = poc ? (STATE_STEP[poc.state] ?? 0) : -1

  const Dot = ({ n, label, active, done, failed }) => (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, flex: 1 }}>
      <div style={{
        width: 26, height: 26, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 11, fontWeight: 700,
        background: failed ? '#ef444422' : done ? '#4ade8022' : active ? '#38bdf822' : 'var(--bg-base)',
        color: failed ? '#ef4444' : done ? '#4ade80' : active ? '#38bdf8' : 'var(--text-muted)',
        border: `2px solid ${failed ? '#ef4444' : done ? '#4ade80' : active ? '#38bdf8' : 'var(--border)'}`,
      }}>{done && !failed ? '✓' : failed ? '✗' : n}</div>
      <span style={{ fontSize: 9, color: done || active ? 'var(--text-secondary)' : 'var(--text-muted)', textAlign: 'center' }}>{label}</span>
    </div>
  )
  const Line = ({ done }) => (
    <div style={{ width: 28, height: 2, background: done ? '#4ade80' : 'var(--border)', marginTop: 13, flexShrink: 0, transition: 'background .3s' }} />
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{
        background: '#f59e0b11', border: '1px solid #f59e0b44', borderRadius: 6, padding: '8px 10px',
        fontSize: 11, color: '#f59e0b', lineHeight: 1.6,
      }}>
        ⚠ Agent-generated PoC is <strong>DRAFT</strong> until Validator confirms.
        Sandbox execution is required before validation.
      </div>

      <div style={{ display: 'flex', alignItems: 'flex-start', padding: '4px 0' }}>
        <Dot n={1} label="Generate" active={step < 0} done={step >= 0} />
        <Line done={step >= 1} />
        <Dot n={2} label="Sandbox" active={step === 0} done={step >= 1} />
        <Line done={step >= 2} />
        <Dot n={3} label="Validate" active={step === 1} done={step >= 2} failed={poc?.state === 'REJECTED'} />
      </div>

      {poc && (
        <div style={{
          background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 6,
          padding: 10, fontSize: 10, fontFamily: 'var(--font-mono)', maxHeight: 140,
          overflowY: 'auto', color: 'var(--text-secondary)', lineHeight: 1.6, whiteSpace: 'pre-wrap',
        }}>{poc.code || poc.content || '(no code body)'}</div>
      )}
      {error && <div style={{ color: '#f87171', fontSize: 11 }}>⚠ {error}</div>}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {step < 0 && <Btn onClick={generatePoC} disabled={loading} variant="secondary" size="sm">⚡ Generate PoC</Btn>}
        {step === 0 && <Btn onClick={executePoC} disabled={loading} variant="warning" size="sm">▶ Execute in Sandbox</Btn>}
        {step === 1 && <Btn onClick={validatePoC} disabled={loading} variant="success" size="sm">✓ Request Validation</Btn>}
        {step >= 0 && <Btn onClick={generatePoC} disabled={loading} variant="ghost" size="sm">↺ Regenerate</Btn>}
      </div>

      {poc && (
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)' }}>
          <span>State: <strong style={{ color: step >= 2 ? '#4ade80' : poc.state === 'REJECTED' ? '#f87171' : '#fbbf24' }}>{poc.state}</strong></span>
          <span>v{poc.version || 1} · <Mono>{shortId(poc.reproducer_id)}</Mono></span>
        </div>
      )}
    </div>
  )
}

// ── Agent Workroom ────────────────────────────────────────────────────────────

export function AgentWorkroom({ selectedNode, agents, onClose, onRefresh }) {
  const [tab, setTab] = useState('overview')
  const [attempts, setAttempts] = useState([])
  const [tools, setTools] = useState([])
  const [finding, setFinding] = useState(null)
  const [loading, setLoading] = useState(false)

  const nodeType = selectedNode?.data?.nodeType
  const rawData = selectedNode?.data?.rawData

  const loadDetails = useCallback(async () => {
    if (!rawData) return
    setLoading(true)
    try {
      if (nodeType === 'task' && rawData.task_id) {
        const [att, te, findings] = await Promise.all([
          api.taskAttempts(rawData.task_id).catch(() => ({ items: [] })),
          api.toolExecutions({ task_id: rawData.task_id }).catch(() => ({ items: [] })),
          api.findings({ task_id: rawData.task_id, limit: 1 }).catch(() => ({ items: [] })),
        ])
        setAttempts(att.items || [])
        setTools(te.items || [])
        setFinding((findings.items || [])[0] || null)
      } else if (nodeType === 'agent' && rawData.agent_id) {
        const te = await api.toolExecutions({ agent_id: rawData.agent_id }).catch(() => ({ items: [] }))
        setTools(te.items || [])
      }
    } finally { setLoading(false) }
  }, [rawData, nodeType])

  useEffect(() => {
    setTab('overview')
    setAttempts([]); setTools([]); setFinding(null)
    loadDetails()
  }, [loadDetails])

  if (!selectedNode) return null

  const TABS_TASK = ['overview', 'instructions', 'tools', 'poc']
  const TABS_AGENT = ['overview', 'tools']
  const TABS_OTHER = ['overview']
  const tabs = nodeType === 'task' ? TABS_TASK : nodeType === 'agent' ? TABS_AGENT : TABS_OTHER

  const TAB_LABEL = {
    overview: '📋 Info',
    instructions: '📝 Instruct',
    tools: '🔧 Tools',
    poc: '⚡ PoC',
  }

  const assignedAgent = agents?.find(a => a.agent_id === rawData?.agent_id)

  return (
    <div style={{
      width: 420, flexShrink: 0, background: 'var(--bg-panel)',
      border: '1px solid var(--border)', borderRadius: 10,
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      boxShadow: '0 0 40px rgba(0,0,0,0.5)',
    }}>
      {/* Header */}
      <div style={{
        padding: '12px 16px', borderBottom: '1px solid var(--border)',
        background: 'var(--bg-elevated)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
      }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 2 }}>
            🔬 {nodeType === 'agent' ? 'Agent' : nodeType === 'task' ? 'Task' : nodeType?.charAt(0).toUpperCase() + nodeType?.slice(1)} Detail
          </div>
          <Mono style={{ color: 'var(--text-muted)' }}>
            {selectedNode?.data?.label || shortId(rawData?.task_id || rawData?.agent_id || '')}
          </Mono>
        </div>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 18, lineHeight: 1 }}>✕</button>
      </div>

      {/* Summary strip */}
      <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        {rawData?.status && <StatusPill status={rawData.status} />}
        {rawData?.health && <StatusPill status={rawData.health} />}
        {rawData?.severity && <SeverityBadge severity={rawData.severity} />}
        {rawData?.role && <span style={{ fontSize: 10, color: 'var(--text-muted)', fontStyle: 'italic' }}>{rawData.role}</span>}
        {assignedAgent && nodeType === 'task' && (
          <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 999, background: 'var(--bg-elevated)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>
            🤖 {assignedAgent.name || assignedAgent.agent_id}
          </span>
        )}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', background: 'var(--bg-base)', flexShrink: 0 }}>
        {tabs.map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            flex: 1, padding: '8px 4px', border: 'none', cursor: 'pointer', fontSize: 10, fontWeight: 700,
            background: tab === t ? 'var(--bg-panel)' : 'transparent',
            color: tab === t ? 'var(--accent-blue)' : 'var(--text-muted)',
            borderBottom: tab === t ? '2px solid var(--accent-blue)' : '2px solid transparent',
            textTransform: 'uppercase', letterSpacing: '0.04em', transition: 'all .15s',
          }}>{TAB_LABEL[t]}</button>
        ))}
      </div>

      {/* Tab body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '14px 16px' }}>
        {tab === 'overview' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <dl style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: '5px 10px', fontSize: 12 }}>
              {rawData?.task_id && <><dt style={{ color: 'var(--text-muted)' }}>Task ID</dt><dd><Mono>{shortId(rawData.task_id)}</Mono></dd></>}
              {rawData?.agent_id && <><dt style={{ color: 'var(--text-muted)' }}>Agent ID</dt><dd><Mono>{shortId(rawData.agent_id)}</Mono></dd></>}
              {rawData?.name && <><dt style={{ color: 'var(--text-muted)' }}>Name</dt><dd style={{ color: 'var(--text-secondary)' }}>{rawData.name}</dd></>}
              {rawData?.role && <><dt style={{ color: 'var(--text-muted)' }}>Role</dt><dd style={{ color: 'var(--text-secondary)' }}>{rawData.role}</dd></>}
              {rawData?.scope && <><dt style={{ color: 'var(--text-muted)' }}>Scope</dt><dd style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{rawData.scope}</dd></>}
              {rawData?.status && <><dt style={{ color: 'var(--text-muted)' }}>Status</dt><dd><StatusPill status={rawData.status} /></dd></>}
              {rawData?.health && <><dt style={{ color: 'var(--text-muted)' }}>Health</dt><dd><StatusPill status={rawData.health} /></dd></>}
              {rawData?.created_at && <><dt style={{ color: 'var(--text-muted)' }}>Created</dt><dd style={{ color: 'var(--text-muted)' }}>{fmt(rawData.created_at)}</dd></>}
              {rawData?.started_at && <><dt style={{ color: 'var(--text-muted)' }}>Started</dt><dd style={{ color: 'var(--text-muted)' }}>{fmt(rawData.started_at)}</dd></>}
              {attempts.length > 0 && <><dt style={{ color: 'var(--text-muted)' }}>Attempts</dt><dd style={{ color: 'var(--text-secondary)' }}>{attempts.length}</dd></>}
            </dl>
            {rawData?.objective && (
              <div style={{ background: 'var(--bg-base)', borderRadius: 6, padding: '8px 10px', fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                <div style={{ fontWeight: 700, marginBottom: 4, color: 'var(--text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Objective</div>
                {rawData.objective}
              </div>
            )}
            {rawData?.description && (
              <div style={{ background: 'var(--bg-base)', borderRadius: 6, padding: '8px 10px', fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                {rawData.description.slice(0, 300)}
              </div>
            )}
            {rawData?.error && (
              <div style={{ background: '#f8717111', border: '1px solid #f8717133', borderRadius: 6, padding: '8px 10px', fontSize: 11, color: '#f87171' }}>
                ⚠ {rawData.error}
              </div>
            )}
            {/* Actions */}
            {nodeType === 'task' && (
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                <button onClick={() => setTab('instructions')} style={{ fontSize: 11, padding: '5px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-elevated)', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                  📝 Send Instruction
                </button>
              </div>
            )}
          </div>
        )}

        {tab === 'instructions' && rawData?.task_id && (
          <AnalystInstructionPanel
            taskId={rawData.task_id}
            attempts={attempts}
            onSubmit={() => { loadDetails(); onRefresh && onRefresh() }}
          />
        )}

        {tab === 'tools' && (
          loading
            ? <div style={{ display: 'flex', justifyContent: 'center', padding: 20 }}><Spinner /></div>
            : <ToolExecutionFeed tools={tools} />
        )}

        {tab === 'poc' && (
          finding
            ? <PoCLifecyclePanel finding={finding} onRefresh={() => { loadDetails(); onRefresh && onRefresh() }} />
            : <div style={{ color: 'var(--text-muted)', fontSize: 12, lineHeight: 1.6 }}>
                No finding linked to this task.<br />PoC lifecycle requires an associated finding with an active hypothesis.
              </div>
        )}
      </div>
    </div>
  )
}
