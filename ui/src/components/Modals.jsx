import React, { useState, useEffect } from 'react';
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
  const [newModelId, setNewModelId] = useState('');
  const [reason, setReason] = useState('Analyst requested model switch');
  const [scope, setScope] = useState('CURRENT_TASK');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  useEffect(() => {
    if (isOpen && agent) {
      api.agentModels(agent.agent_id).then(res => {
        const supported = res.supported_models || [];
        setModels(supported);
        if (supported.length > 0) {
          const alt = supported.find(m => m.model_id !== agent.current_model_id);
          setNewModelId(alt ? alt.model_id : supported[0].model_id);
        }
      }).catch(() => {
        api.models().then(res => {
          setModels(res.items || []);
          if ((res.items || []).length > 0) setNewModelId(res.items[0].model_id);
        });
      });
    }
  }, [isOpen, agent]);

  if (!isOpen || !agent) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!newModelId) {
      setError('Please select a target model.');
      return;
    }
    setLoading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const res = await api.modelSwitch({
        agent_id: agent.agent_id,
        new_model_id: newModelId,
        reason: reason.trim() || 'Manual model switch',
        scope,
      });

      setSuccessMsg(`Model switched to ${res.new_model_id}!`);
      if (onSuccess) onSuccess(res);
      setTimeout(() => {
        onClose();
        setSuccessMsg(null);
      }, 1200);
    } catch (err) {
      setError(err.message || 'Model switch failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <span>⚙</span> Switch Active Model for Agent: <Mono>{agent.agent_id}</Mono>
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
              <label className="form-label">Currently Active Model</label>
              <div style={{ padding: '8px 12px', background: 'var(--bg-card)', borderRadius: '4px', border: '1px solid var(--border)', fontSize: '13px' }}>
                <Mono>{agent.current_model_id || agent.model || 'runtime-resolved'}</Mono>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Select Compatible Target Model</label>
              <select
                className="form-control"
                value={newModelId}
                onChange={e => setNewModelId(e.target.value)}
                disabled={loading}
              >
                {models.map(m => (
                  <option key={m.model_id} value={m.model_id}>
                    {m.model_name || m.model_id} ({m.provider}) · {((m.context_window || 0) / 1000).toFixed(0)}k ctx · {m.cost_tier}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Switch Scope</label>
              <select
                className="form-control"
                value={scope}
                onChange={e => setScope(e.target.value)}
                disabled={loading}
              >
                <option value="CURRENT_TASK">CURRENT_TASK (Apply to active task execution)</option>
                <option value="FUTURE_TASKS">FUTURE_TASKS (Persist as default for upcoming dispatches)</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Switch Reason</label>
              <input
                type="text"
                className="form-control"
                value={reason}
                onChange={e => setReason(e.target.value)}
                placeholder="Reason for switching model..."
                disabled={loading}
                required
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={loading}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading || models.length === 0}>
              {loading ? 'Switching…' : 'Apply Model'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function RepoEstimateModal({ isOpen, onClose, onBudgetSet }) {
  const [repoPath, setRepoPath] = useState('.');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [estimate, setEstimate] = useState(null);
  const [budgetLimit, setBudgetLimit] = useState(100000);
  const [budgetSuccess, setBudgetSuccess] = useState(false);

  if (!isOpen) return null;

  const handleEstimate = async () => {
    setLoading(true);
    setError(null);
    setEstimate(null);
    setBudgetSuccess(false);

    try {
      const res = await api.estimateRepository({ repo_path: repoPath.trim() || '.' });
      setEstimate(res);
      if (res.recommended_token_budget) {
        setBudgetLimit(res.recommended_token_budget);
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

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card modal-card-lg" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <span>📊</span> Repository Token & Cost Estimator
          </div>
          <button className="btn btn-secondary btn-sm" onClick={onClose} disabled={loading}>✕</button>
        </div>

        <div className="modal-body">
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            Calculates raw disk tokens vs LLM-scoped tokens, excludes secrets quarantine, and predicts stage distribution prior to investigation dispatch.
          </p>

          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="text"
              className="form-control"
              style={{ flex: 1 }}
              value={repoPath}
              onChange={e => setRepoPath(e.target.value)}
              placeholder="Repository path (e.g. . or /path/to/repo)"
              disabled={loading}
            />
            <button className="btn btn-primary" onClick={handleEstimate} disabled={loading}>
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
                  <div className="stat-value">{estimate.raw_token_footprint?.toLocaleString()}</div>
                  <div className="stat-sub">{estimate.total_files} total files</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">LLM-Scoped Tokens</div>
                  <div className="stat-value text-blue">{estimate.scoped_token_footprint?.toLocaleString()}</div>
                  <div className="stat-sub">{estimate.scoped_files} security units</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Scope Reduction</div>
                  <div className="stat-value text-green">
                    {estimate.raw_token_footprint > 0
                      ? `${Math.round((1 - estimate.scoped_token_footprint / estimate.raw_token_footprint) * 100)}%`
                      : '0%'}
                  </div>
                  <div className="stat-sub">irrelevant files skipped</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Secrets Excluded</div>
                  <div className="stat-value text-amber">{estimate.excluded_secrets_count}</div>
                  <div className="stat-sub">quarantine protected</div>
                </div>
              </div>

              {/* Stage breakdown */}
              <div className="card">
                <div className="card-header">
                  <div className="card-title">Investigation Stage Token Distribution</div>
                </div>
                <table className="data-table">
                  <thead>
                    <tr><th>Stage</th><th>Share %</th><th>Estimated Tokens</th></tr>
                  </thead>
                  <tbody>
                    {(estimate.stage_breakdowns || []).map(st => (
                      <tr key={st.stage_name}>
                        <td style={{ fontWeight: 500, textTransform: 'capitalize' }}>{st.stage_name}</td>
                        <td>{Math.round(st.percentage_of_total * 100)}%</td>
                        <td><Mono>{st.estimated_tokens?.toLocaleString()}</Mono></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Language breakdown */}
              {(estimate.language_breakdowns || []).length > 0 && (
                <div className="card">
                  <div className="card-header">
                    <div className="card-title">Language Token Distribution</div>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {estimate.language_breakdowns.map(lb => (
                      <div key={lb.language} style={{ padding: '6px 10px', background: 'var(--bg-card)', borderRadius: '4px', border: '1px solid var(--border)', fontSize: '12px' }}>
                        <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{lb.language}</span>: {lb.scoped_tokens?.toLocaleString()} tokens ({lb.file_count} files)
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommended budget */}
              <div className="card" style={{ border: '1px solid var(--accent-blue)', background: 'rgba(59,130,246,0.05)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--accent-blue)' }}>Recommended Token Budget</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                      Includes 30% verification reserve and confidence rating ({estimate.confidence_level})
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
