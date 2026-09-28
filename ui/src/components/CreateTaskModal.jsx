/**
 * CreateTaskModal.jsx — Clean Configuration UX with Grouped Advanced Controls
 * Section 3:
 * - BASIC section (Only essentials for normal analyst)
 * - ADVANCED section (Collapsed by default), grouped into:
 *   EXECUTION, AGENT, METHOD, TOOLS, BUDGET, CONTEXT, SAFETY
 * - Proper form spacing, labels, helper text, validation and defaults.
 * - Claude is disabled by policy; AGY and Codex are allowed executors.
 */

import { useState } from 'react'
import api from '../api'

export default function CreateTaskModal({ isOpen, onClose, onTaskCreated }) {
  // BASIC inputs
  const [goal, setGoal] = useState('')
  const [target, setTarget] = useState('rtl/spi_host')
  const [riskLevel, setRiskLevel] = useState('MEDIUM')

  // ADVANCED inputs (collapsed by default)
  const [showAdvanced, setShowAdvanced] = useState(false)

  // ADVANCED: EXECUTION
  const [executionPolicy, setExecutionPolicy] = useState('DETERMINISTIC_SANDBOX')
  const [retryLimit, setRetryLimit] = useState(3)
  const [timeBudget, setTimeBudget] = useState(600) // seconds

  // ADVANCED: AGENT
  const [agent, setAgent] = useState('AGY')
  const [role, setRole] = useState('VERIFICATION_ENGINEER')
  const [model, setModel] = useState('codex-davinci-002')

  // ADVANCED: METHOD
  const [method, setMethod] = useState('formal')

  // ADVANCED: TOOLS
  const [selectedTools, setSelectedTools] = useState(['Yosys', 'Boolector'])

  // ADVANCED: BUDGET
  const [tokenBudget, setTokenBudget] = useState(60000)

  // ADVANCED: CONTEXT
  const [contextScope, setContextScope] = useState('ONE_HOP_EXPANSION')
  const [includeVendor, setIncludeVendor] = useState(false)
  const [includeGenerated, setIncludeGenerated] = useState(false)

  // ADVANCED: SAFETY
  const [requireHumanReview, setRequireHumanReview] = useState(false)
  const [failSafeGate, setFailSafeGate] = useState(true)

  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  if (!isOpen) return null

  const handleToolToggle = (toolName) => {
    if (selectedTools.includes(toolName)) {
      if (selectedTools.length > 1) {
        setSelectedTools(selectedTools.filter(t => t !== toolName))
      }
    } else {
      setSelectedTools([...selectedTools, toolName])
    }
  }

  const handleSubmit = async () => {
    if (!goal.trim()) {
      setErrorMsg('Please specify what you want to verify.')
      return
    }

    try {
      setLoading(true)
      setErrorMsg('')

      const payload = {
        objective: goal.trim(),
        target_component: target || 'core',
        risk_level: riskLevel,
        assigned_agent_id: agent,
        inputs: {
          goal: goal.trim(),
          scope: target || 'rtl/',
          method: method,
          tool: selectedTools[0] || 'Yosys',
          tools: selectedTools,
          agent: agent,
          role: role,
          model: model,
          token_budget: Number(tokenBudget),
          time_budget: Number(timeBudget),
          retry_limit: Number(retryLimit),
          execution_policy: executionPolicy,
          context_scope: contextScope,
          include_vendor: includeVendor,
          include_generated: includeGenerated,
          require_human_review: requireHumanReview,
          fail_safe_gate: failSafeGate,
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
    <div className="modal-backdrop" onClick={onClose} style={{ zIndex: 1000, overflowY: 'auto', padding: '30px 0' }}>
      <div
        className="modal-content"
        onClick={e => e.stopPropagation()}
        style={{
          width: '740px',
          maxWidth: '92vw',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          margin: 'auto',
          background: 'var(--bg-surface)',
          borderRadius: 4,
          boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
          border: '1px solid var(--border)'
        }}
      >
        {/* Modal Header */}
        <div className="modal-header" style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-bright)' }}>
              Dispatch Verification Task
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
              Define verification objectives and configure runtime parameters
            </div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose} style={{ fontSize: 16 }}>✕</button>
        </div>

        {/* Modal Scrollable Body */}
        <div style={{ padding: '20px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 18 }}>
          {errorMsg && (
            <div style={{ padding: '8px 12px', background: 'var(--red-bg)', border: '1px solid var(--red-border)', color: 'var(--red)', fontSize: 12, borderRadius: 3 }}>
              ⚠ {errorMsg}
            </div>
          )}

          {/* ─── BASIC SECTION ─────────────────────────────────────────────── */}
          <div style={{ background: '#ffffff', border: '1px solid var(--border)', borderRadius: 4, padding: '16px' }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--blue)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>
              BASIC CONFIGURATION
            </div>

            {/* Verification Objective */}
            <div className="form-group" style={{ marginBottom: 14 }}>
              <label className="form-label" style={{ fontSize: 13 }}>
                Verification Objective / Goal *
              </label>
              <textarea
                className="form-control"
                placeholder="e.g. Verify clock domain crossing between sys_clk and aon_clk in reset_controller..."
                value={goal}
                onChange={e => setGoal(e.target.value)}
                style={{ minHeight: 64, fontSize: 13 }}
                autoFocus
              />
              <div className="form-hint" style={{ fontSize: 11 }}>
                Provide high-level property, vulnerability hypothesis, or verification check.
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 14 }}>
              {/* Target Component */}
              <div className="form-group">
                <label className="form-label" style={{ fontSize: 13 }}>
                  Target Subsystem / Files
                </label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="rtl/spi_host or hw/ip/..."
                  value={target}
                  onChange={e => setTarget(e.target.value)}
                  style={{ fontSize: 13 }}
                />
              </div>

              {/* Priority / Risk Level */}
              <div className="form-group">
                <label className="form-label" style={{ fontSize: 13 }}>
                  Risk / Priority Level
                </label>
                <select
                  className="form-control"
                  value={riskLevel}
                  onChange={e => setRiskLevel(e.target.value)}
                  style={{ fontSize: 13 }}
                >
                  <option value="LOW">LOW</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="HIGH">HIGH</option>
                  <option value="CRITICAL">CRITICAL (Gated)</option>
                </select>
              </div>
            </div>
          </div>

          {/* ─── ADVANCED TOGGLE ───────────────────────────────────────────── */}
          <div>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setShowAdvanced(!showAdvanced)}
              style={{
                width: '100%',
                display: 'flex',
                justifyContent: 'space-between',
                padding: '8px 14px',
                fontWeight: 600,
                fontSize: 12.5,
                color: 'var(--text-primary)'
              }}
            >
              <span>⚙ ADVANCED CONTROLS (Execution, Agent, Method, Tools, Budget, Context, Safety)</span>
              <span>{showAdvanced ? '▲ Collapse' : '▼ Expand (7 groups)'}</span>
            </button>
          </div>

          {/* ─── ADVANCED COLLAPSIBLE CONTAINER ─────────────────────────────── */}
          {showAdvanced && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

              {/* 1. EXECUTION */}
              <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 4, padding: '14px' }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 10, letterSpacing: '0.04em' }}>
                  1. EXECUTION
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 12 }}>
                  <div className="form-group">
                    <label className="form-label" style={{ fontSize: 11 }}>Execution Policy</label>
                    <select className="form-control" value={executionPolicy} onChange={e => setExecutionPolicy(e.target.value)} style={{ fontSize: 12 }}>
                      <option value="DETERMINISTIC_SANDBOX">DETERMINISTIC_SANDBOX (Isolated)</option>
                      <option value="HOST_EXECUTION">HOST_EXECUTION (Local CLI)</option>
                      <option value="DRY_RUN_PLAN_ONLY">DRY_RUN_PLAN_ONLY</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label" style={{ fontSize: 11 }}>Timeout (Sec)</label>
                    <input type="number" className="form-control" value={timeBudget} onChange={e => setTimeBudget(e.target.value)} style={{ fontSize: 12 }} />
                  </div>
                  <div className="form-group">
                    <label className="form-label" style={{ fontSize: 11 }}>Max Retries</label>
                    <input type="number" className="form-control" value={retryLimit} onChange={e => setRetryLimit(e.target.value)} style={{ fontSize: 12 }} />
                  </div>
                </div>
              </div>

              {/* 2. AGENT */}
              <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 4, padding: '14px' }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 10, letterSpacing: '0.04em' }}>
                  2. AGENT & ROLE
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
                  <div className="form-group">
                    <label className="form-label" style={{ fontSize: 11 }}>Assigned Agent</label>
                    <select className="form-control" value={agent} onChange={e => setAgent(e.target.value)} style={{ fontSize: 12 }}>
                      <option value="AGY">AGY (Autonomous EDA Agent)</option>
                      <option value="Codex">Codex (Deterministic Code Agent)</option>
                      <option value="Claude" disabled>Claude (Disabled by Policy)</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label" style={{ fontSize: 11 }}>Agent Role</label>
                    <select className="form-control" value={role} onChange={e => setRole(e.target.value)} style={{ fontSize: 12 }}>
                      <option value="VERIFICATION_ENGINEER">Verification Engineer</option>
                      <option value="FORMAL_SPECIALIST">Formal Specialist</option>
                      <option value="SECURITY_RESEARCHER">Security Researcher</option>
                      <option value="ORCHESTRATOR">Orchestrator</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label" style={{ fontSize: 11 }}>Model Engine</label>
                    <select className="form-control" value={model} onChange={e => setModel(e.target.value)} style={{ fontSize: 12 }}>
                      <option value="codex-davinci-002">Codex Davinci 002 (Real)</option>
                      <option value="gpt-4o">GPT-4o (Real)</option>
                      <option value="gemini-1.5-pro">Gemini 1.5 Pro (Real)</option>
                      <option value="deterministic-local">Deterministic Local</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* 3. METHOD & 4. TOOLS */}
              <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 4, padding: '14px' }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 10, letterSpacing: '0.04em' }}>
                  3. METHOD & 4. DETERMINISTIC TOOLS
                </div>
                <div style={{ marginBottom: 12 }}>
                  <label className="form-label" style={{ fontSize: 11 }}>Verification Method</label>
                  <select className="form-control" value={method} onChange={e => setMethod(e.target.value)} style={{ fontSize: 12 }}>
                    <option value="formal">Formal SMT Property Verification</option>
                    <option value="dynamic_simulation">Dynamic Simulation & Assertions</option>
                    <option value="static_ast">Static AST & Lint Analysis</option>
                    <option value="fuzzing">Coverage-Guided Fuzzing</option>
                    <option value="security_boundary">Security Boundary Lock Verification</option>
                  </select>
                </div>
                <div>
                  <label className="form-label" style={{ fontSize: 11, marginBottom: 6 }}>Allowed Deterministic Tool Plane</label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {['Verilator', 'Yosys', 'Slang', 'Boolector', 'Z3', 'Cocotb', 'Surfer', 'Sby'].map(t => {
                      const isSel = selectedTools.includes(t)
                      return (
                        <button
                          key={t}
                          type="button"
                          className={`btn ${isSel ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                          onClick={() => handleToolToggle(t)}
                          style={{ fontSize: 11, padding: '3px 8px' }}
                        >
                          {isSel ? '✓ ' : '+ '}{t}
                        </button>
                      )
                    })}
                  </div>
                </div>
              </div>

              {/* 5. BUDGET */}
              <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 4, padding: '14px' }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 10, letterSpacing: '0.04em' }}>
                  5. TOKEN BUDGET & ACCOUNTING
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 12, alignItems: 'center' }}>
                  <div className="form-group">
                    <label className="form-label" style={{ fontSize: 11 }}>Token Cap</label>
                    <input
                      type="number"
                      className="form-control"
                      value={tokenBudget}
                      onChange={e => setTokenBudget(e.target.value)}
                      style={{ fontSize: 12 }}
                    />
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                    Hard budget gate. When reached, task will pause and trigger a watchdog alert.
                  </div>
                </div>
              </div>

              {/* 6. CONTEXT SCOPE */}
              <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 4, padding: '14px' }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 10, letterSpacing: '0.04em' }}>
                  6. CONTEXT SCOPE & FABRIC
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 8 }}>
                  <div className="form-group">
                    <label className="form-label" style={{ fontSize: 11 }}>Scope Depth</label>
                    <select className="form-control" value={contextScope} onChange={e => setContextScope(e.target.value)} style={{ fontSize: 12 }}>
                      <option value="LOCAL_FILE_ONLY">Local File Only</option>
                      <option value="ONE_HOP_EXPANSION">1-Hop Dependency Expansion (Recommended)</option>
                      <option value="FULL_SUBSYSTEM">Full Subsystem Hierarchy</option>
                    </select>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, paddingTop: 18 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
                      <input type="checkbox" checked={includeVendor} onChange={e => setIncludeVendor(e.target.checked)} />
                      Include third-party vendor code
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
                      <input type="checkbox" checked={includeGenerated} onChange={e => setIncludeGenerated(e.target.checked)} />
                      Include auto-generated register headers
                    </label>
                  </div>
                </div>
              </div>

              {/* 7. SAFETY & HUMAN-IN-THE-LOOP */}
              <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 4, padding: '14px' }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 10, letterSpacing: '0.04em' }}>
                  7. SAFETY & GATES
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, cursor: 'pointer' }}>
                    <input type="checkbox" checked={requireHumanReview} onChange={e => setRequireHumanReview(e.target.checked)} />
                    Require Lead Analyst sign-off before committing result to verification closure
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, cursor: 'pointer' }}>
                    <input type="checkbox" checked={failSafeGate} onChange={e => setFailSafeGate(e.target.checked)} />
                    Enforce fail-safe halt if AST compilation errors occur
                  </label>
                </div>
              </div>

            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="modal-footer" style={{ padding: '14px 20px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button className="btn btn-secondary btn-md" onClick={onClose} disabled={loading}>
            Cancel
          </button>
          <button
            id="btn-dispatch-task"
            className="btn btn-primary btn-md"
            onClick={handleSubmit}
            disabled={loading}
            style={{ fontWeight: 600, minWidth: 130 }}
          >
            {loading ? 'Dispatching...' : 'Dispatch Task'}
          </button>
        </div>
      </div>
    </div>
  )
}
