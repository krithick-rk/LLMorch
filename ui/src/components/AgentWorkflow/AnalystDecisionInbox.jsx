import { useState, useEffect } from 'react'
import api from '../../api'
import { fmt, shortId, Btn, Spinner } from '../shared'

/**
 * AnalystDecisionInbox.jsx — Phase 9.5
 * Located at the BOTTOM of the investigation workflow.
 * Renders Human-in-the-loop decisions, agent pause requests, and stall protection notices.
 */
export function AnalystDecisionInbox({ runId, refreshSignal, onDecisionHandled }) {
  const [questions, setQuestions] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedAnswers, setSelectedAnswers] = useState({})
  const [customAnswers, setCustomAnswers] = useState({})
  const [submittingId, setSubmittingId] = useState(null)
  const [error, setError] = useState(null)

  const loadQuestions = async () => {
    try {
      const res = await api.questions({ status: 'QUESTION_PENDING', limit: 20 })
      const list = Array.isArray(res) ? res : (res.items || [])
      setQuestions(list)
    } catch (err) {
      console.error('Failed to load analyst questions:', err)
    }
  }

  useEffect(() => {
    loadQuestions()
  }, [runId, refreshSignal])

  const handleSelectOption = (questionId, optionId) => {
    setSelectedAnswers(prev => ({ ...prev, [questionId]: optionId }))
  }

  const handleCustomAnswerChange = (questionId, text) => {
    setCustomAnswers(prev => ({ ...prev, [questionId]: text }))
  }

  const handleAnswer = async (q) => {
    setSubmittingId(q.question_id)
    setError(null)
    try {
      const selectedOptId = selectedAnswers[q.question_id] || q.default_option || (q.options?.[0]?.option_id)
      const customText = customAnswers[q.question_id]
      
      const payload = {
        selected_option_id: selectedOptId,
        custom_response: customText,
      }
      
      await api.answerQuestion(q.question_id, payload)
      await loadQuestions()
      if (onDecisionHandled) onDecisionHandled(q.question_id)
    } catch (err) {
      setError(err.message || 'Failed to submit decision')
    } finally {
      setSubmittingId(null)
    }
  }

  const handleDismiss = async (q) => {
    setSubmittingId(q.question_id)
    try {
      await api.dismissQuestion(q.question_id, { reason: 'Dismissed by analyst' })
      await loadQuestions()
      if (onDecisionHandled) onDecisionHandled(q.question_id)
    } catch (err) {
      setError(err.message || 'Failed to dismiss question')
    } finally {
      setSubmittingId(null)
    }
  }

  if (questions.length === 0) {
    return (
      <div style={{
        padding: '12px 16px',
        background: 'var(--bg-panel)',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '14px' }}>🛡️</span>
          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
            HUMAN-IN-THE-LOOP DECISION INBOX
          </span>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>— 0 pending decisions. Autonomous investigation proceeding.</span>
        </div>
        <div style={{ fontSize: '11px', color: '#22c55e', display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
          AUTONOMOUS
        </div>
      </div>
    )
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '10px',
      background: 'var(--bg-panel)',
      border: '1.5px solid var(--accent-orange, #f59e0b)',
      borderRadius: '8px',
      padding: '14px 16px',
      boxShadow: '0 4px 12px rgba(245, 158, 11, 0.1)',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '16px' }}>⚠️</span>
          <span style={{ fontSize: '13px', fontWeight: 700, color: '#f59e0b' }}>
            ANALYST DECISIONS REQUIRED ({questions.length} Pending)
          </span>
        </div>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
          Execution paused on affected tasks waiting for analyst guidance
        </span>
      </div>

      {error && (
        <div style={{ fontSize: '11px', color: 'var(--red)', background: 'rgba(239, 68, 68, 0.1)', padding: '6px 10px', borderRadius: '4px' }}>
          ⚠ {error}
        </div>
      )}

      {/* Questions list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {questions.map(q => {
          const selectedOptId = selectedAnswers[q.question_id] || q.default_option || q.options?.[0]?.option_id
          const isSubmitting = submittingId === q.question_id

          return (
            <div
              key={q.question_id}
              style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                borderRadius: '6px',
                padding: '12px 14px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '2px' }}>
                    🤖 {q.agent_id ? `${q.agent_id}` : 'Orchestrator'} {q.reason ? `• Reason: ${q.reason}` : ''}
                  </div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {q.question}
                  </div>
                </div>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {q.created_at ? new Date(q.created_at).toLocaleTimeString() : ''}
                </span>
              </div>

              {/* Options */}
              {q.options && q.options.length > 0 && (
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '4px' }}>
                  {q.options.map(opt => (
                    <button
                      key={opt.option_id}
                      onClick={() => handleSelectOption(q.question_id, opt.option_id)}
                      style={{
                        padding: '6px 12px',
                        borderRadius: '5px',
                        fontSize: '11px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        background: selectedOptId === opt.option_id ? 'var(--accent-blue, #2563eb)' : 'var(--bg-base)',
                        color: selectedOptId === opt.option_id ? '#fff' : 'var(--text-secondary)',
                        border: selectedOptId === opt.option_id ? '1px solid var(--accent-blue, #2563eb)' : '1px solid var(--border)',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              )}

              {/* Custom Response input */}
              <div style={{ display: 'flex', gap: '8px', marginTop: '4px', alignItems: 'center' }}>
                <input
                  type="text"
                  placeholder="Or provide specific analyst guidance / instruction..."
                  value={customAnswers[q.question_id] || ''}
                  onChange={(e) => handleCustomAnswerChange(q.question_id, e.target.value)}
                  style={{
                    flex: 1,
                    padding: '6px 10px',
                    borderRadius: '4px',
                    border: '1px solid var(--border)',
                    background: 'var(--bg-base)',
                    color: 'var(--text-primary)',
                    fontSize: '11px',
                  }}
                />
                <button
                  disabled={isSubmitting}
                  onClick={() => handleAnswer(q)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: '4px',
                    background: '#22c55e',
                    color: '#fff',
                    border: 'none',
                    fontSize: '11px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  {isSubmitting ? 'Submitting…' : '✓ Submit Decision'}
                </button>
                <button
                  disabled={isSubmitting}
                  onClick={() => handleDismiss(q)}
                  style={{
                    padding: '6px 10px',
                    borderRadius: '4px',
                    background: 'transparent',
                    color: 'var(--text-muted)',
                    border: '1px solid var(--border)',
                    fontSize: '11px',
                    cursor: 'pointer',
                  }}
                >
                  Dismiss
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
