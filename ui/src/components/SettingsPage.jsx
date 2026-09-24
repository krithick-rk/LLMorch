import React, { useState, useEffect } from 'react';
import api from '../api';

function Mono({ children }) {
  return <span className="mono">{children}</span>;
}

export function SettingsPage({ refreshSignal }) {
  const [activeTab, setActiveTab] = useState('agents');
  const [settings, setSettings] = useState(null);
  const [models, setModels] = useState([]);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  // Editable settings draft
  const [draft, setDraft] = useState({
    system: { environment: 'production', log_level: 'INFO' },
    agents: { preferred_agent: 'agent-agy-01', allowed_agents: [], agent_concurrency_limit: 2 },
    models: { selection_mode: 'POLICY', active_policy: 'balanced', fallback_enabled: true },
    scope: { include_paths: ['src/**', 'include/**'], exclude_paths: ['test/**', 'build/**', '.git/**'] },
    execution: { max_concurrent_tasks: 4, task_timeout_seconds: 600, max_retries_per_task: 3 },
    token_budgets: { default_run_budget_tokens: 150000, warning_threshold_pct: 0.8, auto_stop_on_exhaustion: true },
    security: { credentials_masked: {}, quarantine_secrets: true },
  });

  const loadSettings = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sRes, mRes, aRes] = await Promise.all([
        api.settings().catch(() => null),
        api.models().catch(() => ({ items: [] })),
        api.agents().catch(() => ({ items: [] })),
      ]);

      if (sRes) {
        setSettings(sRes);
        setDraft(prev => ({
          ...prev,
          ...sRes,
          token_budgets: sRes.token_budgets || prev.token_budgets,
        }));
      }
      setModels(mRes?.items || []);
      setAgents(aRes?.items || []);
    } catch (err) {
      setError(err.message || 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSettings();
  }, [refreshSignal]);

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const updated = await api.updateSettings(draft);
      setSettings(updated);
      setMessage('Settings successfully saved to control plane!');
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      setError(err.message || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="spinner" />;
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">⚙️ Control Plane Settings & Policy</div>
          <div className="page-subtitle">Configure elastic agents, models, token accounting, and execution scope</div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-secondary btn-sm" onClick={loadSettings} disabled={saving}>↺ Reload</button>
          <button className="btn btn-primary btn-sm" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : '💾 Save Settings'}
          </button>
        </div>
      </div>

      {message && (
        <div style={{ marginBottom: '16px', padding: '10px 14px', background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: '6px', color: '#34d399', fontSize: '13px' }}>
          ✓ {message}
        </div>
      )}

      {error && (
        <div style={{ marginBottom: '16px', padding: '10px 14px', background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '6px', color: '#f87171', fontSize: '13px' }}>
          ⚠️ {error}
        </div>
      )}

      {/* Tabs */}
      <div className="settings-tabs">
        {[
          { id: 'agents', label: '🤖 Agents', count: agents.length },
          { id: 'models', label: '🧠 Models', count: models.length },
          { id: 'budgets', label: '🪙 Token Budgets' },
          { id: 'execution', label: '⚡ Execution & Scope' },
          { id: 'security', label: '🔐 Security & Secrets' },
        ].map(tab => (
          <div
            key={tab.id}
            className={`settings-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </div>
        ))}
      </div>

      {/* Tab: Agents */}
      {activeTab === 'agents' && (
        <div className="settings-card">
          <div className="card-title mb-16">Agent Pool Management (Elastic 1–4 Agents)</div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Agent ID</th>
                <th>Provider</th>
                <th>Role</th>
                <th>Status</th>
                <th>Active Model</th>
                <th>State</th>
              </tr>
            </thead>
            <tbody>
              {agents.map(a => (
                <tr key={a.agent_id}>
                  <td><Mono>{a.agent_id}</Mono></td>
                  <td>{a.provider}</td>
                  <td>{a.role || 'general_analysis'}</td>
                  <td><span className={`badge badge-${(a.health || 'available').toLowerCase()}`}>{a.health}</span></td>
                  <td><Mono>{a.current_model_id || a.model || 'auto'}</Mono></td>
                  <td>
                    <button
                      className={`btn btn-sm ${a.enabled !== false ? 'btn-secondary' : 'btn-danger'}`}
                      onClick={async () => {
                        const newEnabled = a.enabled === false;
                        a.enabled = newEnabled;
                        setDraft(prev => ({ ...prev }));
                      }}
                    >
                      {a.enabled !== false ? 'Enabled' : 'Disabled'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab: Models */}
      {activeTab === 'models' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="settings-card">
            <div className="card-title mb-16">Model Selection Engine</div>
            <div className="settings-row">
              <div className="settings-info">
                <div className="settings-name">Selection Mode</div>
                <div className="settings-desc">Choose whether models are selected automatically, strictly manually, or via policy.</div>
              </div>
              <select
                className="form-control"
                style={{ width: '180px' }}
                value={draft.models?.selection_mode || 'POLICY'}
                onChange={e => setDraft(prev => ({
                  ...prev,
                  models: { ...prev.models, selection_mode: e.target.value }
                }))}
              >
                <option value="AUTO">AUTO (Capability match)</option>
                <option value="POLICY">POLICY (Cost/speed profile)</option>
                <option value="MANUAL">MANUAL (Analyst pinned)</option>
              </select>
            </div>

            <div className="settings-row">
              <div className="settings-info">
                <div className="settings-name">Active Policy Profile</div>
                <div className="settings-desc">Deterministic heuristic optimization policy for model routing.</div>
              </div>
              <select
                className="form-control"
                style={{ width: '220px' }}
                value={draft.models?.active_policy || 'balanced'}
                onChange={e => setDraft(prev => ({
                  ...prev,
                  models: { ...prev.models, active_policy: e.target.value }
                }))}
              >
                <option value="balanced">balanced (Recommended)</option>
                <option value="fast_cost_effective">fast_cost_effective (Low latency)</option>
                <option value="deep_security_reasoning">deep_security_reasoning (Max capability)</option>
              </select>
            </div>
          </div>

          <div className="settings-card">
            <div className="card-title mb-16">Model Registry (Capability & Context Metadata)</div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Model ID</th>
                  <th>Provider</th>
                  <th>Context Window</th>
                  <th>Cost Tier</th>
                  <th>Reasoning Score</th>
                  <th>Capabilities</th>
                </tr>
              </thead>
              <tbody>
                {models.map(m => (
                  <tr key={m.model_id}>
                    <td><Mono>{m.model_id}</Mono></td>
                    <td>{m.provider}</td>
                    <td>{(m.context_window / 1000).toFixed(0)}k</td>
                    <td>{m.cost_tier}</td>
                    <td>{(m.reasoning_score * 10).toFixed(1)}/10</td>
                    <td>
                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                        {(m.capabilities || []).map(c => (
                          <span key={c} className="cap-tag">{c}</span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab: Budgets */}
      {activeTab === 'budgets' && (
        <div className="settings-card">
          <div className="card-title mb-16">Token Budget Controls</div>

          <div className="settings-row">
            <div className="settings-info">
              <div className="settings-name">Default Run Token Limit</div>
              <div className="settings-desc">Maximum authoritative tokens an investigation run can consume.</div>
            </div>
            <input
              type="number"
              className="form-control"
              style={{ width: '180px' }}
              value={draft.token_budgets?.default_run_budget_tokens || 150000}
              onChange={e => setDraft(prev => ({
                ...prev,
                token_budgets: { ...prev.token_budgets, default_run_budget_tokens: parseInt(e.target.value, 10) }
              }))}
            />
          </div>

          <div className="settings-row">
            <div className="settings-info">
              <div className="settings-name">Warning Threshold (%)</div>
              <div className="settings-desc">Triggers LOW and NEAR_LIMIT events when token consumption reaches this percentage.</div>
            </div>
            <input
              type="number"
              step="0.05"
              min="0.1"
              max="1.0"
              className="form-control"
              style={{ width: '180px' }}
              value={draft.token_budgets?.warning_threshold_pct || 0.8}
              onChange={e => setDraft(prev => ({
                ...prev,
                token_budgets: { ...prev.token_budgets, warning_threshold_pct: parseFloat(e.target.value) }
              }))}
            />
          </div>

          <div className="settings-row">
            <div className="settings-info">
              <div className="settings-name">Auto-Stop on Quota Exhaustion</div>
              <div className="settings-desc">Immediately halts further LLM dispatch and checkpoints state when budget is exhausted.</div>
            </div>
            <input
              type="checkbox"
              style={{ width: '18px', height: '18px', accentColor: 'var(--accent-blue)' }}
              checked={draft.token_budgets?.auto_stop_on_exhaustion !== false}
              onChange={e => setDraft(prev => ({
                ...prev,
                token_budgets: { ...prev.token_budgets, auto_stop_on_exhaustion: e.target.checked }
              }))}
            />
          </div>
        </div>
      )}

      {/* Tab: Execution & Scope */}
      {activeTab === 'execution' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="settings-card">
            <div className="card-title mb-16">Execution Policies</div>
            <div className="settings-row">
              <div className="settings-info">
                <div className="settings-name">Max Concurrent Tasks</div>
                <div className="settings-desc">Parallel investigation tasks scheduled across the active agent pool.</div>
              </div>
              <input
                type="number"
                min="1"
                max="8"
                className="form-control"
                style={{ width: '120px' }}
                value={draft.execution?.max_concurrent_tasks || 4}
                onChange={e => setDraft(prev => ({
                  ...prev,
                  execution: { ...prev.execution, max_concurrent_tasks: parseInt(e.target.value, 10) }
                }))}
              />
            </div>

            <div className="settings-row">
              <div className="settings-info">
                <div className="settings-name">Max Retries Per Task</div>
                <div className="settings-desc">Failover recovery attempts before marking a task as permanently failed.</div>
              </div>
              <input
                type="number"
                min="0"
                max="5"
                className="form-control"
                style={{ width: '120px' }}
                value={draft.execution?.max_retries_per_task || 3}
                onChange={e => setDraft(prev => ({
                  ...prev,
                  execution: { ...prev.execution, max_retries_per_task: parseInt(e.target.value, 10) }
                }))}
              />
            </div>
          </div>

          <div className="settings-card">
            <div className="card-title mb-16">Investigation Scope Patterns</div>
            <div className="form-group mb-12">
              <label className="form-label">Include Path Patterns (comma-separated)</label>
              <input
                type="text"
                className="form-control"
                value={(draft.scope?.include_paths || []).join(', ')}
                onChange={e => setDraft(prev => ({
                  ...prev,
                  scope: { ...prev.scope, include_paths: e.target.value.split(',').map(s => s.trim()).filter(Boolean) }
                }))}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Exclude Path Patterns (comma-separated)</label>
              <input
                type="text"
                className="form-control"
                value={(draft.scope?.exclude_paths || []).join(', ')}
                onChange={e => setDraft(prev => ({
                  ...prev,
                  scope: { ...prev.scope, exclude_paths: e.target.value.split(',').map(s => s.trim()).filter(Boolean) }
                }))}
              />
            </div>
          </div>
        </div>
      )}

      {/* Tab: Security */}
      {activeTab === 'security' && (
        <div className="settings-card">
          <div className="card-title mb-16">Security & Provider Credentials</div>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
            Credential values are safely masked on the server. Cleartext secrets are never transmitted to the browser or stored in client memory.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {[
              { provider: 'antigravity', label: 'Google Antigravity (AGY)', key: 'ANTIGRAVITY_API_KEY', status: 'CONNECTED' },
              { provider: 'anthropic', label: 'Anthropic Claude Code', key: 'ANTHROPIC_API_KEY', status: 'CONNECTED' },
              { provider: 'openai', label: 'OpenAI Codex CLI', key: 'OPENAI_API_KEY', status: 'CONNECTED' },
            ].map(p => (
              <div key={p.provider} className="settings-row">
                <div className="settings-info">
                  <div className="settings-name">{p.label}</div>
                  <div className="settings-desc">Environment Key: <Mono>{p.key}</Mono></div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>••••••••••••••••</span>
                  <span className={`badge badge-${p.status.toLowerCase()}`}>{p.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
