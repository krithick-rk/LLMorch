/**
 * CreateTaskModal.jsx — Viewport-Fixed Context-Aware Task Creation Modal
 * Sections 23, 24, 25, 51, 55:
 * - Viewport-fixed positioning (position: fixed; top: 0; left: 0; width: 100vw; height: 100vh)
 * - Modal has its own scroll area; background page does NOT push, resize, or scroll
 * - Context-aware prefilling from initialContext:
 *   Task page -> parent task context
 *   Finding page -> finding context
 *   Gap -> gap objective
 *   Repository / Project -> project scope
 *   Agent -> prefill agent
 *   Tool -> prefill tool
 *   File -> prefill file
 * - Normal UX view:
 *   What do you want to do? [large input]
 *   Scope: [Current Project]
 *   Target: [Auto]
 *   Analysis Mode: [Quick / Standard / Deep]
 *   Method: [Auto]
 *   Agent: [Auto]
 *   Tools: [Auto]
 *   Budget: [Auto]
 *   [Create Task]
 * - Advanced controls remain collapsible
 */

import { useState, useEffect } from 'react'
import api from '../api'

export default function CreateTaskModal({ isOpen, onClose, onTaskCreated, initialContext = null, activeProject = null }) {
  // Normal / Basic Inputs
  const [goal, setGoal] = useState('')
  const [scope, setScope] = useState('Current Project')
  const [target, setTarget] = useState('runtime/src/drivers.rs')
  const [analysisMode, setAnalysisMode] = useState('Standard') // Quick | Standard | Deep
  const [method, setMethod] = useState('Auto')
  const [agent, setAgent] = useState('Auto')
  const [tools, setTools] = useState('Auto')
  const [budget, setBudget] = useState('Auto')
  const [riskLevel, setRiskLevel] = useState('MEDIUM')

  // Advanced collapsible section
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState('agent-agy-01')
  const [selectedTools, setSelectedTools] = useState(['rust_source_inspector', 'cargo_audit'])
  const [timeBudget, setTimeBudget] = useState(600)
  const [tokenBudget, setTokenBudget] = useState(60000)
  const [retryLimit, setRetryLimit] = useState(3)
  const [requireHumanReview, setRequireHumanReview] = useState(false)

  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  // Context-aware auto-population (Section 24)
  useEffect(() => {
    if (!isOpen) return

    const projectName = activeProject?.name || activeProject?.target_directory || 'Current Project'
    setScope(projectName)

    if (initialContext) {
      if (initialContext.goal || initialContext.objective) {
        setGoal(initialContext.goal || initialContext.objective)
      } else if (initialContext.gap_title) {
        setGoal(`Verify and close gap: ${initialContext.gap_title}`)
      } else if (initialContext.finding_title) {
        setGoal(`Investigate and verify finding: ${initialContext.finding_title}`)
      }

      if (initialContext.target || initialContext.file || initialContext.target_component) {
        setTarget(initialContext.target || initialContext.file || initialContext.target_component)
      }

      if (initialContext.agent) {
        setAgent(initialContext.agent)
        setSelectedAgent(initialContext.agent)
      }

      if (initialContext.tool) {
        setTools(initialContext.tool)
        setSelectedTools([initialContext.tool])
      }

      if (initialContext.method) {
        setMethod(initialContext.method)
      }
    } else {
      if (!goal) {
        setGoal('')
      }
      setTarget(activeProject?.metadata?.intake?.sample_files?.[0] || 'runtime/src/drivers.rs')
    }
  }, [isOpen, initialContext, activeProject])

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

      const effectiveAgent = agent === 'Auto' ? selectedAgent : agent
      const effectiveMethod = method === 'Auto' ? 'Firmware Security Analysis' : method
      const effectiveTools = tools === 'Auto' ? selectedTools : [tools]

      const payload = {
        objective: goal.trim(),
        target_component: target || 'runtime/',
        risk_level: riskLevel,
        assigned_agent_id: effectiveAgent,
        inputs: {
          goal: goal.trim(),
          scope: target || 'runtime/',
          method: effectiveMethod,
          tool: effectiveTools[0] || 'rust_source_inspector',
          tools: effectiveTools,
          agent: effectiveAgent,
          analysis_mode: analysisMode,
          token_budget: budget === 'Auto' ? 60000 : Number(tokenBudget),
          time_budget: Number(timeBudget),
          retry_limit: Number(retryLimit),
          require_human_review: requireHumanReview,
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
    <div
      id="create-task-modal-backdrop"
      className="modal-backdrop modal-overlay"
      onClick={onClose}
      style={{
        position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
        zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'rgba(0, 0, 0, 0.65)', backdropFilter: 'blur(3px)'
      }}
    >
      <div
        className="modal-content"
        onClick={e => e.stopPropagation()}
        style={{
          width: '680px', maxWidth: '92vw', maxHeight: '85vh',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
          background: 'var(--bg-base)', border: '1px solid var(--border-focus)',
          borderRadius: 6, boxShadow: '0 12px 48px rgba(0, 0, 0, 0.5)'
        }}
      >
        {/* Fixed Modal Header (Section 23) */}
        <div className="modal-header" style={{
          padding: '14px 20px', borderBottom: '1px solid var(--border)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          background: 'var(--bg-surface)'
        }}>
          <div>
            <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-bright)' }}>
              Create Verification Task
            </span>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              Scope-bound verifiable task dispatched to Central Orchestrator
            </div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose} style={{ fontSize: 16 }}>✕</button>
        </div>

        {/* Internally Scrollable Modal Body (Section 23 & 25) */}
        <div className="modal-body" style={{
          flex: 1, overflowY: 'auto', padding: '18px 20px',
          display: 'flex', flexDirection: 'column', gap: 14
        }}>
          {errorMsg && (
            <div style={{
              background: '#fef2f2', border: '1px solid #f87171', color: '#991b1b',
              padding: '8px 12px', borderRadius: 4, fontSize: 12
            }}>
              {errorMsg}
            </div>
          )}

          {/* Question: What do you want to do? (Section 25) */}
          <div className="form-group">
            <label className="form-label" style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)' }}>
              What do you want to do? <span style={{ color: 'var(--blue)' }}>*</span>
            </label>
            <textarea
              id="input-task-goal"
              className="form-control"
              rows={3}
              placeholder="e.g. Audit DPE command deserialization logic in runtime/src/invoke_dpe.rs and verify authorization gate prevents unauthenticated execution"
              value={goal}
              onChange={e => setGoal(e.target.value)}
              style={{ fontSize: 13, resize: 'vertical' }}
            />
          </div>

          {/* Normal View Configuration Grid (Section 25) */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="form-group">
              <label className="form-label" style={{ fontSize: 11, fontWeight: 600 }}>Scope</label>
              <input
                type="text"
                className="form-control"
                value={scope}
                disabled
                style={{ fontSize: 12, background: 'var(--bg-subtle)' }}
              />
            </div>

            <div className="form-group">
              <label className="form-label" style={{ fontSize: 11, fontWeight: 600 }}>Target File / Component</label>
              <input
                id="input-task-target"
                type="text"
                className="form-control"
                value={target}
                onChange={e => setTarget(e.target.value)}
                placeholder="runtime/src/drivers.rs"
                style={{ fontSize: 12 }}
              />
            </div>

            <div className="form-group">
              <label className="form-label" style={{ fontSize: 11, fontWeight: 600 }}>Analysis Mode</label>
              <select
                className="form-control"
                value={analysisMode}
                onChange={e => setAnalysisMode(e.target.value)}
                style={{ fontSize: 12 }}
              >
                <option value="Quick">Quick (Deterministic Pre-check & Static Inspection)</option>
                <option value="Standard">Standard (Full AST, Capability Audit & Evidence Dossier)</option>
                <option value="Deep">Deep (Exhaustive Formal Solver & Protocol Invariant)</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label" style={{ fontSize: 11, fontWeight: 600 }}>Method</label>
              <select
                className="form-control"
                value={method}
                onChange={e => setMethod(e.target.value)}
                style={{ fontSize: 12 }}
              >
                <option value="Auto">Auto (Orchestrator Selected)</option>
                <option value="Firmware Security Analysis">Firmware Security Analysis</option>
                <option value="Formal Register Verification">Formal Register Verification</option>
                <option value="Clock Domain Crossing Check">Clock Domain Crossing Check</option>
                <option value="Memory Safety Audit">Memory Safety Audit</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label" style={{ fontSize: 11, fontWeight: 600 }}>Agent</label>
              <select
                className="form-control"
                value={agent}
                onChange={e => setAgent(e.target.value)}
                style={{ fontSize: 12 }}
              >
                <option value="Auto">Auto (AGY / Codex by Capability)</option>
                <option value="agent-agy-01">Antigravity (AGY)</option>
                <option value="agent-codex-01">Codex</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label" style={{ fontSize: 11, fontWeight: 600 }}>Tools</label>
              <select
                className="form-control"
                value={tools}
                onChange={e => setTools(e.target.value)}
                style={{ fontSize: 12 }}
              >
                <option value="Auto">Auto (Language & Scope Aware)</option>
                <option value="rust_source_inspector">rust_source_inspector</option>
                <option value="cargo_audit">cargo_audit</option>
                <option value="yosys">Yosys Formal / Synthesis</option>
                <option value="verilator">Verilator Simulation</option>
              </select>
            </div>
          </div>

          {/* Advanced Controls Toggle */}
          <div style={{ marginTop: 4 }}>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setShowAdvanced(!showAdvanced)}
              style={{ fontSize: 11, color: 'var(--blue)', padding: '2px 0' }}
            >
              {showAdvanced ? '▼ Hide Advanced Configuration' : '▶ Show Advanced Configuration (Budgets, Tools, Review Gate)'}
            </button>
          </div>

          {/* Advanced Collapsible Pane */}
          {showAdvanced && (
            <div style={{
              background: 'var(--bg-subtle)', border: '1px solid var(--border)',
              borderRadius: 4, padding: 14, display: 'flex', flexDirection: 'column', gap: 12
            }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)' }}>
                Advanced Execution & Safety Bounds
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, fontSize: 11 }}>
                <div>
                  <label className="form-label">Time Budget (sec)</label>
                  <input
                    type="number"
                    className="form-control"
                    value={timeBudget}
                    onChange={e => setTimeBudget(Number(e.target.value))}
                    style={{ fontSize: 12 }}
                  />
                </div>
                <div>
                  <label className="form-label">Token Cap</label>
                  <input
                    type="number"
                    className="form-control"
                    value={tokenBudget}
                    onChange={e => setTokenBudget(Number(e.target.value))}
                    style={{ fontSize: 12 }}
                  />
                </div>
                <div>
                  <label className="form-label">Max Retries</label>
                  <input
                    type="number"
                    className="form-control"
                    value={retryLimit}
                    onChange={e => setRetryLimit(Number(e.target.value))}
                    style={{ fontSize: 12 }}
                  />
                </div>
              </div>

              <div>
                <label className="form-label" style={{ fontSize: 11, marginBottom: 4 }}>
                  Allowed Deterministic Tools
                </label>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {['rust_source_inspector', 'cargo_audit', 'yosys', 'verilator', 'sby'].map(t => (
                    <button
                      key={t}
                      type="button"
                      className={`btn btn-sm ${selectedTools.includes(t) ? 'btn-primary' : 'btn-secondary'}`}
                      style={{ fontSize: 11, padding: '2px 8px' }}
                      onClick={() => handleToolToggle(t)}
                    >
                      {selectedTools.includes(t) ? `✓ ${t}` : t}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11 }}>
                <input
                  type="checkbox"
                  id="chk-human-review"
                  checked={requireHumanReview}
                  onChange={e => setRequireHumanReview(e.target.checked)}
                />
                <label htmlFor="chk-human-review" style={{ cursor: 'pointer' }}>
                  Require Lead Analyst sign-off before committing result to verification closure
                </label>
              </div>
            </div>
          )}
        </div>

        {/* Fixed Modal Footer (Section 23) */}
        <div className="modal-footer" style={{
          padding: '12px 20px', borderTop: '1px solid var(--border)',
          display: 'flex', justifyContent: 'flex-end', gap: 10,
          background: 'var(--bg-surface)'
        }}>
          <button className="btn btn-secondary btn-sm" onClick={onClose} disabled={loading}>
            Cancel
          </button>
          <button
            id="btn-submit-task"
            className="btn btn-primary btn-sm"
            onClick={handleSubmit}
            disabled={loading || !goal.trim()}
            style={{ fontWeight: 700 }}
          >
            {loading ? 'Creating Task...' : '✓ Create Task'}
          </button>
        </div>
      </div>
    </div>
  )
}
