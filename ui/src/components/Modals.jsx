import React, { useState, useEffect, useCallback } from 'react';
import api from '../api';

function Mono({ children }) {
  return <span className="mono">{children}</span>;
}

export function AgentSwitchModal({ isOpen, onClose, task, agents = [], onSuccess }) {
  const [targetAgentId, setTargetAgentId] = useState('');
  const [reason, setReason] = useState('Analyst requested manual agent switch');
  const [resumeAction, setResumeAction] = useState('RESUME_FROM_CHECKPOINT');
  const [newModelId, setNewModelId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  const eligibleAgents = agents.filter(a =>
    a.agent_id !== (task?.assigned_agent_id) &&
    a.health !== 'BLOCKED' &&
    a.enabled !== false
  );

  useEffect(() => {
    if (eligibleAgents.length > 0 && !targetAgentId) {
      setTargetAgentId(eligibleAgents[0].agent_id);
    }
  }, [eligibleAgents, targetAgentId]);

  if (!isOpen || !task) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!targetAgentId) {
      setError('Please select a target replacement agent.');
      return;
    }
    setLoading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const res = await api.agentSwitch({
        task_id: task.task_id,
        new_agent_id: targetAgentId,
        reason: reason.trim() || 'Manual switch by analyst',
        resume_action: resumeAction,
        new_model_id: newModelId || null,
      });

      setSuccessMsg(`Switch successful! New run: ${res.new_run_id?.slice(0, 10)}… (Checkpoint: ${res.checkpoint_id?.slice(0, 8)}…)`);
      if (onSuccess) onSuccess(res);
      setTimeout(() => {
        onClose();
        setSuccessMsg(null);
      }, 1400);
    } catch (err) {
      setError(err.message || 'Agent switch failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <span>⇄</span> Switch Agent for Task: <Mono>{task.task_id.slice(0, 12)}…</Mono>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={onClose} disabled={loading}>✕</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {error && (
              <div style={{ padding: '10px 14px', background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '6px', color: '#f87171', fontSize: '13px' }}>
                ⚠️ {error}
              </div>
            )}
            {successMsg && (
              <div style={{ padding: '10px 14px', background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: '6px', color: '#34d399', fontSize: '13px' }}>
                ✓ {successMsg}
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Currently Assigned Agent</label>
              <div style={{ padding: '8px 12px', background: 'var(--bg-card)', borderRadius: '4px', border: '1px solid var(--border)', fontSize: '13px' }}>
                <Mono>{task.assigned_agent_id || 'unassigned'}</Mono>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Target Replacement Agent</label>
              <select
                className="form-control"
                value={targetAgentId}
                onChange={e => setTargetAgentId(e.target.value)}
                disabled={loading}
              >
                {eligibleAgents.map(a => (
                  <option key={a.agent_id} value={a.agent_id}>
                    {a.agent_id} ({a.provider}) — {a.health}
                  </option>
                ))}
              </select>
              <span className="form-hint">
                Only healthy, enabled agents matching required capabilities are eligible.
              </span>
            </div>

            <div className="form-group">
              <label className="form-label">Resume Strategy</label>
              <select
                className="form-control"
                value={resumeAction}
                onChange={e => setResumeAction(e.target.value)}
                disabled={loading}
              >
                <option value="RESUME_FROM_CHECKPOINT">RESUME_FROM_CHECKPOINT (Preserve state & artifacts)</option>
                <option value="RETRY">RETRY (Clean retry with replacement agent)</option>
                <option value="PAUSE">PAUSE (Retire run and halt for analyst review)</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Switch Reason (Auditable)</label>
              <input
                type="text"
                className="form-control"
                value={reason}
                onChange={e => setReason(e.target.value)}
                placeholder="Reason for switching..."
                disabled={loading}
                required
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={loading}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading || eligibleAgents.length === 0}>
              {loading ? 'Switching…' : 'Execute Agent Switch'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function ModelSwitchModal({ isOpen, onClose, agent, onSuccess }) {
  const [models, setModels] = useState([]);
  const [currentModelInfo, setCurrentModelInfo] = useState({ id: '', status: '' });
  const [diagnostics, setDiagnostics] = useState([]);
  const [loadingModels, setLoadingModels] = useState(true);
  const [modelFetchError, setModelFetchError] = useState(null);
  const [newModelId, setNewModelId] = useState('');
  const [reason, setReason] = useState('Analyst requested model switch');
  const [scope, setScope] = useState('CURRENT_TASK');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  const loadModels = useCallback(async () => {
    if (!agent) return;
    setLoadingModels(true);
    setModelFetchError(null);
    try {
      const res = await api.getAgentModels(agent.agent_id);
      const list = res.models || res.supported_models || (Array.isArray(res) ? res : []);
      setModels(list);
      setCurrentModelInfo({
        id: res.current_model_id || agent.current_model_id || agent.model || 'runtime-resolved',
        status: res.current_model_status || (agent.executable === false ? 'DISABLED BY POLICY' : 'REGISTERED & ACTIVE'),
      });
      if (res.diagnostics) setDiagnostics(res.diagnostics);

      if (list.length > 0) {
        const alt = list.find(m => m.model_id !== (res.current_model_id || agent.current_model_id));
        setNewModelId(alt ? alt.model_id : list[0].model_id);
      } else {
        setNewModelId('');
      }
    } catch (err) {
      setModelFetchError(err.message || 'Unable to load models from ModelRegistry');
    } finally {
      setLoadingModels(false);
    }
  }, [agent]);

  useEffect(() => {
    if (isOpen && agent) {
      loadModels();
      setSubmitError(null);
      setSuccessMsg(null);
    }
  }, [isOpen, agent, loadModels]);

  if (!isOpen || !agent) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!newModelId) {
      setSubmitError('Please select a target model.');
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    setSuccessMsg(null);

    try {
      const res = await api.switchModel({
        agent_id: agent.agent_id,
        new_model_id: newModelId,
        reason: reason.trim() || 'Manual model switch',
        scope,
      });

      setSuccessMsg(`Model successfully switched to ${res.new_model_id}!`);
      if (onSuccess) onSuccess(res);
      setTimeout(() => {
        onClose();
        setSuccessMsg(null);
      }, 1200);
    } catch (err) {
      setSubmitError(err.message || 'Model switch rejected by control plane');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={e => e.stopPropagation()} style={{ maxWidth: '580px' }}>
        <div className="modal-header">
          <div className="modal-title">
            <span>⚙</span> Switch Active Model for Agent: <Mono>{agent.agent_id}</Mono>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={onClose} disabled={submitting}>✕</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {submitError && (
              <div style={{ padding: '10px 14px', background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '6px', color: '#f87171', fontSize: '13px' }}>
                ⚠️ {submitError}
              </div>
            )}
            {successMsg && (
              <div style={{ padding: '10px 14px', background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: '6px', color: '#34d399', fontSize: '13px' }}>
                ✓ {successMsg}
              </div>
            )}

            {/* Current Active Model */}
            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <label className="form-label" style={{ marginBottom: 0 }}>Currently Active Model</label>
                <span
                  className={`badge ${currentModelInfo.status?.includes('ACTIVE') ? 'badge-success' : 'badge-paused'}`}
                  style={{ fontSize: '10px' }}
                >
                  {currentModelInfo.status || 'ACTIVE'}
                </span>
              </div>
              <div style={{ padding: '8px 12px', background: 'var(--bg-card)', borderRadius: '4px', border: '1px solid var(--border)', fontSize: '13px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Mono style={{ fontWeight: 600, color: 'var(--accent-cyan)' }}>
                  {currentModelInfo.id || 'runtime-resolved'}
                </Mono>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Agent: {agent.provider} ({agent.interface})
                </span>
              </div>
            </div>

            {/* Target Model Selector with All 5 States */}
            <div className="form-group">
              <label className="form-label">Select Compatible Target Model</label>

              {/* State 1: Loading */}
              {loadingModels && (
                <div style={{ padding: '14px', textAlign: 'center', background: 'var(--bg-card)', borderRadius: '6px', border: '1px solid var(--border)', color: 'var(--text-muted)', fontSize: '13px' }}>
                  <span className="spinner" style={{ display: 'inline-block', marginRight: '8px' }} />
                  Loading compatible models from Model Registry…
                </div>
              )}

              {/* State 2: API Error */}
              {!loadingModels && modelFetchError && (
                <div style={{ padding: '12px 14px', background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '6px' }}>
                  <div style={{ color: '#f87171', fontSize: '13px', marginBottom: '8px' }}>
                    ⚠️ Unable to load models: {modelFetchError}
                  </div>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={loadModels}>
                    ↺ Retry Loading Models
                  </button>
                </div>
              )}

              {/* State 3: No Compatible Models Available */}
              {!loadingModels && !modelFetchError && models.length === 0 && (
                <div style={{ padding: '14px', background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: '6px' }}>
                  <div style={{ color: '#fbbf24', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                    No compatible models are currently available for this agent.
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px' }}>
                    {agent.executable === false
                      ? `Agent execution is disabled: ${agent.execution_disabled_reason || 'Local execution policy.'}`
                      : 'Possible reasons: Agent capability mismatch, no enabled models configured in registry, or agent execution policy restriction.'}
                  </div>
                  {diagnostics.length > 0 && (
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '8px', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '6px' }}>
                      <div style={{ fontWeight: 600, marginBottom: '4px' }}>Registry Diagnostic Evaluation:</div>
                      {diagnostics.filter(d => !d.compatible).slice(0, 4).map(d => (
                        <div key={d.model_id}>
                          • <Mono>{d.model_id}</Mono>: {d.rejection_reason || 'Incompatible with agent'}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* State 4: Selectable Models Available */}
              {!loadingModels && !modelFetchError && models.length > 0 && (
                <div>
                  <select
                    className="form-control"
                    value={newModelId}
                    onChange={e => setNewModelId(e.target.value)}
                    disabled={submitting}
                    id="select-target-model"
                  >
                    {models.map(m => {
                      const ctxFormatted = (m.context_window || 0) >= 1000000
                        ? `${((m.context_window || 0) / 1000000).toFixed(0)}M`
                        : `${Math.round((m.context_window || 0) / 1000)}K`;
                      const caps = (m.capabilities || []).slice(0, 3).join(', ');
                      return (
                        <option key={m.model_id} value={m.model_id}>
                          {m.display_name || m.model_id} · {m.provider} ({ctxFormatted} ctx{caps ? ` · ${caps}` : ''})
                        </option>
                      );
                    })}
                  </select>

                  {/* Highlight current selection details */}
                  {(() => {
                    const sel = models.find(m => m.model_id === newModelId);
                    if (!sel) return null;
                    return (
                      <div style={{ marginTop: '6px', padding: '6px 10px', background: 'var(--bg-card)', borderRadius: '4px', fontSize: '11px', color: 'var(--text-secondary)' }}>
                        <strong>Provider:</strong> {sel.provider} · <strong>Context:</strong> {(sel.context_window || 0).toLocaleString()} tokens · <strong>Capabilities:</strong> {(sel.capabilities || []).join(', ') || 'General'}
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>

            {/* Scope */}
            <div className="form-group">
              <label className="form-label">Switch Scope</label>
              <select
                className="form-control"
                value={scope}
                onChange={e => setScope(e.target.value)}
                disabled={submitting}
              >
                <option value="CURRENT_TASK">CURRENT_TASK (Apply to active task execution)</option>
                <option value="FUTURE_TASKS">FUTURE_TASKS (Persist as default for upcoming dispatches)</option>
                <option value="ALL_TASKS">ALL_TASKS (Apply across all current and future tasks)</option>
                <option value="GLOBAL">GLOBAL (Global agent default)</option>
              </select>
            </div>

            {/* Reason */}
            <div className="form-group">
              <label className="form-label">Switch Reason</label>
              <input
                type="text"
                className="form-control"
                value={reason}
                onChange={e => setReason(e.target.value)}
                placeholder="Reason for switching model (e.g. Deep RTL reasoning required)"
                disabled={submitting}
                required
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={submitting || loadingModels || models.length === 0 || !newModelId}
              id="btn-apply-model-switch"
            >
              {submitting ? 'Switching Model…' : '✓ Apply Model Switch'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function RepoEstimateModal({ isOpen, onClose, initialRepoPath, onBudgetSet }) {
  const [repoPath, setRepoPath] = useState(initialRepoPath || '.');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [estimate, setEstimate] = useState(null);
  const [budgetLimit, setBudgetLimit] = useState(100000);
  const [budgetSuccess, setBudgetSuccess] = useState(false);

  useEffect(() => {
    if (isOpen) {
      if (initialRepoPath) {
        setRepoPath(initialRepoPath);
      } else {
        api.currentRepository().then(res => {
          if (res?.repository?.repository_path) {
            setRepoPath(res.repository.repository_path);
          }
        }).catch(() => {});
      }
      setEstimate(null);
      setError(null);
      setBudgetSuccess(false);
    }
  }, [isOpen, initialRepoPath]);

  if (!isOpen) return null;

  const handleEstimate = async () => {
    setLoading(true);
    setError(null);
    setEstimate(null);
    setBudgetSuccess(false);

    try {
      const res = await api.estimateRepository({
        repository_path: repoPath.trim() || undefined,
        repo_path: repoPath.trim() || undefined,
      });
      setEstimate(res);
      const rec = res.recommended_budget ?? res.recommended_token_budget;
      if (rec) {
        setBudgetLimit(rec);
      }
    } catch (err) {
      setError(err.message || 'Estimation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleApplyBudget = async () => {
    try {
      await api.updateBudget({
        budget_limit_tokens: parseInt(budgetLimit, 10),
        warning_threshold_pct: 0.8,
        exhaustion_threshold_pct: 0.95,
      });
      setBudgetSuccess(true);
      if (onBudgetSet) onBudgetSet(budgetLimit);
      setTimeout(() => {
        onClose();
      }, 1200);
    } catch (err) {
      setError(err.message || 'Failed to update budget');
    }
  };

  const rawTokens = estimate?.raw_token_estimate ?? estimate?.raw_token_footprint ?? 0;
  const scopedTokens = estimate?.llm_scoped_token_estimate ?? estimate?.scoped_token_footprint ?? 0;
  const totalFiles = estimate?.total_files_discovered ?? estimate?.total_files ?? 0;
  const scopedFiles = estimate?.security_relevant_files_count ?? estimate?.scoped_files ?? 0;
  const excludedSecrets = estimate?.quarantined_secrets_count ?? estimate?.excluded_secrets_count ?? 0;
  const stageBreakdowns = estimate?.breakdown_by_stage ?? estimate?.stage_breakdowns ?? [];
  const langBreakdowns = estimate?.breakdown_by_language ?? estimate?.language_breakdowns ?? [];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card modal-card-lg" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <span>📊</span> Repository Token & Cost Estimator
          </div>
          <button className="btn btn-secondary btn-sm" onClick={onClose} disabled={loading}>✕</button>
        </div>

        <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            Calculates raw repository token footprint vs LLM-scoped security tokens, protects against secrets leakage, and predicts investigation budget.
          </p>

          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="text"
              className="form-control"
              style={{ flex: 1 }}
              value={repoPath}
              onChange={e => setRepoPath(e.target.value)}
              placeholder="Target repository path (e.g. /home/user/project)"
              disabled={loading}
              id="input-estimate-path"
            />
            <button className="btn btn-primary" onClick={handleEstimate} disabled={loading} id="btn-run-estimate">
              {loading ? 'Analyzing…' : 'Estimate Tokens'}
            </button>
          </div>

          {error && (
            <div style={{ padding: '10px 14px', background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '6px', color: '#f87171', fontSize: '13px' }}>
              ⚠️ {error}
            </div>
          )}

          {budgetSuccess && (
            <div style={{ padding: '10px 14px', background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: '6px', color: '#34d399', fontSize: '13px' }}>
              ✓ Run Token Budget successfully updated to {Number(budgetLimit).toLocaleString()} tokens!
            </div>
          )}

          {estimate && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div className="stat-grid">
                <div className="stat-card">
                  <div className="stat-label">Raw Disk Footprint</div>
                  <div className="stat-value">{rawTokens.toLocaleString()}</div>
                  <div className="stat-sub">{totalFiles} total files</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">LLM-Scoped Tokens</div>
                  <div className="stat-value text-blue">{scopedTokens.toLocaleString()}</div>
                  <div className="stat-sub">{scopedFiles} security units</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Scope Reduction</div>
                  <div className="stat-value text-green">
                    {rawTokens > 0
                      ? `${Math.round((1 - scopedTokens / rawTokens) * 100)}%`
                      : '0%'}
                  </div>
                  <div className="stat-sub">noise excluded safely</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Secrets Excluded</div>
                  <div className="stat-value text-amber">{excludedSecrets}</div>
                  <div className="stat-sub">quarantine protected</div>
                </div>
              </div>

              {/* Stage breakdown */}
              {stageBreakdowns.length > 0 && (
                <div className="card">
                  <div className="card-header">
                    <div className="card-title">Investigation Stage Token Distribution</div>
                  </div>
                  <table className="data-table">
                    <thead>
                      <tr><th>Stage</th><th>Share %</th><th>Estimated Tokens</th></tr>
                    </thead>
                    <tbody>
                      {stageBreakdowns.map((st, idx) => {
                        const name = st.stage_name || st.stage || `Stage ${idx + 1}`;
                        const tokens = st.estimated_tokens || st.tokens || 0;
                        const pct = st.percentage_of_total ? Math.round(st.percentage_of_total * 100) : 0;
                        return (
                          <tr key={name}>
                            <td style={{ fontWeight: 500, textTransform: 'capitalize' }}>{name}</td>
                            <td>{pct}%</td>
                            <td><Mono>{tokens.toLocaleString()}</Mono></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Language breakdown */}
              {langBreakdowns.length > 0 && (
                <div className="card">
                  <div className="card-header">
                    <div className="card-title">Language Token Distribution</div>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {langBreakdowns.map(lb => (
                      <div key={lb.language} style={{ padding: '6px 10px', background: 'var(--bg-card)', borderRadius: '4px', border: '1px solid var(--border)', fontSize: '12px' }}>
                        <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{lb.language}</span>:{' '}
                        {(lb.scoped_tokens || lb.tokens || 0).toLocaleString()} tokens ({lb.file_count || 0} files)
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommended budget */}
              <div className="card" style={{ border: '1px solid var(--accent-blue)', background: 'rgba(59,130,246,0.05)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
                  <div>
                    <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--accent-blue)' }}>Recommended Token Budget</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                      Includes verification buffer and confidence rating ({estimate.confidence || estimate.confidence_level || 'HIGH'})
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <input
                      type="number"
                      className="form-control"
                      style={{ width: '130px' }}
                      value={budgetLimit}
                      onChange={e => setBudgetLimit(e.target.value)}
                    />
                    <button className="btn btn-primary" onClick={handleApplyBudget}>
                      Apply Budget
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
