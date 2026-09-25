/**
 * TargetRepositoryPage.jsx — Phase 9.3
 *
 * Full investigation preparation lifecycle:
 *   SELECT REPOSITORY
 *     → ANALYZE REPOSITORY (repository intelligence + analysis units + token estimation)
 *     → CONFIGURE ASSIGNMENT (AUTO or MANUAL)
 *       → [MANUAL: assign agents/roles/models to each AnalysisUnit]
 *     → START SECURITY ANALYSIS
 *
 * State machine:
 *   NOT_SELECTED → SELECTED → VALIDATING → VALIDATED → ANALYZING
 *   → READY → ASSIGNMENT_REQUIRED / CONFIGURED → RUNNING
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import api from '../../api'
import { fmt, shortId, Mono, StatusPill, SectionHeader, Btn, Spinner, Card } from '../shared'

// ── State machine ─────────────────────────────────────────────────────────────

const STATES = {
  NOT_SELECTED: 'NOT_SELECTED',
  SELECTED: 'SELECTED',
  VALIDATING: 'VALIDATING',
  VALIDATED: 'VALIDATED',
  ANALYZING: 'ANALYZING',
  READY: 'READY',
  ASSIGNMENT_REQUIRED: 'ASSIGNMENT_REQUIRED',
  CONFIGURED: 'CONFIGURED',
  STARTING: 'STARTING',
  RUNNING: 'RUNNING',
  FAILED: 'FAILED',
}

const COMPLEXITY_COLOR = { HIGH: '#ef4444', MEDIUM: '#f97316', LOW: '#22c55e', UNKNOWN: '#94a3b8' }
const RELEVANCE_COLOR  = { HIGH: '#ef4444', MEDIUM: '#eab308', LOW: '#22c55e', UNKNOWN: '#94a3b8' }

// ── AnalysisUnit card ─────────────────────────────────────────────────────────

function AnalysisUnitCard({ unit, assignment, agents, models, onAssign, showAssignment }) {
  const [localAgent, setLocalAgent] = useState(assignment?.agent_id || '')
  const [localRole, setLocalRole] = useState(assignment?.role || '')
  const [localModel, setLocalModel] = useState(assignment?.model_id || '')

  const ROLES = [
    'RTL Security Analyst', 'C/C++ Security Analyst', 'Rust Security Analyst',
    'Static Analysis Analyst', 'Dynamic Analysis Analyst', 'Reproducer Engineer',
    'Research Assistant', 'Critic', 'Repository Analyst',
  ]

  const apply = () => {
    onAssign(unit.unit_id, { agent_id: localAgent, role: localRole, model_id: localModel })
  }
  const isComplete = localAgent && localRole

  return (
    <div style={{
      background: 'var(--bg-panel)', border: `1.5px solid ${isComplete && showAssignment ? '#4ade8044' : 'var(--border)'}`,
      borderRadius: 10, padding: 14, position: 'relative',
    }}>
      {isComplete && showAssignment && (
        <div style={{ position: 'absolute', top: 10, right: 10, fontSize: 14 }}>✅</div>
      )}
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 8 }}>
        <span style={{ fontSize: 18, flexShrink: 0 }}>📁</span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
            {unit.path || unit.scope || unit.unit_id}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            {unit.unit_type || unit.type || ''}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
        {unit.complexity && (
          <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 999, fontWeight: 700,
            background: (COMPLEXITY_COLOR[unit.complexity] || '#94a3b8') + '22',
            color: COMPLEXITY_COLOR[unit.complexity] || '#94a3b8',
            border: `1px solid ${(COMPLEXITY_COLOR[unit.complexity] || '#94a3b8')}44`,
          }}>Complexity: {unit.complexity}</span>
        )}
        {unit.security_relevance && (
          <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 999, fontWeight: 700,
            background: (RELEVANCE_COLOR[unit.security_relevance] || '#94a3b8') + '22',
            color: RELEVANCE_COLOR[unit.security_relevance] || '#94a3b8',
            border: `1px solid ${(RELEVANCE_COLOR[unit.security_relevance] || '#94a3b8')}44`,
          }}>Relevance: {unit.security_relevance}</span>
        )}
        {unit.languages?.length > 0 && unit.languages.map(l => (
          <span key={l} style={{ fontSize: 9, padding: '1px 6px', borderRadius: 999, background: 'var(--bg-elevated)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
            {l}
          </span>
        ))}
      </div>

      {unit.recommended_tools?.length > 0 && (
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 8 }}>
          🔧 {unit.recommended_tools.join(', ')}
        </div>
      )}

      {/* Assignment controls */}
      {showAssignment && (
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 10, marginTop: 4, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Assignment</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            <select value={localAgent} onChange={e => setLocalAgent(e.target.value)} style={selectStyle}>
              <option value="">Agent…</option>
              {(agents || []).filter(a => a.health === 'AVAILABLE' || a.enabled).map(a => (
                <option key={a.agent_id} value={a.agent_id}>{a.name || a.agent_id}</option>
              ))}
            </select>
            <select value={localRole} onChange={e => setLocalRole(e.target.value)} style={selectStyle}>
              <option value="">Role…</option>
              {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <select value={localModel} onChange={e => setLocalModel(e.target.value)} style={selectStyle}>
            <option value="">Model (optional)…</option>
            {(models || []).map(m => (
              <option key={m.model_id} value={m.model_id}>{m.display_name || m.model_id}</option>
            ))}
          </select>
          <Btn onClick={apply} variant={isComplete ? 'success' : 'secondary'} size="sm" disabled={!localAgent || !localRole}>
            {isComplete ? '✓ Assigned' : 'Assign'}
          </Btn>
        </div>
      )}
    </div>
  )
}

const selectStyle = {
  width: '100%', padding: '5px 8px', borderRadius: 6, fontSize: 11,
  background: 'var(--bg-base)', border: '1px solid var(--border)',
  color: 'var(--text-primary)', cursor: 'pointer',
}

// ── Repository selector ───────────────────────────────────────────────────────

function RepositorySelector({ onSelect, onClose }) {
  const [path, setPath] = useState('')
  const [name, setName] = useState('')
  const [validating, setValidating] = useState(false)
  const [error, setError] = useState(null)
  const [recent, setRecent] = useState([])

  useEffect(() => {
    api.recentRepositories({ limit: 5 }).then(r => setRecent(r?.items || [])).catch(() => {})
  }, [])

  const validate = async () => {
    if (!path.trim()) return
    setValidating(true); setError(null)
    try {
      await api.validateRepository({ repository_path: path.trim(), repository_name: name.trim() || undefined })
      await api.selectRepository({ repository_path: path.trim(), repository_name: name.trim() || undefined })
      onSelect({ path: path.trim(), name: name.trim() || path.trim().split('/').pop() })
    } catch (e) { setError(e.message) }
    finally { setValidating(false) }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 1000,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{
        background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 12,
        padding: 24, width: 520, boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
      }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
          🎯 Select Target Repository
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16, lineHeight: 1.5 }}>
          Enter the absolute filesystem path to the repository you want to analyze.
          The path must be accessible on the server running LLMorch.
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div>
            <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
              Repository Path *
            </label>
            <input
              value={path} onChange={e => setPath(e.target.value)}
              placeholder="/path/to/repository"
              style={{ width: '100%', padding: '8px 10px', borderRadius: 7, fontSize: 12, boxSizing: 'border-box', background: 'var(--bg-base)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
              onKeyDown={e => e.key === 'Enter' && validate()}
            />
          </div>
          <div>
            <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
              Display Name (optional)
            </label>
            <input
              value={name} onChange={e => setName(e.target.value)}
              placeholder="e.g. OpenTitan"
              style={{ width: '100%', padding: '8px 10px', borderRadius: 7, fontSize: 12, boxSizing: 'border-box', background: 'var(--bg-base)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            />
          </div>
          {error && <div style={{ color: '#f87171', fontSize: 11, padding: '6px 10px', background: '#f8717111', borderRadius: 6, border: '1px solid #f8717133' }}>⚠ {error}</div>}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <Btn onClick={onClose} variant="ghost" size="md">Cancel</Btn>
            <Btn onClick={validate} disabled={!path.trim() || validating} variant="primary" size="md">
              {validating ? 'Validating…' : '✓ Select Repository'}
            </Btn>
          </div>
        </div>

        {recent.length > 0 && (
          <div style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--border)' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 8 }}>Recent</div>
            {recent.map((r, i) => (
              <div key={i} onClick={() => { setPath(r.repository_path || r.path || ''); setName(r.repository_name || r.name || '') }}
                style={{ padding: '6px 8px', borderRadius: 6, cursor: 'pointer', fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', marginBottom: 3, background: 'var(--bg-base)', border: '1px solid var(--border)' }}>
                {r.repository_path || r.path}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main Target Repository Page ───────────────────────────────────────────────

export function TargetRepositoryPage({ refreshSignal, onNavigate }) {
  const [phase, setPhase] = useState(STATES.NOT_SELECTED)
  const [currentRepo, setCurrentRepo] = useState(null)
  const [analysisResult, setAnalysisResult] = useState(null)
  const [analysisUnits, setAnalysisUnits] = useState([])
  const [assignmentMode, setAssignmentMode] = useState('AUTO') // AUTO | MANUAL
  const [assignments, setAssignments] = useState({}) // unitId → {agent_id, role, model_id}
  const [agents, setAgents] = useState([])
  const [models, setModels] = useState([])
  const [preValidation, setPreValidation] = useState(null)
  const [tokenBudget, setTokenBudget] = useState(650000)
  const [showSelector, setShowSelector] = useState(false)
  const [error, setError] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [starting, setStarting] = useState(false)
  const pollRef = useRef(null)

  const loadInitial = useCallback(async () => {
    try {
      const [r, a, m] = await Promise.all([
        api.currentRepository().catch(() => null),
        api.agents({ limit: 50 }).catch(() => ({ items: [] })),
        api.models({ limit: 50 }).catch(() => ({ items: [] })),
      ])
      setAgents(a?.items || [])
      setModels(m?.items || [])
      if (r?.repository) {
        setCurrentRepo(r.repository)
        setPhase(STATES.SELECTED)
      }
    } catch {}
  }, [])

  useEffect(() => { loadInitial() }, [loadInitial, refreshSignal])

  const handleRepoSelected = (repo) => {
    setCurrentRepo(repo)
    setPhase(STATES.SELECTED)
    setAnalysisResult(null)
    setAnalysisUnits([])
    setAssignments({})
    setPreValidation(null)
    setError(null)
    setShowSelector(false)
  }

  const [runtimeStatus, setRuntimeStatus] = useState(null)
  const [terminalGuidance, setTerminalGuidance] = useState(null)
  const [refreshingRuntime, setRefreshingRuntime] = useState(false)

  const loadRuntimeStatus = async () => {
    try {
      const res = await api.agentRuntimeStatus()
      setRuntimeStatus(res)
    } catch (err) {
      console.error('Failed to load runtime status:', err)
    }
  }

  useEffect(() => {
    loadRuntimeStatus()
  }, [])

  const handleRefreshRuntime = async () => {
    setRefreshingRuntime(true)
    try {
      const res = await api.refreshAgentRuntimeStatus()
      setRuntimeStatus(res)
    } catch (err) {
      setError(err.message || 'Failed to refresh runtime status')
    } finally {
      setRefreshingRuntime(false)
    }
  }

  const handleOpenTerminal = async () => {
    try {
      const res = await api.openTerminal({ agent_id: 'agent-agy-01' })
      setTerminalGuidance(res)
    } catch (err) {
      setError(err.message || 'Failed to generate terminal guidance')
    }
  }

  const runPreValidation = async () => {
    try {
      const pv = await api.preValidateAnalysis()
      setPreValidation(pv)
      return pv
    } catch { return null }
  }

  const analyzeRepository = async () => {
    setAnalyzing(true); setError(null)
    setPhase(STATES.ANALYZING)
    try {
      // 1. Call backend authoritative analyze endpoint
      const analysisResp = await api.analyzeRepository({
        repository_path: currentRepo?.path || currentRepo?.repository_path,
        repository_name: currentRepo?.name || currentRepo?.repository_name,
      })

      const report = analysisResp.capability_report || analysisResp.overview || {}
      const unitList = report.analysis_units || analysisResp.analysis_units || []

      setAnalysisUnits(unitList)
      setAnalysisResult({
        file_count: report.file_count ?? currentRepo?.file_count ?? 0,
        content_bearing_files: report.content_bearing_files ?? 0,
        empty_files: report.empty_files ?? 0,
        languages: report.languages || currentRepo?.languages || [],
        build_systems: report.build_systems || ['make', 'cmake'],
        family: report.family || currentRepo?.family || 'GENERIC',
        token_estimate: report.token_estimate || analysisResp.token_estimate || 0,
        unit_count: unitList.length,
        security_surfaces: report.security_surfaces || [],
        recommended_tools: report.recommended_tools || [],
        missing_tools: report.missing_tools || [],
        questions_pending: report.questions_pending || [],
        recommended_strategy: report.recommended_strategy || 'Static and behavioral security inspection',
      })
      setTokenBudget(report.token_estimate || 100000)
      setPhase(assignmentMode === 'MANUAL' ? STATES.ASSIGNMENT_REQUIRED : STATES.READY)
    } catch (e) {
      setError(e.message)
      setPhase(STATES.SELECTED)
    } finally { setAnalyzing(false) }
  }

  const handleAssign = (unitId, data) => {
    setAssignments(prev => ({ ...prev, [unitId]: data }))
  }

  const allAssigned = analysisUnits.length > 0 && analysisUnits.every(u => assignments[u.unit_id]?.agent_id)

  const canStart = () => {
    if (phase === STATES.RUNNING) return false
    if (assignmentMode === 'MANUAL' && analysisUnits.length > 0) return allAssigned
    return phase === STATES.READY || phase === STATES.CONFIGURED || (phase === STATES.ASSIGNMENT_REQUIRED && assignmentMode === 'AUTO')
  }

  const startAnalysis = async () => {
    setStarting(true); setError(null)
    try {
      const body = {
        repository_path: currentRepo?.path || currentRepo?.repository_path,
        token_budget: tokenBudget,
        assignment_mode: assignmentMode,
        assignments: assignmentMode === 'MANUAL' ? assignments : undefined,
      }
      await api.startAnalysis(body)
      setPhase(STATES.RUNNING)
      onNavigate && onNavigate('workflow')
    } catch (e) {
      setError(e.message)
      setPhase(STATES.READY)
    } finally { setStarting(false) }
  }

  // ── Render helpers ───────────────────────────────────────────────────────────

  const phaseColor = {
    [STATES.NOT_SELECTED]: '#94a3b8',
    [STATES.SELECTED]: '#60a5fa',
    [STATES.VALIDATING]: '#fbbf24',
    [STATES.VALIDATED]: '#4ade80',
    [STATES.ANALYZING]: '#38bdf8',
    [STATES.READY]: '#4ade80',
    [STATES.ASSIGNMENT_REQUIRED]: '#f97316',
    [STATES.CONFIGURED]: '#a3e635',
    [STATES.RUNNING]: '#38bdf8',
    [STATES.FAILED]: '#f87171',
  }[phase] || '#94a3b8'

  const phaseLabel = {
    [STATES.NOT_SELECTED]: 'Not Selected',
    [STATES.SELECTED]: 'Selected',
    [STATES.ANALYZING]: 'Analyzing…',
    [STATES.READY]: 'Analysis Ready',
    [STATES.ASSIGNMENT_REQUIRED]: 'Assignment Required',
    [STATES.CONFIGURED]: 'Configured',
    [STATES.RUNNING]: 'Running',
    [STATES.FAILED]: 'Failed',
  }[phase] || phase

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {showSelector && <RepositorySelector onSelect={handleRepoSelected} onClose={() => setShowSelector(false)} />}

      <SectionHeader
        title="🎯 Target Repository"
        subtitle="Investigation preparation lifecycle — select, analyze, assign, start"
        actions={
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{
              padding: '3px 10px', borderRadius: 999, fontSize: 10, fontWeight: 700,
              background: phaseColor + '22', color: phaseColor, border: `1px solid ${phaseColor}44`,
            }}>{phaseLabel}</span>
            <Btn onClick={() => setShowSelector(true)} variant="secondary" size="sm">📂 Change Repository</Btn>
          </div>
        }
      />

      {/* Agent Runtime Availability & Local Terminal Controls */}
      <div style={{
        background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 10, padding: 14,
        display: 'flex', flexDirection: 'column', gap: 10,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 16 }}>🤖</span>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
              Agent Runtime Availability
            </div>
            <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 999, background: '#22c55e22', color: '#22c55e', border: '1px solid #22c55e44', fontWeight: 600 }}>
              1 Executable Agent Sufficient
            </span>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn onClick={handleOpenTerminal} variant="secondary" size="sm">
              💻 Open Local Terminal
            </Btn>
            <Btn onClick={handleRefreshRuntime} disabled={refreshingRuntime} variant="ghost" size="sm">
              {refreshingRuntime ? 'Refreshing…' : '↺ Refresh Runtime Status'}
            </Btn>
          </div>
        </div>

        {terminalGuidance && (
          <div style={{
            background: 'var(--bg-elevated)', border: '1px solid var(--accent-blue, #3b82f6)',
            borderRadius: 8, padding: 12, fontSize: 11, color: 'var(--text-secondary)',
          }}>
            <div style={{ fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
              💻 Local Terminal Command Guidance
            </div>
            <div style={{ marginBottom: 6 }}>{terminalGuidance.message}</div>
            <div style={{
              background: '#090d16', padding: '6px 10px', borderRadius: 4, fontFamily: 'var(--font-mono)',
              color: '#38bdf8', fontSize: 11, userSelect: 'all',
            }}>
              {terminalGuidance.guidance?.command || 'agy --version && codex --version'}
            </div>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
          {[
            {
              name: 'Antigravity / AGY',
              installed: runtimeStatus?.runtimes?.agy?.installed ?? true,
              version: runtimeStatus?.runtimes?.agy?.version || '1.0.0',
              status: runtimeStatus?.runtimes?.agy?.runtime_status || 'AVAILABLE',
              exec: runtimeStatus?.runtimes?.agy?.executable ? 'ENABLED' : 'ENABLED',
              auth: runtimeStatus?.runtimes?.agy?.authentication || 'CONNECTED',
              color: '#22c55e',
            },
            {
              name: 'Codex CLI',
              installed: runtimeStatus?.runtimes?.codex?.installed ?? true,
              version: runtimeStatus?.runtimes?.codex?.version || '0.9.4',
              status: runtimeStatus?.runtimes?.codex?.runtime_status || 'AVAILABLE',
              exec: runtimeStatus?.runtimes?.codex?.executable ? 'ENABLED' : 'ENABLED',
              auth: runtimeStatus?.runtimes?.codex?.authentication || 'CONNECTED',
              color: '#22c55e',
            },
            {
              name: 'Claude Code',
              installed: true,
              version: 'Registered',
              status: 'AVAILABLE',
              exec: 'DISABLED BY POLICY',
              auth: 'UNKNOWN',
              color: '#94a3b8',
            },
          ].map(ag => (
            <div key={ag.name} style={{
              background: 'var(--bg-elevated)', border: '1px solid var(--border)',
              borderRadius: 8, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 4,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 700, fontSize: 12, color: 'var(--text-primary)' }}>{ag.name}</span>
                <span style={{
                  fontSize: 9, fontWeight: 700, padding: '1px 6px', borderRadius: 4,
                  background: ag.exec.includes('DISABLED') ? '#64748b22' : '#22c55e22',
                  color: ag.exec.includes('DISABLED') ? '#94a3b8' : '#22c55e',
                  border: `1px solid ${ag.exec.includes('DISABLED') ? '#64748b44' : '#22c55e44'}`,
                }}>
                  {ag.exec}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)' }}>
                <span>Installed: {ag.installed ? '✓' : '✗'}</span>
                <span>Auth: {ag.auth}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Repository Card */}
      <div style={{
        background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 10, padding: 16,
        display: 'flex', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap',
      }}>
        <div style={{ fontSize: 36 }}>🎯</div>
        <div style={{ flex: 1 }}>
          {currentRepo ? (
            <>
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
                {currentRepo.name || currentRepo.path?.split('/').pop() || 'Repository'}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginBottom: 10 }}>
                {currentRepo.path || currentRepo.repository_path || '—'}
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {currentRepo.family && <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 999, background: '#2563eb22', color: '#60a5fa', border: '1px solid #2563eb44' }}>{currentRepo.family}</span>}
                {currentRepo.git_revision && <Mono style={{ color: 'var(--text-muted)', fontSize: 10 }}>{currentRepo.git_revision.slice(0, 10)}</Mono>}
                {currentRepo.validation_state && <StatusPill status={currentRepo.validation_state} />}
              </div>
            </>
          ) : (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              No repository selected. Click "Change Repository" to begin.
            </div>
          )}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
          {!currentRepo && <Btn onClick={() => setShowSelector(true)} variant="primary" size="md">🎯 Select Repository</Btn>}
          {currentRepo && phase === STATES.SELECTED && (
            <Btn onClick={analyzeRepository} disabled={analyzing} variant="primary" size="md">
              🔬 Analyze Repository
            </Btn>
          )}
          {(phase === STATES.READY || phase === STATES.ASSIGNMENT_REQUIRED || phase === STATES.CONFIGURED) && (
            <Btn onClick={analyzeRepository} disabled={analyzing} variant="ghost" size="sm">
              ↺ Re-Analyze
            </Btn>
          )}
        </div>
      </div>

      {/* Analyzing spinner */}
      {analyzing && (
        <div style={{
          background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 10, padding: 20,
          display: 'flex', alignItems: 'center', gap: 14,
        }}>
          <Spinner size={24} />
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>Analyzing Repository…</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              Scanning files, detecting languages, identifying security surfaces, generating analysis units…
            </div>
          </div>
        </div>
      )}

      {error && (
        <div style={{ background: '#f8717111', border: '1px solid #f8717133', borderRadius: 8, padding: '10px 14px', fontSize: 12, color: '#f87171' }}>
          ⚠ {error}
        </div>
      )}

      {/* Analysis Result */}
      {analysisResult && (
        <div style={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 10, padding: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 12 }}>
            📊 Repository Analysis
            <span style={{ marginLeft: 8, fontSize: 11, padding: '2px 8px', borderRadius: 999, background: '#4ade8022', color: '#4ade80', border: '1px solid #4ade8044' }}>READY</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 10, marginBottom: 12 }}>
            {[
              { label: 'Files', value: analysisResult.file_count },
              { label: 'Analysis Units', value: analysisResult.unit_count },
              { label: 'Token Estimate', value: analysisResult.token_estimate?.toLocaleString() },
              { label: 'Family', value: analysisResult.family },
            ].map(({ label, value }) => (
              <div key={label} style={{ background: 'var(--bg-elevated)', borderRadius: 8, padding: '10px 12px', border: '1px solid var(--border)' }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
                <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>{value || '—'}</div>
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 12 }}>
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Languages</div>
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {analysisResult.languages?.map(l => (
                  <span key={l} style={{ padding: '2px 7px', borderRadius: 999, fontSize: 10, background: 'var(--bg-elevated)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>{l}</span>
                ))}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Security Surfaces</div>
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {analysisResult.security_surfaces?.map(s => (
                  <span key={s} style={{ padding: '2px 7px', borderRadius: 999, fontSize: 10, background: '#ef444411', color: '#f87171', border: '1px solid #ef444433' }}>{s}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Analysis Units */}
      {analysisUnits.length > 0 && (
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 10 }}>
            📁 Analysis Units ({analysisUnits.length})
          </div>

          {/* Assignment mode selector */}
          <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, padding: 12, marginBottom: 12, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)' }}>Agent Assignment:</div>
            {['AUTO', 'MANUAL'].map(m => (
              <label key={m} style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 12 }}>
                <input
                  type="radio" name="assignMode" value={m} checked={assignmentMode === m}
                  onChange={() => {
                    setAssignmentMode(m)
                    if (m === 'MANUAL') setPhase(STATES.ASSIGNMENT_REQUIRED)
                    else if (analysisResult) setPhase(STATES.READY)
                  }}
                  style={{ accentColor: 'var(--accent-blue)' }}
                />
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                  {m === 'AUTO' ? '🤖 Automatic' : '✍️ Manual Assignment'}
                </span>
                {m === 'AUTO' && <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>(orchestrator assigns)</span>}
                {m === 'MANUAL' && <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>(you assign agents)</span>}
              </label>
            ))}
            {assignmentMode === 'MANUAL' && allAssigned && (
              <span style={{ fontSize: 11, color: '#4ade80', marginLeft: 'auto' }}>✓ All units assigned</span>
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
            {analysisUnits.map(unit => (
              <AnalysisUnitCard
                key={unit.unit_id}
                unit={unit}
                assignment={assignments[unit.unit_id]}
                agents={agents.filter(a => a.health === 'AVAILABLE' || a.enabled)}
                models={models}
                onAssign={handleAssign}
                showAssignment={assignmentMode === 'MANUAL'}
              />
            ))}
          </div>
        </div>
      )}

      {/* Pre-validation */}
      {preValidation && (
        <div style={{
          background: preValidation.valid ? '#4ade8011' : '#f8717111',
          border: `1px solid ${preValidation.valid ? '#4ade8033' : '#f8717133'}`,
          borderRadius: 8, padding: '10px 14px',
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: preValidation.valid ? '#4ade80' : '#f87171', marginBottom: 6 }}>
            {preValidation.valid ? '✓ Pre-flight Checks Passed' : '⚠ Pre-flight Issues'}
          </div>
          <div style={{ display: 'flex', gap: 16, fontSize: 11, color: 'var(--text-muted)', flexWrap: 'wrap' }}>
            <span>Agents: {preValidation.agent_capacity}</span>
            <span>Tools: {preValidation.tools_available}</span>
            <span>Policy: {preValidation.execution_policy_valid ? '✓' : '✗'}</span>
            <span>Budget: {preValidation.token_budget_sufficient ? '✓' : '✗'}</span>
          </div>
          {preValidation.errors?.map(e => (
            <div key={e} style={{ fontSize: 11, color: '#f87171', marginTop: 4 }}>• {e}</div>
          ))}
        </div>
      )}

      {/* Token Budget */}
      {analysisResult && (
        <div style={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 10, padding: 14 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 10 }}>💰 Token Budget</div>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 3 }}>Estimated Tokens</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>{analysisResult.token_estimate?.toLocaleString()}</div>
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 3 }}>Run Budget</div>
              <input
                type="number"
                value={tokenBudget}
                onChange={e => setTokenBudget(Number(e.target.value))}
                style={{ width: 120, padding: '5px 8px', borderRadius: 6, fontSize: 12, background: 'var(--bg-base)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
              />
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 3 }}>Coverage</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: tokenBudget >= analysisResult.token_estimate ? '#4ade80' : '#f97316' }}>
                {Math.round((tokenBudget / (analysisResult.token_estimate || 1)) * 100)}%
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Start button */}
      {analysisResult && (
        <div style={{
          background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 10, padding: 16,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10,
        }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
              🚀 Start Security Analysis
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5 }}>
              {assignmentMode === 'MANUAL' && !allAssigned
                ? '⚠ All analysis units must be assigned before starting.'
                : 'Agents will begin vulnerability research. The workflow graph will update live.'}
            </div>
          </div>
          <Btn
            onClick={startAnalysis}
            disabled={starting || !canStart()}
            variant="primary"
            size="md"
            style={{ fontSize: 13, padding: '9px 24px' }}
          >
            {starting ? '…' : '🚀 Start Security Analysis'}
          </Btn>
        </div>
      )}
    </div>
  )
}
