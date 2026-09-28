/**
 * CreateTaskModal.jsx — Streamlined Task Creation with Advanced Power User Controls
 * Sections 16 & 17:
 * - Simple 6-field default view:
 *   1. What do you want to do? (Text area)
 *   2. Target (Repository / Component / Files)
 *   3. Method ([Auto], Static, Simulation, Formal, Security, Custom)
 *   4. Tools ([Auto], Yosys, Verilator, Cocotb, Surfer, Sby, Z3)
 *   5. Agent ([Auto], AGY, Codex)
 *   6. Budget ([Auto], Standard, High)
 * - Collapsible "Advanced Power User Options" (Role, Model, Token budget, Time budget, Retries, Scope)
 * - Primary Action: [Run Task]
 * - Secondary: [Review Plan First]
 */

import { useState } from 'react'
import api from '../api'

export default function CreateTaskModal({ isOpen, onClose, onTaskCreated }) {
  // Primary simple inputs
  const [goal, setGoal] = useState('')
  const [target, setTarget] = useState('rtl/spi_host')
  const [method, setMethod] = useState('auto')
  const [selectedTools, setSelectedTools] = useState(['auto'])
  const [agent, setAgent] = useState('auto')
  const [budgetTier, setBudgetTier] = useState('auto')

  // Power user advanced inputs (collapsed by default)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [role, setRole] = useState('CDC / RDC / Clock / Reset')
  const [model, setModel] = useState('claude-3-5-sonnet-20241022')
  const [tokenBudget, setTokenBudget] = useState(60000)
  const [timeBudget, setTimeBudget] = useState(600)
  const [retryLimit, setRetryLimit] = useState(3)
  const [bucket, setBucket] = useState('RESET_AND_CLOCK')

  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  if (!isOpen) return null

  const handleToolToggle = (t) => {
    if (t === 'auto') {
      setSelectedTools(['auto'])
      return
    }
    const current = selectedTools.filter(x => x !== 'auto')
    if (current.includes(t)) {
      const next = current.filter(x => x !== t)
      setSelectedTools(next.length ? next : ['auto'])
    } else {
      setSelectedTools([...current, t])
    }
  }

  const handleSubmit = async (reviewPlanFirst = false) => {
    if (!goal.trim()) {
      setErrorMsg('Please specify what you want to verify.')
      return
    }

    try {
      setLoading(true)
      setErrorMsg('')

      const effectiveAgent = agent === 'auto' ? 'AGY' : agent
      const effectiveMethod = method === 'auto' ? 'structural' : method
      const effectiveTools = selectedTools.includes('auto') ? ['Yosys'] : selectedTools

      const payload = {
        objective: goal.trim(),
        target_component: target || 'core',
        risk_level: 'MEDIUM',
        assigned_agent_id: effectiveAgent,
        inputs: {
          goal: goal.trim(),
          scope: target || 'rtl/',
          method: effectiveMethod,
          tool: effectiveTools[0] || 'Yosys',
          tools: effectiveTools,
          agent: effectiveAgent,
          role: showAdvanced ? role : 'CDC / Clock / Reset Analysis',
          bucket: showAdvanced ? bucket : 'RESET_AND_CLOCK',
          token_budget: showAdvanced ? tokenBudget : 60000,
          time_budget: showAdvanced ? timeBudget : 600,
          retry_limit: showAdvanced ? retryLimit : 3,
        }
      }

      const res = await api.createTask(payload)
      if (onTaskCreated) onTaskCreated(res)
      onClose()
    } catch (err) {
      setErrorMsg(err.message || 'Failed to dispatch verification task')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ width: 560 }}>
        {/* Header */}
        <div className="modal-header">
          <span className="modal-title">Create Verification Task</span>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>

        {/* Body */}
        <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {errorMsg && (
            <div className="diag-box" style={{ padding: 10 }}>
              <div style={{ color: 'var(--red)', fontSize: 12 }}>{errorMsg}</div>
            </div>
          )}

          {/* 1. What do you want to do? */}
          <div className="form-group">
            <label className="form-label">What do you want to verify? *</label>
            <textarea
              className="form-control"
              placeholder="e.g. Check whether reset signals can cross into the secure domain unsafely."
              value={goal}
              onChange={e => setGoal(e.target.value)}
              style={{ minHeight: 70, fontSize: 13 }}
              autoFocus
            />
          </div>

          {/* 2. Target */}
          <div className="form-group">
            <label className="form-label">Target Component / Scope:</label>
            <input
              className="form-control"
              placeholder="e.g. rtl/spi_host or spi_host_core"
              value={target}
              onChange={e => setTarget(e.target.value)}
            />
          </div>

          {/* 3. Verification Method */}
          <div className="form-group">
            <label className="form-label">Verification Method:</label>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {[
                { id: 'auto', label: 'Auto (Recommended)' },
                { id: 'structural', label: 'Static Structural' },
                { id: 'simulation', label: 'Simulation / Lint' },
                { id: 'formal', label: 'Formal Proof' },
                { id: 'security', label: 'Security Domain' },
              ].map(m => (
                <button
                  key={m.id}
                  type="button"
                  className={`btn btn-sm ${method === m.id ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setMethod(m.id)}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {/* 4. Tools */}
          <div className="form-group">
            <label className="form-label">Deterministic Tools:</label>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {[
                { id: 'auto', label: 'Auto Select' },
                { id: 'Yosys', label: 'Yosys' },
                { id: 'Verilator', label: 'Verilator' },
                { id: 'Cocotb', label: 'Cocotb' },
                { id: 'Sby', label: 'SymbiYosys' },
                { id: 'Z3', label: 'Z3' },
              ].map(t => {
                const isSelected = selectedTools.includes(t.id)
                return (
                  <button
                    key={t.id}
                    type="button"
                    className={`btn btn-sm ${isSelected ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => handleToolToggle(t.id)}
                  >
                    {t.label}
                  </button>
                )
              })}
            </div>
          </div>

          {/* 5. Agent & Budget */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="form-group">
              <label className="form-label">Executor Agent:</label>
              <select className="form-control" value={agent} onChange={e => setAgent(e.target.value)}>
                <option value="auto">Auto (AGY Preferred)</option>
                <option value="AGY">AGY (Antigravity CLI)</option>
                <option value="Codex">Codex (OpenAI Model)</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Resource Budget:</label>
              <select className="form-control" value={budgetTier} onChange={e => setBudgetTier(e.target.value)}>
                <option value="auto">Auto (Standard 60k tokens)</option>
                <option value="light">Lightweight (25k tokens)</option>
                <option value="high">Deep Verification (150k tokens)</option>
              </select>
            </div>
          </div>

          {/* ── Section 17: Collapsible Advanced Power User Controls ─────────── */}
          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 10 }}>
            <div
              style={{
                fontSize: 11, fontWeight: 600, color: 'var(--blue)', cursor: 'pointer',
                userSelect: 'none', display: 'flex', alignItems: 'center', gap: 6
              }}
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              <span>{showAdvanced ? '▼' : '►'}</span>
              <span>Advanced Power User Options</span>
              <span style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 400 }}>
                (Role, Model, Token limit, Timeout, Retries)
              </span>
            </div>

            {showAdvanced && (
              <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10, background: 'var(--bg-subtle)', padding: 12, borderRadius: 'var(--radius)' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <div className="form-group">
                    <label className="form-label">Agent Role:</label>
                    <input className="form-control" value={role} onChange={e => setRole(e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Verification Bucket:</label>
                    <select className="form-control" value={bucket} onChange={e => setBucket(e.target.value)}>
                      <option value="RESET_AND_CLOCK">RESET_AND_CLOCK</option>
                      <option value="CLOCK_DOMAIN_CROSSING">CLOCK_DOMAIN_CROSSING</option>
                      <option value="DEBUG_AND_TRACE">DEBUG_AND_TRACE</option>
                      <option value="ACCESS_CONTROL">ACCESS_CONTROL</option>
                      <option value="SECURE_BOOT_AND_LIFECYCLE">SECURE_BOOT_AND_LIFECYCLE</option>
                    </select>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
                  <div className="form-group">
                    <label className="form-label">Token Cap:</label>
                    <input type="number" className="form-control" value={tokenBudget} onChange={e => setTokenBudget(parseInt(e.target.value, 10))} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Timeout (sec):</label>
                    <input type="number" className="form-control" value={timeBudget} onChange={e => setTimeBudget(parseInt(e.target.value, 10))} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Retry Limit:</label>
                    <input type="number" className="form-control" value={retryLimit} onChange={e => setRetryLimit(parseInt(e.target.value, 10))} />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <button className="btn btn-secondary btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => handleSubmit(true)}
            disabled={loading}
          >
            Review Plan First
          </button>
          <button
            id="btn-submit-task"
            className="btn btn-primary btn-sm"
            onClick={() => handleSubmit(false)}
            disabled={loading}
          >
            {loading ? 'Dispatching...' : 'Run Task'}
          </button>
        </div>
      </div>
    </div>
  )
}
