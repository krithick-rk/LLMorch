/**
 * ProjectHomePage.jsx — Professional Engineering Project Home
 * Sections 8, 9, 10, 11:
 * - Deterministic repository intake summary before autonomous analysis
 * - Waits for user direction: [ Analyze Repository ], [ Start Verification Planning ], [ Create Task ]
 * - Tailored handling for small/unrelated directories (hello.c, script.py)
 * - Natural User Instruction box with structured INTERPRETED ACTION confirmation
 */

import { useState, useEffect, useCallback } from 'react'
import api from '../api'
import { StatusPill, Spinner, fmt, Mono } from './shared'

export default function ProjectHomePage({ activeProject, onNavigate, onOpenCreateTask }) {
  const [briefing, setBriefing] = useState(null)
  const [loading, setLoading] = useState(true)
  const [instruction, setInstruction] = useState('')
  const [interpreting, setInterpreting] = useState(false)
  const [interpretedAction, setInterpretedAction] = useState(null)
  const [dispatchMsg, setDispatchMsg] = useState(null)

  const loadBriefing = useCallback(async () => {
    if (!activeProject?.project_id) return
    try {
      setLoading(true)
      const data = await api.projectBriefing(activeProject.project_id).catch(() => null)
      setBriefing(data)
    } finally {
      setLoading(false)
    }
  }, [activeProject])

  useEffect(() => {
    loadBriefing()
  }, [loadBriefing])

  const handleInterpret = async () => {
    if (!instruction.trim() || !activeProject?.project_id) return
    try {
      setInterpreting(true)
      setDispatchMsg(null)
      const res = await api.interpretInstruction(activeProject.project_id, { instruction })
      setInterpretedAction(res)
    } catch (err) {
      alert(`Failed to interpret instruction: ${err.message}`)
    } finally {
      setInterpreting(false)
    }
  }

  const handleConfirmAction = async () => {
    if (!interpretedAction?.suggested_task) return
    try {
      const taskPayload = {
        objective: interpretedAction.suggested_task.title || interpretedAction.goal,
        target_component: interpretedAction.target,
        risk_level: 'MEDIUM',
        assigned_agent_id: interpretedAction.suggested_task.agent || 'AGY',
        inputs: {
          goal: interpretedAction.goal,
          method: interpretedAction.method,
          tool: interpretedAction.tool,
          scope: interpretedAction.target,
          ...interpretedAction.parameters,
        }
      }
      const res = await api.createTask(taskPayload)
      setDispatchMsg(`Task dispatched successfully: ${res.task_id || 'new task'}. Switching to Task Detail...`)
      setTimeout(() => {
        if (res.task_id) {
          onNavigate('task', { entityId: res.task_id })
        } else {
          onNavigate('tasks')
        }
      }, 900)
    } catch (err) {
      alert(`Failed to dispatch action: ${err.message}`)
    }
  }

  if (loading) return <Spinner />

  const isSmall = briefing?.is_small_or_generic || false
  const intake = briefing || activeProject?.metadata?.intake || {}

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: '100%', padding: '24px 28px', background: 'var(--bg-base)' }}>
      {/* ── Page Header ──────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-bright)' }}>
              Project Home: {activeProject?.name || 'Untitled Project'}
            </h1>
            <span className={`badge badge-${(activeProject?.status || 'READY').toLowerCase()}`} style={{ fontSize: 11 }}>
              {activeProject?.status || 'READY'}
            </span>
          </div>
          <div className="mono text-muted" style={{ fontSize: 13, marginTop: 4 }}>
            Directory: <strong>{activeProject?.target_directory}</strong> · Revision: {intake.revision || 'HEAD'}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary btn-sm" onClick={loadBriefing}>
            ↺ Refresh Intake
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => onNavigate('master')}>
            ▶ Open Master Session
          </button>
        </div>
      </div>

      {dispatchMsg && (
        <div style={{ padding: '10px 16px', background: 'var(--green-bg)', border: '1px solid var(--green-border)', color: 'var(--green)', fontSize: 13, borderRadius: 3, marginBottom: 16 }}>
          ✓ {dispatchMsg}
        </div>
      )}

      {/* ── Repository Intake & Classification Strip ─────────────────────────── */}
      <div className="panel" style={{ marginBottom: 20, boxShadow: 'var(--shadow-sm)' }}>
        <div className="panel-header" style={{ padding: '12px 18px', background: 'var(--bg-surface)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
              REPOSITORY INTAKE & INVENTORY
            </span>
            <span className="badge badge-ready" style={{ fontSize: 10 }}>
              DETERMINISTIC SCAN COMPLETE
            </span>
          </div>
          <span className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Classification: <strong style={{ color: 'var(--blue)' }}>{intake.classification || 'Generic Repository'}</strong>
          </span>
        </div>

        <div className="panel-body" style={{ padding: '18px', display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14, borderBottom: '1px solid var(--border-dim)' }}>
          <div style={{ background: 'var(--bg-subtle)', padding: '10px 14px', borderRadius: 3, border: '1px solid var(--border-dim)' }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Total Files</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-bright)', marginTop: 2 }}>
              {intake.files_summary?.total_analyzable || intake.total_files || 0}
            </div>
          </div>

          <div style={{ background: 'var(--bg-subtle)', padding: '10px 14px', borderRadius: 3, border: '1px solid var(--border-dim)' }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>RTL / Hardware</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: intake.files_summary?.rtl_files > 0 ? 'var(--blue)' : 'var(--text-secondary)', marginTop: 2 }}>
              {intake.files_summary?.rtl_files ?? (intake.rtl_count || 0)} files
            </div>
          </div>

          <div style={{ background: 'var(--bg-subtle)', padding: '10px 14px', borderRadius: 3, border: '1px solid var(--border-dim)' }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>C / C++ Software</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-bright)', marginTop: 2 }}>
              {intake.files_summary?.c_files ?? (intake.c_count || 0)} files
            </div>
          </div>

          <div style={{ background: 'var(--bg-subtle)', padding: '10px 14px', borderRadius: 3, border: '1px solid var(--border-dim)' }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Python / Scripts</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-bright)', marginTop: 2 }}>
              {intake.files_summary?.py_files ?? (intake.py_count || 0)} files
            </div>
          </div>

          <div style={{ background: 'var(--bg-subtle)', padding: '10px 14px', borderRadius: 3, border: '1px solid var(--border-dim)' }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Build System</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginTop: 4 }}>
              {intake.build_system || 'Not detected'}
            </div>
          </div>
        </div>

        {/* Small repository tailored prompt or SoC architecture briefing */}
        <div style={{ padding: '16px 18px', background: isSmall ? '#fffbeb' : '#ffffff' }}>
          {isSmall ? (
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--amber)', marginBottom: 4 }}>
                Small / Generic Directory Detected
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12 }}>
                This directory contains {intake.files_summary?.total_analyzable || 2} analyzable files and no detected RTL hardware modules. Autonomous security planning is held. What would you like to do with this directory?
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {briefing?.recommended_actions?.map(action => (
                  <button
                    key={action.id}
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: 12, padding: '5px 12px' }}
                    onClick={() => {
                      setInstruction(action.label)
                      setInterpretedAction({
                        goal: action.label,
                        method: action.method,
                        target: 'Detected files (hello.c, script.py)',
                        tool: action.id === 'run_files' ? 'Runner' : 'Semgrep',
                        parameters: { action_id: action.id },
                        suggested_task: {
                          title: `${action.label}: Small directory`,
                          agent: 'AGY',
                          tool: action.id === 'run_files' ? 'runner' : 'semgrep'
                        }
                      })
                    }}
                  >
                    [{action.label}]
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                Architecture Domains & Potential Analysis Areas:
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {briefing?.potential_analysis_areas?.map((area, idx) => (
                  <span key={idx} className="mono" style={{ fontSize: 11, background: 'var(--bg-elevated)', padding: '3px 8px', borderRadius: 2, border: '1px solid var(--border-dim)' }}>
                    • {area}
                  </span>
                )) || (
                  <span className="mono text-muted" style={{ fontSize: 12 }}>Standard SoC Verification buckets available</span>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Natural User Instruction Box (Section 11) ─────────────────────────── */}
      <div className="panel" style={{ marginBottom: 20, boxShadow: 'var(--shadow-sm)' }}>
        <div className="panel-header" style={{ padding: '12px 18px' }}>
          <span className="panel-title" style={{ fontSize: 14 }}>
            DIRECT NATURAL INSTRUCTION (ANALYST INTENT)
          </span>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Tell LLMorch what to do in plain engineering language
          </span>
        </div>

        <div className="panel-body" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', gap: 10 }}>
            <input
              type="text"
              className="form-control"
              placeholder="e.g. 'Run those files.', 'Debug script.py.', 'Find bugs in the C file.', 'Tell me how to run them.'"
              value={instruction}
              onChange={e => setInstruction(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleInterpret() }}
              style={{ fontSize: 14, padding: '8px 12px' }}
            />
            <button
              id="btn-interpret-instruction"
              className="btn btn-primary btn-md"
              onClick={handleInterpret}
              disabled={interpreting || !instruction.trim()}
              style={{ minWidth: 150, fontWeight: 600 }}
            >
              {interpreting ? 'Interpreting...' : 'Interpret Action'}
            </button>
          </div>

          {/* Structured Interpreted Action Confirmation */}
          {interpretedAction && (
            <div style={{ marginTop: 8, padding: '16px', background: 'var(--bg-subtle)', border: '1.5px solid var(--blue)', borderRadius: 4 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--blue)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  STRUCTURED INTERPRETED ACTION
                </span>
                <span className="badge badge-ready">READY FOR CONFIRMATION</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 14 }}>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Goal</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-bright)', marginTop: 2 }}>{interpretedAction.goal}</div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Method</div>
                  <div style={{ fontSize: 13, color: 'var(--text-primary)', marginTop: 2 }}>{interpretedAction.method}</div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Target</div>
                  <div className="mono" style={{ fontSize: 12, color: 'var(--text-primary)', marginTop: 2 }}>{interpretedAction.target}</div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Tool</div>
                  <div className="mono" style={{ fontSize: 12, color: 'var(--blue)', marginTop: 2 }}>{interpretedAction.tool}</div>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, borderTop: '1px solid var(--border-dim)', paddingTop: 12 }}>
                <button className="btn btn-secondary btn-sm" onClick={() => setInterpretedAction(null)}>
                  Edit Instruction
                </button>
                <button id="btn-confirm-interpreted-action" className="btn btn-success btn-sm" onClick={handleConfirmAction} style={{ fontWeight: 600, padding: '4px 14px' }}>
                  ✓ Confirm & Dispatch Task
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── "WHAT WOULD YOU LIKE TO DO?" Primary Actions Grid (Section 8) ────── */}
      <div className="panel" style={{ boxShadow: 'var(--shadow-sm)' }}>
        <div className="panel-header" style={{ padding: '12px 18px' }}>
          <span className="panel-title" style={{ fontSize: 14 }}>
            WHAT WOULD YOU LIKE TO DO?
          </span>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            Choose an engineering workflow direction
          </span>
        </div>

        <div className="panel-body" style={{ padding: '20px', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
          {/* Action 1 */}
          <div
            onClick={() => onNavigate('target-repo')}
            style={{ padding: '16px', border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer', background: '#ffffff', transition: 'box-shadow 0.1s ease' }}
            onMouseEnter={e => e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)'}
            onMouseLeave={e => e.currentTarget.style.boxShadow = 'none'}
          >
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--blue)', marginBottom: 6 }}>
              ⊙ Analyze Repository
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
              Execute deep AST extraction, dependency graphs, and hardware/software contract detection.
            </div>
          </div>

          {/* Action 2 */}
          <div
            onClick={() => onNavigate('verification-plan')}
            style={{ padding: '16px', border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer', background: '#ffffff', transition: 'box-shadow 0.1s ease' }}
            onMouseEnter={e => e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)'}
            onMouseLeave={e => e.currentTarget.style.boxShadow = 'none'}
          >
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--blue)', marginBottom: 6 }}>
              📋 Start Verification Planning
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
              Generate or review the 23-bucket SoC coverage plan, resource gates, and work packages.
            </div>
          </div>

          {/* Action 3 */}
          <div
            onClick={() => onOpenCreateTask ? onOpenCreateTask() : onNavigate('tasks')}
            style={{ padding: '16px', border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer', background: '#ffffff', transition: 'box-shadow 0.1s ease' }}
            onMouseEnter={e => e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)'}
            onMouseLeave={e => e.currentTarget.style.boxShadow = 'none'}
          >
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--blue)', marginBottom: 6 }}>
              ⚡ Create Custom Task
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
              Configure and dispatch a specific formal, dynamic, or security audit task.
            </div>
          </div>

          {/* Action 4 */}
          <div
            onClick={() => onNavigate('target-repo')}
            style={{ padding: '16px', border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer', background: '#ffffff', transition: 'box-shadow 0.1s ease' }}
            onMouseEnter={e => e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)'}
            onMouseLeave={e => e.currentTarget.style.boxShadow = 'none'}
          >
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>
              🔍 Inspect Repository Structure
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
              Browse directories, inspect RTL hierarchies, and review identified security surfaces.
            </div>
          </div>

          {/* Action 5 */}
          <div
            onClick={() => onNavigate('context-fabric')}
            style={{ padding: '16px', border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer', background: '#ffffff', transition: 'box-shadow 0.1s ease' }}
            onMouseEnter={e => e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)'}
            onMouseLeave={e => e.currentTarget.style.boxShadow = 'none'}
          >
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>
              📖 Add Reference / Requirement
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
              Attach architecture documents, TRMs, or register specs to the Context Fabric.
            </div>
          </div>

          {/* Action 6 */}
          <div
            onClick={() => onNavigate('runs')}
            style={{ padding: '16px', border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer', background: '#ffffff', transition: 'box-shadow 0.1s ease' }}
            onMouseEnter={e => e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)'}
            onMouseLeave={e => e.currentTarget.style.boxShadow = 'none'}
          >
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>
              ⏱ Open Previous Analysis
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
              Review past simulation runs, task attempt logs, and verification closure dossiers.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
