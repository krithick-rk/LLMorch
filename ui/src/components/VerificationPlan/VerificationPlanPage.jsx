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

const ALL_23_BUCKETS = [
  { id: 'RESET_AND_CLOCK', name: 'Reset & Clock Domain Crossing', app: 'Applicable', obj: 12, ev: 8, state: 'Partial' },
  { id: 'POWER_AND_ENERGY', name: 'Power & Energy Management', app: 'Applicable', obj: 6, ev: 6, state: 'Covered' },
  { id: 'DEBUG_AND_TRACE', name: 'Debug & Trace Authorization', app: 'Applicable', obj: 8, ev: 2, state: 'Partial' },
  { id: 'SIDE_CHANNEL_LEAKAGE', name: 'Side-Channel Leakage Immunity', app: 'Applicable', obj: 5, ev: 0, state: 'Blocked' },
  { id: 'FAULT_INJECTION', name: 'Fault Injection Countermeasures', app: 'Applicable', obj: 7, ev: 3, state: 'Partial' },
  { id: 'INTERCONNECT_AND_FABRIC', name: 'Interconnect & Bus Fabric Firewall', app: 'Applicable', obj: 14, ev: 11, state: 'Partial' },
  { id: 'CRYPTO_ACCELERATOR', name: 'Cryptographic Engine Correctness', app: 'Applicable', obj: 9, ev: 9, state: 'Covered' },
  { id: 'SECURE_BOOT_AND_LIFECYCLE', name: 'Secure Boot & Device Lifecycle', app: 'Applicable', obj: 11, ev: 11, state: 'Covered' },
  { id: 'DMA_AND_BUS_MASTERING', name: 'DMA & Bus Mastering Security', app: 'Applicable', obj: 6, ev: 4, state: 'Partial' },
  { id: 'TEST_AND_MANUFACTURING', name: 'Test & Manufacturing Security', app: 'Applicable', obj: 4, ev: 4, state: 'Covered' },
  { id: 'ACCESS_CONTROL', name: 'Memory & Register Access Control', app: 'Applicable', obj: 15, ev: 13, state: 'Partial' },
  { id: 'MEMORY_SUBSYSTEM', name: 'Memory Subsystem & Scrambling', app: 'Applicable', obj: 8, ev: 5, state: 'Partial' },
  { id: 'INTERRUPT_HANDLING', name: 'Interrupt Handling & Prioritization', app: 'Applicable', obj: 6, ev: 6, state: 'Covered' },
  { id: 'TAMPER_RESISTANCE', name: 'Physical & Environmental Tamper', app: 'Unknown', obj: 4, ev: 0, state: 'Blocked' },
  { id: 'PERIPHERAL_INTERFACES', name: 'Peripheral Interfaces (SPI, I2C, UART)', app: 'Applicable', obj: 10, ev: 8, state: 'Partial' },
  { id: 'FIRMWARE_HARDWARE_INTERFACE', name: 'Firmware-Hardware Interface Handshake', app: 'Applicable', obj: 7, ev: 5, state: 'Partial' },
  { id: 'CLOCK_DOMAIN_CROSSING', name: 'Structural CDC / RDC Verification', app: 'Applicable', obj: 12, ev: 9, state: 'Partial' },
  { id: 'REGISTER_ACCESS', name: 'Register Access Policies & Privileges', app: 'Applicable', obj: 16, ev: 16, state: 'Covered' },
  { id: 'FORMAL_PROPERTY_VERIFICATION', name: 'Formal Security Invariant Checking', app: 'Applicable', obj: 8, ev: 4, state: 'Partial' },
  { id: 'CODE_COVERAGE', name: 'RTL Line, Branch & Toggle Coverage', app: 'Applicable', obj: 10, ev: 7, state: 'Partial' },
  { id: 'FUNCTIONAL_COVERAGE', name: 'Functional Coverage Model Closure', app: 'Applicable', obj: 12, ev: 8, state: 'Partial' },
  { id: 'SECURITY_REGRESSION', name: 'Automated Security Regression Suite', app: 'Applicable', obj: 5, ev: 5, state: 'Covered' },
  { id: 'ANALOG_MIXED_SIGNAL', name: 'Analog / Mixed-Signal Boundary Check', app: 'Not Applicable', obj: 0, ev: 0, state: 'Not Applicable' },
]

export default function VerificationPlanPage({ planId, onNavigate }) {
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
      const res = await api.listVerificationPlans()
      const list = res.plans || []
      setPlans(list)
      const targetId = planId || (list.length > 0 ? list[0].plan_id : null)
      if (targetId) {
        await loadPlanDetail(targetId)
      }
    } catch (err) {
      console.error('Failed to load verification plans:', err)
    } finally {
      setLoading(false)
    }
  }, [planId])

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

  const handleApprovePlan = async () => {
    if (!selectedPlan) return
    try {
      setActionMsg('Approving plan and activating work package tasks...')
      const res = await api.approveVerificationPlan(selectedPlan.plan_id)
      setActionMsg(`Plan approved! ${res.activated_tasks?.length || 0} tasks dispatched to queue.`)
      await loadPlanDetail(selectedPlan.plan_id)
    } catch (err) {
      setActionMsg(`Error: ${err.message}`)
    }
  }

  // Work package counts
  const totalPackages = selectedPlan?.total_work_packages || workPackages.length || 23
  const isLargeTask = totalPackages >= 10

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
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
                <StatusPill status={selectedPlan.status || 'PROPOSED'} />
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

        {/* Primary Plan Actions (Section 11) */}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {selectedPlan?.status !== 'APPROVED' ? (
            <button
              id="btn-approve-plan"
              className="btn btn-primary btn-sm"
              onClick={handleApprovePlan}
            >
              ✓ Approve Plan
            </button>
          ) : (
            <button className="btn btn-success btn-sm" disabled>
              ✓ Plan Approved
            </button>
          )}

          <button
            className="btn btn-secondary btn-sm"
            onClick={() => {
              if (onNavigate) onNavigate('tasks')
            }}
          >
            Run Recommended Work
          </button>

          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setActiveTab('gate')}
          >
            Run Full Plan
          </button>

          <button
            className="btn btn-secondary btn-sm"
            onClick={handleGeneratePlan}
            disabled={generating}
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

      {/* ── Summary & Metrics Bar ───────────────────────────────────────────── */}
      <div style={{
        padding: '8px 20px', background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap', fontSize: 11
      }}>
        <div>
          <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Work Packages: </span>
          <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{totalPackages}</span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Objectives: </span>
          <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{objectives.length || 184}</span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Applicable Buckets: </span>
          <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--blue)' }}>22 / 23</span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Estimated Budget: </span>
          <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
            ~{selectedPlan?.estimated_tokens ? (selectedPlan.estimated_tokens / 1000).toFixed(0) : '480'}k tokens
          </span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Estimated Time: </span>
          <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>1.5 – 3.0 hours</span>
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
                  <th>Bucket Name</th>
                  <th style={{ width: 130 }}>Applicability</th>
                  <th style={{ width: 90 }}>Objectives</th>
                  <th style={{ width: 90 }}>Evidence</th>
                  <th style={{ width: 110 }}>Closure State</th>
                  <th style={{ width: 100 }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {ALL_23_BUCKETS.map((b, idx) => (
                  <tr key={b.id}>
                    <td className="mono" style={{ color: 'var(--text-muted)' }}>{idx + 1}</td>
                    <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      {b.name}
                      <span className="mono" style={{ display: 'block', fontSize: 10, color: 'var(--text-muted)' }}>
                        {b.id}
                      </span>
                    </td>
                    <td>
                      <span style={{
                        fontFamily: 'var(--font-mono)', fontSize: 11,
                        color: b.app === 'Applicable' ? 'var(--blue)' : 'var(--text-muted)',
                        fontWeight: 500
                      }}>
                        {b.app}
                      </span>
                    </td>
                    <td className="mono">{b.obj}</td>
                    <td className="mono">{b.ev}</td>
                    <td>
                      <StatusPill status={b.state} />
                    </td>
                    <td>
                      <button
                        className="btn btn-secondary btn-sm"
                        style={{ fontSize: 10, padding: '1px 6px' }}
                        onClick={() => {
                          if (onNavigate) onNavigate('tasks')
                        }}
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
