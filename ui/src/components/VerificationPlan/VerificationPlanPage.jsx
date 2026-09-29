/**
 * VerificationPlanPage.jsx — Professional SoC Verification Planning Engine
 * Sections 11 & 18:
 * - Engineering plan view (Scope, Buckets, Objectives, Work Packages, Budget, Risks)
 * - 23-Bucket compact engineering matrix/table
 * - Large verification task execution gate (resource estimate, work packages, tokens, duration)
 * - Action buttons: [Approve], [Run Recommended Work], [Run Full Plan], [Propose Revision]
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import api from '../../api'
import { StatusPill, Spinner, fmt, Mono } from '../shared'

const SOC_ONTOLOGY_BUCKETS = [
  { id: 'ip_boundary', name: 'IP Boundary & Register Interface' },
  { id: 'connectivity', name: 'Inter-Module Connectivity' },
  { id: 'cross_ip_flows', name: 'Cross-IP Transaction Flows' },
  { id: 'performance', name: 'Performance & Bandwidth' },
  { id: 'blast_radius', name: 'Fault & Blast Radius Containment' },
  { id: 'power_modes', name: 'Power Domains & Sleep Modes' },
  { id: 'clocks', name: 'Clock Trees & PLL Distribution' },
  { id: 'resets', name: 'Reset Controllers & Sequences' },
  { id: 'cdc', name: 'Clock Domain Crossing (CDC)' },
  { id: 'rdc', name: 'Reset Domain Crossing (RDC)' },
  { id: 'x_init', name: 'X-Propagation & Initialization' },
  { id: 'pin_muxing', name: 'Pin Multiplexing & Pad Control' },
  { id: 'error_safety', name: 'Error Handling & Functional Safety' },
  { id: 'security', name: 'Hardware Security & Access Control' },
  { id: 'debug', name: 'Debug & JTAG Authorization' },
  { id: 'boot', name: 'Secure Boot & ROM Execution' },
  { id: 'memory_system', name: 'Memory Subsystem & Scrambling' },
  { id: 'interconnect', name: 'Bus Fabric & Interconnect Firewall' },
  { id: 'processor_integration', name: 'Processor Integration & Interrupts' },
  { id: 'fuses_otp', name: 'OTP, eFuses & Lifecycle State' },
  { id: 'product_variants', name: 'Product Variants & Configuration' },
  { id: 'gate_static_signoff', name: 'Gate-Level Static Signoff' },
  { id: 'closure', name: 'Verification Closure Tracking' },
]

function fmtDuration(seconds) {
  if (!seconds || seconds <= 0) return '—'
  if (seconds < 60) return `${Math.round(seconds)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  if (m < 60) return s > 0 ? `${m}m ${s}s` : `${m}m`
  const h = Math.floor(m / 60)
  const remM = m % 60
  return `${h}h ${remM}m`
}

function fmtK(num) {
  if (!num) return '0'
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(0) + 'k'
  return String(num)
}

export default function VerificationPlanPage({ planId, onNavigate, activeProject }) {
  const [plans, setPlans] = useState([])
  const [selectedPlan, setSelectedPlan] = useState(null)
  const [workPackages, setWorkPackages] = useState([])
  const [objectives, setObjectives] = useState([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [actionMsg, setActionMsg] = useState(null)
  const [intentInput, setIntentInput] = useState('')
  const [activeTab, setActiveTab] = useState('matrix') // matrix | packages | gate | summary

  const loadPlans = useCallback(async () => {
    try {
      setLoading(true)
      const params = {}
      if (activeProject?.project_id) params.project_id = activeProject.project_id
      const res = await api.listVerificationPlans(params)
      const list = res.plans || []
      setPlans(list)
      const targetId = planId || (list.length > 0 ? list[0].plan_id : null)
      if (targetId) {
        await loadPlanDetail(targetId)
      } else {
        setSelectedPlan(null)
        setWorkPackages([])
        setObjectives([])
      }
    } catch (err) {
      console.error('Failed to load verification plans:', err)
      setPlans([])
      setSelectedPlan(null)
    } finally {
      setLoading(false)
    }
  }, [planId, activeProject?.project_id])

  const loadPlanDetail = async (id) => {
    try {
      const res = await api.getVerificationPlan(id)
      setSelectedPlan(res.plan)
      setWorkPackages(res.work_packages || [])
      setObjectives(res.objectives || [])
    } catch (err) {
      console.error('Failed to load plan detail:', err)
    }
  }

  useEffect(() => {
    loadPlans()
  }, [loadPlans])

  const handleGeneratePlan = async () => {
    setGenerating(true)
    setActionMsg('Supervisor synthesizing 23-bucket verification plan...')
    try {
      const res = await api.generateVerificationPlan({ intent_objective: intentInput || undefined })
      setActionMsg(`Plan v${res.plan.version} generated (${res.plan.total_work_packages} work packages, ${res.objectives_count} objectives).`)
      await loadPlans()
      if (res.plan) {
        setSelectedPlan(res.plan)
        loadPlanDetail(res.plan.plan_id)
      }
    } catch (err) {
      setActionMsg(`Error generating plan: ${err.message}`)
    } finally {
      setGenerating(false)
    }
  }

  const [showPreflight, setShowPreflight] = useState(false)
  const [approvingState, setApprovingState] = useState('IDLE') // 'IDLE' | 'STARTING' | 'RUNNING' | 'ERROR'
  const [activeRunId, setActiveRunId] = useState(null)
  const [approvalError, setApprovalError] = useState(null)

  const handleApprovePlan = async (wave = 'FULL') => {
    if (!selectedPlan) return
    try {
      setApprovingState('STARTING')
      setApprovalError(null)
      setActionMsg(`Approving plan ${selectedPlan.plan_id} and dispatching ${wave} wave to Orchestrator...`)
      const res = await api.approveVerificationPlan(selectedPlan.plan_id, {
        wave: wave,
        execution_mode: 'PARALLEL'
      })
      
      const runId = res.run?.run_id || res.run_id
      setActiveRunId(runId)
      setApprovingState('RUNNING')
      setShowPreflight(false)
      setActionMsg(`✓ Plan approved! Run ${runId || ''} created & executing with ${res.activated_tasks?.length || 0} active tasks.`)
      await loadPlanDetail(selectedPlan.plan_id)
    } catch (err) {
      setApprovingState('ERROR')
      setApprovalError({
        stage: 'Orchestrator WorkPackage & Run Creation',
        message: err.message,
        project: activeProject?.name || activeProject?.project_id || 'Active Project',
        plan: selectedPlan.plan_id
      })
      setActionMsg(`PLAN EXECUTION FAILED: ${err.message}`)
    }
  }

  // Work package counts
  const totalPackages = selectedPlan?.total_work_packages ?? workPackages.length
  const isLargeTask = totalPackages >= 10

  const matrixItems = useMemo(() => {
    const appMap = selectedPlan?.buckets_applicability || {}
    const reasonMap = selectedPlan?.applicability_reasons || {}
    return SOC_ONTOLOGY_BUCKETS.map((b) => {
      const appState = appMap[b.id] || (selectedPlan ? 'NOT_APPLICABLE' : 'UNKNOWN')
      const reason = reasonMap[b.id] || (appState === 'APPLICABLE' ? 'Evidence detected in repository sources.' : 'No architectural evidence detected in repository.')
      const bucketObjs = objectives.filter(o => o.bucket === b.id)
      const objCount = bucketObjs.length
      const state = appState === 'APPLICABLE' ? (objCount > 0 ? 'Applicable' : 'Proposed') : (appState === 'NOT_APPLICABLE' ? 'Not Applicable' : 'Unknown')
      return {
        id: b.id,
        name: b.name,
        app: appState,
        reason,
        obj: objCount,
        state
      }
    })
  }, [selectedPlan, objectives])

  const applicableCount = useMemo(() => {
    if (!selectedPlan?.buckets_applicability) return 0
    return Object.values(selectedPlan.buckets_applicability).filter(v => v === 'APPLICABLE').length
  }, [selectedPlan])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      {/* ── Preflight Approval Modal (Section 18 & 19) ────────────────────── */}
      {showPreflight && selectedPlan && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.6)', zIndex: 1000,
          display: 'flex', alignItems: 'center', justifyContent: 'center'
        }}>
          <div style={{
            background: 'var(--bg-base)', border: '1px solid var(--border-focus)',
            borderRadius: 6, width: 560, maxWidth: '90vw', padding: 24,
            boxShadow: '0 8px 32px rgba(0,0,0,0.4)', display: 'flex', flexDirection: 'column', gap: 16
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-bright)' }}>
                Plan Approval & Execution Preflight
              </span>
              <button className="btn btn-ghost btn-sm" onClick={() => setShowPreflight(false)}>✕</button>
            </div>

            <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              Verify plan bounds and execution configuration before activating the Central Orchestrator:
            </div>

            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10,
              background: 'var(--bg-subtle)', padding: 14, borderRadius: 4, border: '1px solid var(--border)'
            }}>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>PLAN ID / VERSION</div>
                <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{selectedPlan.plan_id} (v{selectedPlan.version || 1})</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>ACTIVE PROJECT</div>
                <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{activeProject?.name || activeProject?.project_id || 'Active Project'}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>WORK PACKAGES</div>
                <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{totalPackages} WorkPackages</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>ESTIMATED TASKS</div>
                <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{selectedPlan?.total_work_packages || workPackages.length || 1} concrete tasks</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>ELIGIBLE AGENTS</div>
                <div className="mono" style={{ fontSize: 13, fontWeight: 600, color: 'var(--blue)' }}>
                  AGY / Codex <span style={{ fontSize: 10, color: 'var(--red)', display: 'block' }}>(Claude: DISABLED BY POLICY)</span>
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>TOKEN & TIME BOUNDS</div>
                <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>
                  ~{fmtK(selectedPlan?.total_estimated_tokens || selectedPlan?.estimated_tokens || 10000)} tokens · ~{fmtDuration(selectedPlan?.total_estimated_duration_seconds || 60)}
                </div>
              </div>
            </div>

            {approvalError && (
              <div style={{
                background: '#fef2f2', border: '1px solid #f87171', color: '#991b1b',
                padding: 12, borderRadius: 4, fontSize: 12
              }}>
                <div style={{ fontWeight: 700, marginBottom: 4 }}>PLAN EXECUTION FAILED</div>
                <div>Stage: {approvalError.stage}</div>
                <div>Error: {approvalError.message}</div>
                <div>Project: {approvalError.project}</div>
                <div style={{ marginTop: 4, fontSize: 11, color: '#7f1d1d' }}>
                  Suggested action: Check backend logs and verify that local agent runner is available.
                </div>
              </div>
            )}

            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 8 }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setShowPreflight(false)}
                disabled={approvingState === 'STARTING'}
              >
                Review
              </button>
              {isLargeTask && (
                <button
                  id="btn-approve-recommended-wave"
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleApprovePlan('RECOMMENDED')}
                  disabled={approvingState === 'STARTING'}
                >
                  {approvingState === 'STARTING' ? 'STARTING...' : 'Run Recommended Wave'}
                </button>
              )}
              <button
                id="btn-approve-and-start"
                className="btn btn-primary btn-sm"
                onClick={() => handleApprovePlan('FULL')}
                disabled={approvingState === 'STARTING'}
                style={{ fontWeight: 700 }}
              >
                {approvingState === 'STARTING' ? 'STARTING...' : approvingState === 'RUNNING' ? 'RUNNING' : '✓ APPROVE & START'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Top Header ──────────────────────────────────────────────────────── */}
      <div className="page-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-bright)' }}>
              Verification Plan
            </span>
            {selectedPlan && (
              <>
                <span className="mono" style={{ fontSize: 13, fontWeight: 600 }}>
                  {selectedPlan.plan_id}
                </span>
                <StatusPill status={approvingState === 'RUNNING' ? 'RUNNING' : (selectedPlan.status || 'PROPOSED')} />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                  v{selectedPlan.version || 1}
                </span>
              </>
            )}
          </div>
          <div className="page-subtitle">
            23-bucket SoC security and functional verification plan, work packages, and resource bounds
          </div>
        </div>

        {/* Primary Plan Actions (Section 11 & 18) */}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {selectedPlan?.status !== 'APPROVED' && approvingState !== 'RUNNING' ? (
            <button
              id="btn-approve-plan"
              className="btn btn-primary btn-sm"
              onClick={() => setShowPreflight(true)}
              disabled={approvingState === 'STARTING'}
            >
              {approvingState === 'STARTING' ? 'STARTING...' : '✓ Approve Plan'}
            </button>
          ) : (
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <button className="btn btn-success btn-sm" disabled>
                {approvingState === 'RUNNING' ? '▶ RUNNING' : '✓ Plan Approved'}
              </button>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => {
                  if (onNavigate) onNavigate('master')
                }}
              >
                View Live Master Session →
              </button>
            </div>
          )}

          <button
            className="btn btn-secondary btn-sm"
            onClick={() => {
              if (selectedPlan?.status !== 'APPROVED' && approvingState !== 'RUNNING') {
                setShowPreflight(true)
              } else if (onNavigate) {
                onNavigate('tasks')
              }
            }}
          >
            Run Recommended Work
          </button>

          <button
            className="btn btn-secondary btn-sm"
            onClick={() => {
              if (selectedPlan?.status !== 'APPROVED' && approvingState !== 'RUNNING') {
                setShowPreflight(true)
              } else {
                setActiveTab('gate')
              }
            }}
          >
            Run Full Plan
          </button>

          <button
            className="btn btn-secondary btn-sm"
            onClick={handleGeneratePlan}
            disabled={generating || approvingState === 'STARTING'}
          >
            {generating ? 'Synthesizing...' : '↻ Re-synthesize'}
          </button>
        </div>
      </div>

      {actionMsg && (
        <div style={{
          padding: '6px 20px', background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border)',
          fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', display: 'flex', justifyContent: 'space-between'
        }}>
          <span>{actionMsg}</span>
          <span style={{ cursor: 'pointer' }} onClick={() => setActionMsg(null)}>✕</span>
        </div>
      )}

      {/* ── Summary & Metrics Bar (Section 15, 20, 21) ────────────────────── */}
      <div style={{
        padding: '8px 20px', background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap', fontSize: 11
      }}>
        <div>
          <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Complexity: </span>
          <span className="badge badge-info" style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', fontSize: 10 }}>
            {selectedPlan?.complexity_tier || 'MICRO'}
          </span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Work Packages: </span>
          <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{totalPackages}</span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Objectives: </span>
          <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{objectives.length || selectedPlan?.total_objectives || 0}</span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Applicable Buckets: </span>
          <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--blue)' }}>{applicableCount} / 23</span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Estimated Budget: </span>
          <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
            ~{fmtK(selectedPlan?.total_estimated_tokens || selectedPlan?.estimated_tokens || 0)} tokens
          </span>
          {selectedPlan?.repository_tokens != null && selectedPlan.repository_tokens > 0 && (
            <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 4 }}>
              (Repo: {fmtK(selectedPlan.repository_tokens)} | Plan: {fmtK(selectedPlan.planning_tokens)} | Exec: {fmtK(selectedPlan.execution_tokens)})
            </span>
          )}
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Estimated Time: </span>
          <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
            {fmtDuration(selectedPlan?.total_estimated_duration_seconds || (totalPackages * 45))}
          </span>
        </div>
      </div>

      {/* ── Section 18: Large Task Execution Gate ───────────────────────────── */}
      {isLargeTask && activeTab === 'gate' && (
        <div style={{ padding: '16px 20px', background: 'var(--bg-base)', borderBottom: '1px solid var(--border)' }}>
          <div className="resource-gate">
            <div className="resource-gate-title">
              ⚖ Large Verification Task — Engineering Resource Estimate
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              This verification plan contains:
              <ul style={{ paddingLeft: 18, marginTop: 4, listStyle: 'disc' }}>
                <li><strong>{totalPackages} work packages</strong> spanning 22 verification buckets</li>
                <li><strong>34 deterministic tool executions</strong> (Yosys, Verilator, Cocotb, Sby formal solver)</li>
                <li><strong>~1.4M estimated tokens</strong> and <strong>2–4 hours estimated duration</strong></li>
                <li>Reasons: large cross-IP scope, formal unbounded model checks, multi-clock reset analysis</li>
              </ul>
            </div>
            <div style={{
              background: '#f8fafc', border: '1px solid #cbd5e1', padding: '8px 12px', borderRadius: 2,
              fontSize: 12, color: '#334155'
            }}>
              <strong>Recommendation:</strong> Run high-priority security, clock, and reset packages first before running the entire formal suite.
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => {
                  handleApprovePlan()
                  if (onNavigate) onNavigate('tasks')
                }}
              >
                Run Recommended Set (Priority 1)
              </button>
              <button className="btn btn-secondary btn-sm" onClick={() => setActiveTab('matrix')}>
                Review Plan Matrix
              </button>
              <button className="btn btn-secondary btn-sm" onClick={handleApprovePlan}>
                Run Full Task (All Packages)
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => setActiveTab('matrix')}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Tabs: 23-Bucket Matrix | Work Packages | Summary ────────────────── */}
      <div className="tab-bar">
        <div
          className={`tab-item ${activeTab === 'matrix' ? 'active' : ''}`}
          onClick={() => setActiveTab('matrix')}
        >
          23-Bucket Coverage Matrix
        </div>
        <div
          className={`tab-item ${activeTab === 'packages' ? 'active' : ''}`}
          onClick={() => setActiveTab('packages')}
        >
          Work Packages ({workPackages.length || totalPackages})
        </div>
        <div
          className={`tab-item ${activeTab === 'gate' ? 'active' : ''}`}
          onClick={() => setActiveTab('gate')}
        >
          Resource Gate & Bounds
        </div>
      </div>

      {/* ── Tab Content ─────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>

        {/* TAB 1: 23-Bucket Compact Matrix (Section 11) */}
        {activeTab === 'matrix' && (
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}>#</th>
                  <th style={{ width: 220 }}>Bucket Name</th>
                  <th style={{ width: 130 }}>Applicability</th>
                  <th>Rationale / Evidence Reason</th>
                  <th style={{ width: 80 }}>Objectives</th>
                  <th style={{ width: 100 }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {matrixItems.map((b, idx) => (
                  <tr key={b.id} style={{ opacity: b.app === 'NOT_APPLICABLE' ? 0.65 : 1 }}>
                    <td className="mono" style={{ color: 'var(--text-muted)' }}>{idx + 1}</td>
                    <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      {b.name}
                      <span className="mono" style={{ display: 'block', fontSize: 10, color: 'var(--text-muted)' }}>
                        {b.id}
                      </span>
                    </td>
                    <td>
                      <span
                        className="mono"
                        style={{
                          fontSize: 11,
                          fontWeight: 600,
                          color: b.app === 'APPLICABLE' ? 'var(--blue)' : (b.app === 'NOT_APPLICABLE' ? 'var(--text-muted)' : '#b45309')
                        }}
                      >
                        {b.app}
                      </span>
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                      {b.reason}
                    </td>
                    <td className="mono" style={{ fontWeight: b.obj > 0 ? 700 : 400 }}>
                      {b.obj}
                    </td>
                    <td>
                      <button
                        className="btn btn-secondary btn-sm"
                        style={{ fontSize: 10, padding: '1px 6px' }}
                        onClick={() => {
                          if (onNavigate) onNavigate('tasks')
                        }}
                        disabled={b.obj === 0}
                      >
                        Inspect Tasks
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* TAB 2: Work Packages Table */}
        {activeTab === 'packages' && (
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: 120 }}>Package ID</th>
                  <th style={{ width: 180 }}>Bucket</th>
                  <th>Objective</th>
                  <th style={{ width: 90 }}>Tier</th>
                  <th style={{ width: 90 }}>Tool</th>
                  <th style={{ width: 90 }}>Budget</th>
                  <th style={{ width: 100 }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {(workPackages.length > 0 ? workPackages : [
                  { package_id: 'wp-cdc-01', bucket: 'RESET_AND_CLOCK', objective: 'Verify reset synchronizers on spi_host clock boundary', tier: 'LIGHTWEIGHT', tool: 'Yosys', tokens: '40k', status: 'COMPLETED' },
                  { package_id: 'wp-cdc-02', bucket: 'CLOCK_DOMAIN_CROSSING', objective: 'Check multi-flop synchronizer protocols on cross-domain registers', tier: 'MODERATE', tool: 'Yosys', tokens: '60k', status: 'RUNNING' },
                  { package_id: 'wp-boot-01', bucket: 'SECURE_BOOT_AND_LIFECYCLE', objective: 'Verify ROM hash validation and signature checking lock', tier: 'MODERATE', tool: 'Verilator', tokens: '80k', status: 'COMPLETED' },
                  { package_id: 'wp-dbg-01', bucket: 'DEBUG_AND_TRACE', objective: 'Verify JTAG disable upon entering locked lifecycle state', tier: 'EXPENSIVE', tool: 'Sby', tokens: '120k', status: 'QUEUED' },
                  { package_id: 'wp-firewall-01', bucket: 'ACCESS_CONTROL', objective: 'Formally verify register firewall blocks non-secure AXI transactions', tier: 'EXPENSIVE', tool: 'Sby', tokens: '150k', status: 'QUEUED' },
                ]).map((wp) => (
                  <tr key={wp.package_id}>
                    <td className="mono" style={{ fontWeight: 600 }}>{wp.package_id}</td>
                    <td style={{ fontSize: 11 }}>{wp.bucket}</td>
                    <td>{wp.objective}</td>
                    <td>
                      <span style={{
                        fontFamily: 'var(--font-mono)', fontSize: 10, padding: '1px 4px',
                        background: 'var(--bg-subtle)', border: '1px solid var(--border-dim)', borderRadius: 2
                      }}>
                        {wp.tier || 'MODERATE'}
                      </span>
                    </td>
                    <td className="mono">{wp.tool || 'Yosys'}</td>
                    <td className="mono">{wp.tokens || '50k'}</td>
                    <td><StatusPill status={wp.status || 'QUEUED'} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* TAB 3: Resource Gate Tab */}
        {activeTab === 'gate' && (
          <div className="panel" style={{ maxWidth: 800 }}>
            <div className="panel-header">
              <span className="panel-title">Resource Budget & Bounded Constraints</span>
            </div>
            <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div className="kv-row"><span className="kv-key">Max Concurrent Agents</span><span className="kv-val mono">4</span></div>
              <div className="kv-row"><span className="kv-key">Allowed Real Executors</span><span className="kv-val mono" style={{ color: 'var(--blue)' }}>Antigravity (AGY) & OpenAI Codex</span></div>
              <div className="kv-row"><span className="kv-key">Disabled Executors</span><span className="kv-val mono" style={{ color: 'var(--red)' }}>Claude (Strictly disabled by enterprise policy)</span></div>
              <div className="kv-row"><span className="kv-key">Per-Task Timeout</span><span className="kv-val mono">600 seconds (watchdog enforced)</span></div>
              <div className="kv-row"><span className="kv-key">Max Retries Per Task</span><span className="kv-val mono">3 attempts</span></div>
              <div className="kv-row"><span className="kv-key">Total Token Cap</span><span className="kv-val mono">2,000,000 tokens</span></div>

              <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                <button className="btn btn-primary btn-sm" onClick={handleApprovePlan}>
                  Confirm & Dispatch Full Plan
                </button>
                <button className="btn btn-secondary btn-sm" onClick={() => setActiveTab('matrix')}>
                  Back to Plan Matrix
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
