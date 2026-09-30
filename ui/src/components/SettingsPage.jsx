/**
 * SettingsPage.jsx — Professional SoC / EDA Configuration Workspace
 * Sections 26 & 27:
 * - Left-side settings navigation categories:
 *   PROJECT (Project Defaults, Analysis Defaults, Scope)
 *   AGENTS (Agents, Models)
 *   TOOLS (Tools, Tool Policies)
 *   EXECUTION (Budgets, Timeouts, Retry)
 *   APPLICATION (Appearance, Layout)
 *   SECURITY (Safety, Sandbox)
 * - Explicit scope switcher at top: [GLOBAL SETTINGS] vs [CURRENT PROJECT]
 * - Structured forms with labels, helper text, dropdowns, toggles, numeric inputs, and save state
 */

import React, { useState, useEffect } from 'react';
import api from '../api';

export function SettingsPage({ refreshSignal, activeProject }) {
  const [scopeMode, setScopeMode] = useState('project'); // 'global' | 'project'
  const [activeSection, setActiveSection] = useState('project-defaults');
  const [settings, setSettings] = useState(null);
  const [models, setModels] = useState([]);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [loggingConfig, setLoggingConfig] = useState(null);
  const [cleaningLogs, setCleaningLogs] = useState(false);
  const [cleanupResult, setCleanupResult] = useState(null);
  const [agentUpdating, setAgentUpdating] = useState(null);
  const [projectPrefs, setProjectPrefs] = useState([]);

  // Form draft state
  const [draft, setDraft] = useState({
    project: {
      default_agent: 'agent-agy-01',
      default_method: 'Firmware Security Analysis',
      analysis_mode: 'STANDARD',
      target_directory: activeProject?.target_directory || '/home/hackdac/Documents/Benchmark/caliptra-vuln-known/runtime',
      isolated_scope: true,
      include_extensions: ['.rs', '.c', '.h', '.sv', '.v', 'Cargo.toml'],
      exclude_patterns: ['target/**', 'build/**', '.git/**', 'node_modules/**'],
      auto_expand_parent: false
    },
    agents: {
      preferred_agent: 'agent-agy-01',
      allowed_executors: ['AGY', 'Codex'],
      claude_disabled_policy: true,
      max_concurrent_agents: 4,
    },
    models: {
      selection_policy: 'CAPABILITY_BALANCED',
      fallback_enabled: true,
      reasoning_effort: 'medium'
    },
    tools: {
      enabled_tools: ['rust_source_inspector', 'cargo_audit', 'yosys', 'verilator', 'sby'],
      deterministic_only: true,
      strict_sandboxing: true
    },
    execution: {
      task_timeout_seconds: 600,
      max_retries_per_task: 3,
      max_concurrent_tasks: 4,
      default_run_budget_tokens: 180000,
      token_cap: 2000000,
      auto_stop_on_exhaustion: true,
      pause_on_anomalies: true
    },
    application: {
      theme: 'dark-engineering',
      font_family: 'JetBrains Mono / Inter',
      dense_mode: true,
      independent_split_scrolling: true,
      show_line_numbers: true
    },
    security: {
      strict_project_isolation: true,
      quarantine_secrets: true,
      mask_credentials: true,
      require_analyst_signoff: false
    }
  });

  const loadSettings = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sRes, mRes, aRes, logRes] = await Promise.all([
        api.settings().catch(() => null),
        api.models().catch(() => ({ items: [] })),
        api.agents().catch(() => ({ items: [] })),
        api.getLoggingConfig().catch(() => null),
      ]);

      if (sRes) {
        setSettings(sRes);
      }
      setModels(mRes?.items || []);
      setAgents(aRes?.items || []);
      if (logRes) setLoggingConfig(logRes);

      if (activeProject?.project_id) {
        const prefRes = await api.getAgentPreferences(activeProject.project_id).catch(() => ({ preferences: [] }));
        setProjectPrefs(prefRes?.preferences || []);
      }
    } catch (err) {
      setError(err.message || 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleAgent = async (agentId, targetEnabled) => {
    setAgentUpdating(agentId);
    setError(null);
    try {
      if (targetEnabled) {
        await api.enableAgent(agentId);
      } else {
        await api.disableAgent(agentId);
      }
      setAgents(prev => prev.map(a => a.agent_id === agentId ? { ...a, enabled: targetEnabled, availability: targetEnabled ? 'ENABLED' : 'DISABLED' } : a));
      setMessage(`Agent ${agentId} ${targetEnabled ? 'ENABLED' : 'DISABLED'}. Scheduler routing updated.`);
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      setError(err.message || 'Failed to update agent status');
    } finally {
      setAgentUpdating(null);
    }
  };

  const handleRunCleanup = async () => {
    setCleaningLogs(true);
    setCleanupResult(null);
    setError(null);
    try {
      const res = await api.runLogCleanup();
      setCleanupResult(res);
      const updatedConfig = await api.getLoggingConfig().catch(() => null);
      if (updatedConfig) setLoggingConfig(updatedConfig);
      setMessage(`Log cleanup succeeded: freed ${(res.bytes_freed / 1024).toFixed(1)} KB across ${res.files_removed} files.`);
      setTimeout(() => setMessage(null), 4000);
    } catch (err) {
      setError(err.message || 'Log cleanup failed');
    } finally {
      setCleaningLogs(false);
    }
  };

  const handleSaveProjectPref = async (agentId, isAllowed, isPreferred) => {
    if (!activeProject?.project_id) return;
    try {
      await api.saveAgentPreferences({
        project_id: activeProject.project_id,
        agent_id: agentId,
        is_allowed: isAllowed,
        is_preferred: isPreferred,
        role_preference: 'VERIFICATION',
        execution_preference: 'STANDARD',
      });
      const prefRes = await api.getAgentPreferences(activeProject.project_id).catch(() => ({ preferences: [] }));
      setProjectPrefs(prefRes?.preferences || []);
      setMessage(`Saved preference for ${agentId} on ${activeProject.name || activeProject.project_id}`);
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      setError(err.message || 'Failed to save project preferences');
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
      await api.updateSettings(draft);
      setMessage(`Settings successfully committed for ${scopeMode === 'global' ? 'GLOBAL scope' : (activeProject?.name || 'Current Project')}!`);
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      setError(err.message || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const navCategories = [
    {
      group: 'PROJECT',
      items: [
        { id: 'project-defaults', label: 'Project Defaults' },
        { id: 'analysis-defaults', label: 'Analysis Defaults' },
        { id: 'project-scope', label: 'Scope Policies' },
      ]
    },
    {
      group: 'AGENTS',
      items: [
        { id: 'agents-config', label: 'Agents' },
        { id: 'models-config', label: 'Models' },
      ]
    },
    {
      group: 'TOOLS',
      items: [
        { id: 'tools-config', label: 'Tools' },
        { id: 'tool-policies', label: 'Tool Policies' },
      ]
    },
    {
      group: 'EXECUTION',
      items: [
        { id: 'execution-budgets', label: 'Budgets' },
        { id: 'execution-timeouts', label: 'Timeouts' },
        { id: 'execution-retry', label: 'Retry' },
      ]
    },
    {
      group: 'APPLICATION',
      items: [
        { id: 'app-appearance', label: 'Appearance' },
        { id: 'app-layout', label: 'Layout' },
      ]
    },
    {
      group: 'SECURITY',
      items: [
        { id: 'security-safety', label: 'Safety' },
        { id: 'security-sandbox', label: 'Sandbox' },
      ]
    },
    {
      group: 'LOGGING',
      items: [
        { id: 'dev-logging', label: 'Development Logging' },
      ]
    },
  ];

  if (loading) return <div className="spinner" />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, height: '100%', overflow: 'hidden', background: 'var(--bg-base)' }}>
      {/* ── Top Header & Scope Selector (Section 27) ─────────────────────────── */}
      <div style={{ padding: '16px 24px', background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-bright)' }}>
              Configuration & Settings Workspace
            </span>
            <div style={{ display: 'inline-flex', background: 'var(--bg-subtle)', padding: 2, borderRadius: 4, border: '1px solid var(--border-dim)' }}>
              <button
                type="button"
                className={`btn btn-sm ${scopeMode === 'project' ? 'btn-primary' : 'btn-ghost'}`}
                style={{ fontSize: 11, padding: '3px 12px', fontWeight: 600 }}
                onClick={() => setScopeMode('project')}
              >
                CURRENT PROJECT: {activeProject?.name || 'Caliptra Runtime'}
              </button>
              <button
                type="button"
                className={`btn btn-sm ${scopeMode === 'global' ? 'btn-primary' : 'btn-ghost'}`}
                style={{ fontSize: 11, padding: '3px 12px', fontWeight: 600 }}
                onClick={() => setScopeMode('global')}
              >
                GLOBAL SETTINGS
              </button>
            </div>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
            {scopeMode === 'project' ? (
              <span>Scoped exclusively to <strong style={{ color: 'var(--blue)' }}>{activeProject?.name || activeProject?.project_id}</strong>. Target isolation strictly maintained.</span>
            ) : (
              <span>System-wide global defaults across all SoC verification workstations.</span>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary btn-sm" onClick={loadSettings} disabled={saving}>↺ Reload</button>
          <button id="btn-save-settings" className="btn btn-primary btn-sm" onClick={handleSave} disabled={saving} style={{ fontWeight: 700 }}>
            {saving ? 'Saving...' : '💾 Save Settings'}
          </button>
        </div>
      </div>

      {message && (
        <div style={{ padding: '8px 24px', background: 'var(--green-bg)', borderBottom: '1px solid var(--green-border)', color: 'var(--green)', fontSize: 12, fontFamily: 'var(--font-mono)' }}>
          ✓ {message}
        </div>
      )}

      {error && (
        <div style={{ padding: '8px 24px', background: '#fef2f2', borderBottom: '1px solid #f87171', color: '#991b1b', fontSize: 12 }}>
          ⚠️ {error}
        </div>
      )}

      {/* ── Left-Rail Navigation + Form Workspace (Section 26) ────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', flex: 1, minHeight: 0, overflow: 'hidden' }}>
        
        {/* Left-side Navigation Rail */}
        <div style={{ background: 'var(--bg-surface)', borderRight: '1px solid var(--border)', overflowY: 'auto', padding: '14px 10px' }}>
          {navCategories.map(cat => (
            <div key={cat.group} style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', padding: '4px 10px' }}>
                {cat.group}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginTop: 2 }}>
                {cat.items.map(item => {
                  const isActive = activeSection === item.id;
                  return (
                    <div
                      key={item.id}
                      id={`settings-tab-${item.id}`}
                      onClick={() => setActiveSection(item.id)}
                      style={{
                        padding: '6px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 12,
                        background: isActive ? 'var(--bg-elevated)' : 'transparent',
                        color: isActive ? 'var(--blue)' : 'var(--text-primary)',
                        fontWeight: isActive ? 600 : 400,
                        borderLeft: isActive ? '3px solid var(--blue)' : '3px solid transparent'
                      }}
                    >
                      {item.label}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Main Content Area: Structured Forms (Section 26) */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px 32px', background: 'var(--bg-base)' }}>

          {/* PROJECT DEFAULTS */}
          {activeSection === 'project-defaults' && (
            <div className="panel" style={{ maxWidth: 740 }}>
              <div className="panel-header" style={{ padding: '12px 18px', background: 'var(--bg-subtle)' }}>
                <span className="panel-title">Project Defaults & Scope Binding</span>
              </div>
              <div className="panel-body" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Target Repository Directory</label>
                  <input
                    type="text"
                    className="form-control mono"
                    value={draft.project.target_directory}
                    disabled
                    style={{ fontSize: 12, background: 'var(--bg-subtle)' }}
                  />
                  <div className="text-muted" style={{ fontSize: 11, marginTop: 4 }}>
                    One Project = One Target Scope invariant. Directory cannot be mutated after creation.
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Default Agent Executor</label>
                  <select
                    className="form-control"
                    value={draft.project.default_agent}
                    onChange={e => setDraft(prev => ({ ...prev, project: { ...prev.project, default_agent: e.target.value } }))}
                  >
                    <option value="agent-agy-01">Antigravity (AGY) — Local Real Subprocess (Default)</option>
                    <option value="agent-codex-01">OpenAI Codex — Real API Execution</option>
                  </select>
                  <div className="text-muted" style={{ fontSize: 11, marginTop: 4 }}>
                    Primary agent allocated for synthesis, file-bound analysis, and code exploration.
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Default Verification Method</label>
                  <select
                    className="form-control"
                    value={draft.project.default_method}
                    onChange={e => setDraft(prev => ({ ...prev, project: { ...prev.project, default_method: e.target.value } }))}
                  >
                    <option value="Firmware Security Analysis">Firmware Security Analysis</option>
                    <option value="Formal Register Verification">Formal Register Verification</option>
                    <option value="Protocol Boundary Check">Protocol Boundary Check</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* ANALYSIS DEFAULTS */}
          {activeSection === 'analysis-defaults' && (
            <div className="panel" style={{ maxWidth: 740 }}>
              <div className="panel-header" style={{ padding: '12px 18px', background: 'var(--bg-subtle)' }}>
                <span className="panel-title">Initial Analysis & Scope Policies</span>
              </div>
              <div className="panel-body" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Analysis Mode</label>
                  <select
                    className="form-control"
                    value={draft.project.analysis_mode}
                    onChange={e => setDraft(prev => ({ ...prev, project: { ...prev.project, analysis_mode: e.target.value } }))}
                  >
                    <option value="QUICK">Quick (Deterministic Scan & AST pre-check)</option>
                    <option value="STANDARD">Standard (Full 23-Bucket Mapping & WorkPackage Plan)</option>
                    <option value="DEEP">Deep (Exhaustive Formal Solvers & Boundary Model Checking)</option>
                  </select>
                  <div className="text-muted" style={{ fontSize: 11, marginTop: 4 }}>
                    Controls the depth of initial security surface extraction and WorkPackage synthesis.
                  </div>
                </div>

                <div className="form-group">
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={draft.project.isolated_scope}
                      onChange={e => setDraft(prev => ({ ...prev, project: { ...prev.project, isolated_scope: e.target.checked } }))}
                    />
                    <span style={{ fontSize: 13, fontWeight: 600 }}>Strict Subdirectory Isolation</span>
                  </label>
                  <div className="text-muted" style={{ fontSize: 11, marginLeft: 24, marginTop: 2 }}>
                    Defer parent repository hardware models until cross-component validation is explicitly requested.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* SCOPE POLICIES */}
          {activeSection === 'project-scope' && (
            <div className="panel" style={{ maxWidth: 740 }}>
              <div className="panel-header" style={{ padding: '12px 18px', background: 'var(--bg-subtle)' }}>
                <span className="panel-title">File Discovery & Scope Inclusion Rules</span>
              </div>
              <div className="panel-body" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Included Extensions (Analyzable Files)</label>
                  <input
                    type="text"
                    className="form-control mono"
                    value={draft.project.include_extensions.join(', ')}
                    onChange={e => setDraft(prev => ({ ...prev, project: { ...prev.project, include_extensions: e.target.value.split(',').map(s => s.trim()) } }))}
                  />
                  <div className="text-muted" style={{ fontSize: 11, marginTop: 4 }}>
                    Files matching these patterns will be included in the Current Analysis Scope.
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Excluded Patterns (Deferred / Filtered)</label>
                  <input
                    type="text"
                    className="form-control mono"
                    value={draft.project.exclude_patterns.join(', ')}
                    onChange={e => setDraft(prev => ({ ...prev, project: { ...prev.project, exclude_patterns: e.target.value.split(',').map(s => s.trim()) } }))}
                  />
                  <div className="text-muted" style={{ fontSize: 11, marginTop: 4 }}>
                    Files matching these glob patterns will be logged with explicit deferral reasons.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* AGENTS CONFIG */}
          {activeSection === 'agents-config' && (
            <div className="panel" style={{ maxWidth: 840 }}>
              <div className="panel-header" style={{ padding: '12px 18px', background: 'var(--bg-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="panel-title">Agent Registry & Execution Control</span>
                <span className="badge badge-info" style={{ fontSize: 11 }}>SCHEDULER LINKED</span>
              </div>
              <div className="panel-body" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div style={{ background: 'var(--bg-subtle)', padding: 12, borderRadius: 4, border: '1px solid var(--border)', fontSize: 12 }}>
                  <div style={{ fontWeight: 700, color: 'var(--green)', marginBottom: 4 }}>✓ Active Enterprise Policy: Real Subprocesses Enabled</div>
                  <div>AGY and Codex are authorized for file-bound task execution. Claude invocation is permanently disabled (0 invocations). Disabling an agent directly updates the scheduler: tasks waiting for disabled agents enter <code className="mono">WAITING_FOR_AGENT</code> without failing.</div>
                </div>

                {/* Agents Management Table */}
                <div style={{ border: '1px solid var(--border)', borderRadius: 4, overflow: 'hidden' }}>
                  <table className="table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead>
                      <tr style={{ background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border)', textAlign: 'left' }}>
                        <th style={{ padding: '8px 12px' }}>Agent ID</th>
                        <th style={{ padding: '8px 12px' }}>Display Name</th>
                        <th style={{ padding: '8px 12px' }}>Provider</th>
                        <th style={{ padding: '8px 12px' }}>CLI Executable</th>
                        <th style={{ padding: '8px 12px' }}>Version</th>
                        <th style={{ padding: '8px 12px' }}>Availability</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right' }}>Control</th>
                      </tr>
                    </thead>
                    <tbody>
                      {agents.map(ag => {
                        const isClaude = ag.agent_id === 'agent-claude-01' || (ag.name && ag.name.toLowerCase().includes('claude'));
                        const isEnabled = !isClaude && ag.enabled !== false && ag.is_enabled !== false;
                        const isUpdating = agentUpdating === ag.agent_id;

                        let statusBadge = <span className="badge badge-ready">Enabled + Ready</span>;
                        if (isClaude) {
                          statusBadge = <span className="badge badge-failed" title="Enterprise policy prohibits Claude execution">Blocked by policy</span>;
                        } else if (!isEnabled) {
                          statusBadge = <span className="badge badge-stopped">Disabled</span>;
                        }

                        return (
                          <tr key={ag.agent_id} style={{ borderBottom: '1px solid var(--border-dim)' }}>
                            <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                              {ag.agent_id}
                            </td>
                            <td style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--text-bright)' }}>
                              {ag.display_name || ag.name || ag.agent_id}
                            </td>
                            <td style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>
                              {ag.provider || 'local'}
                            </td>
                            <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                              {ag.cli_executable || (ag.agent_id.includes('agy') ? 'agy' : (ag.agent_id.includes('codex') ? 'codex' : 'claude'))}
                            </td>
                            <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                              {ag.version || 'v2.4.0'}
                            </td>
                            <td style={{ padding: '8px 12px' }}>
                              {statusBadge}
                            </td>
                            <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                              {isClaude ? (
                                <button className="btn btn-secondary btn-sm" disabled title="Claude invocation permanently disabled (0 invocations policy)" style={{ opacity: 0.5 }}>
                                  Policy Locked
                                </button>
                              ) : isEnabled ? (
                                <button
                                  id={`btn-disable-${ag.agent_id}`}
                                  className="btn btn-secondary btn-sm"
                                  onClick={() => handleToggleAgent(ag.agent_id, false)}
                                  disabled={isUpdating}
                                  style={{ color: 'var(--red)', borderColor: 'rgba(239, 68, 68, 0.4)' }}
                                >
                                  {isUpdating ? 'Updating...' : 'Disable'}
                                </button>
                              ) : (
                                <button
                                  id={`btn-enable-${ag.agent_id}`}
                                  className="btn btn-primary btn-sm"
                                  onClick={() => handleToggleAgent(ag.agent_id, true)}
                                  disabled={isUpdating}
                                >
                                  {isUpdating ? 'Updating...' : 'Enable'}
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Project-Safe Preferences (Scope Mode === 'project') */}
                {scopeMode === 'project' && activeProject && (
                  <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 4, padding: 14 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span>🎯</span> Project Preferences for {activeProject.name || activeProject.project_id}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 12 }}>
                      Configure per-project agent preferences safely without modifying global agent availability.
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
                      {agents.filter(a => a.agent_id !== 'agent-claude-01').map(ag => {
                        const pref = projectPrefs.find(p => p.agent_id === ag.agent_id);
                        const isAllowed = pref ? Boolean(pref.is_allowed) : true;
                        const isPreferred = pref ? Boolean(pref.is_preferred) : ag.agent_id === 'agent-agy-01';

                        return (
                          <div key={ag.agent_id} style={{ padding: 10, background: 'var(--bg-subtle)', border: '1px solid var(--border-dim)', borderRadius: 4 }}>
                            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>{ag.display_name || ag.name}</div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 11 }}>
                              <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                                <input
                                  type="checkbox"
                                  checked={isAllowed}
                                  onChange={e => handleSaveProjectPref(ag.agent_id, e.target.checked, isPreferred)}
                                />
                                <span>Allowed for Project</span>
                              </label>
                              <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                                <input
                                  type="radio"
                                  name="preferred_project_agent"
                                  checked={isPreferred}
                                  onChange={() => handleSaveProjectPref(ag.agent_id, true, true)}
                                />
                                <span>Preferred Agent</span>
                              </label>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                <div className="form-group" style={{ marginTop: 8 }}>
                  <label className="form-label" style={{ fontWeight: 600 }}>Max Concurrent Agents</label>
                  <input
                    type="number"
                    className="form-control"
                    value={draft.agents.max_concurrent_agents}
                    onChange={e => setDraft(prev => ({ ...prev, agents: { ...prev.agents, max_concurrent_agents: Number(e.target.value) } }))}
                    style={{ width: 140 }}
                  />
                  <div className="text-muted" style={{ fontSize: 11, marginTop: 4 }}>
                    Concurrency bound for parallel task attempts (1–4 elastic range).
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TOOLS & TOOL POLICIES */}
          {(activeSection === 'tools-config' || activeSection === 'tool-policies') && (
            <div className="panel" style={{ maxWidth: 740 }}>
              <div className="panel-header" style={{ padding: '12px 18px', background: 'var(--bg-subtle)' }}>
                <span className="panel-title">Deterministic Tool Plane & Sandboxing</span>
              </div>
              <div className="panel-body" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Enabled Verification Tools</label>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 4 }}>
                    {draft.tools.enabled_tools.map(t => (
                      <span key={t} className="badge badge-info mono" style={{ fontSize: 12, padding: '4px 8px' }}>
                        ✓ {t}
                      </span>
                    ))}
                  </div>
                  <div className="text-muted" style={{ fontSize: 11, marginTop: 6 }}>
                    Deterministic tools execute locally with 0 LLM token consumption.
                  </div>
                </div>

                <div className="form-group">
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={draft.tools.strict_sandboxing}
                      onChange={e => setDraft(prev => ({ ...prev, tools: { ...prev.tools, strict_sandboxing: e.target.checked } }))}
                    />
                    <span style={{ fontSize: 13, fontWeight: 600 }}>Strict Workspace Isolation</span>
                  </label>
                  <div className="text-muted" style={{ fontSize: 11, marginLeft: 24, marginTop: 2 }}>
                    Tools may only read/write inside the target repository path.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* EXECUTION BUDGETS, TIMEOUTS, RETRY */}
          {(activeSection === 'execution-budgets' || activeSection === 'execution-timeouts' || activeSection === 'execution-retry') && (
            <div className="panel" style={{ maxWidth: 740 }}>
              <div className="panel-header" style={{ padding: '12px 18px', background: 'var(--bg-subtle)' }}>
                <span className="panel-title">Execution Bounds, Watchdog Timeouts & Retries</span>
              </div>
              <div className="panel-body" style={{ padding: 18, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Task Timeout (seconds)</label>
                  <input
                    type="number"
                    className="form-control"
                    value={draft.execution.task_timeout_seconds}
                    onChange={e => setDraft(prev => ({ ...prev, execution: { ...prev.execution, task_timeout_seconds: Number(e.target.value) } }))}
                  />
                  <div className="text-muted" style={{ fontSize: 11, marginTop: 4 }}>
                    Watchdog kills tasks exceeding this duration.
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Max Retries Per Task</label>
                  <input
                    type="number"
                    className="form-control"
                    value={draft.execution.max_retries_per_task}
                    onChange={e => setDraft(prev => ({ ...prev, execution: { ...prev.execution, max_retries_per_task: Number(e.target.value) } }))}
                  />
                  <div className="text-muted" style={{ fontSize: 11, marginTop: 4 }}>
                    FailoverEngine re-attempts before flagging gap.
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Default Run Budget (tokens)</label>
                  <input
                    type="number"
                    className="form-control"
                    value={draft.execution.default_run_budget_tokens}
                    onChange={e => setDraft(prev => ({ ...prev, execution: { ...prev.execution, default_run_budget_tokens: Number(e.target.value) } }))}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Total Verification Cap (tokens)</label>
                  <input
                    type="number"
                    className="form-control"
                    value={draft.execution.token_cap}
                    onChange={e => setDraft(prev => ({ ...prev, execution: { ...prev.execution, token_cap: Number(e.target.value) } }))}
                  />
                </div>
              </div>
            </div>
          )}

          {/* APPLICATION & SECURITY */}
          {activeSection.startsWith('app-') && (
            <div className="panel" style={{ maxWidth: 740 }}>
              <div className="panel-header" style={{ padding: '12px 18px', background: 'var(--bg-subtle)' }}>
                <span className="panel-title">Application Appearance & Workstation Layout</span>
              </div>
              <div className="panel-body" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Workstation Theme</label>
                  <select className="form-control" value="Dark EDA">
                    <option value="Dark EDA">Dark EDA (High-Contrast Security Console)</option>
                    <option value="Light Workbench">Light Workbench</option>
                  </select>
                </div>
                <div className="form-group">
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                    <input type="checkbox" checked={true} readOnly />
                    <span style={{ fontSize: 13, fontWeight: 600 }}>Independent Pane Scrolling</span>
                  </label>
                  <div className="text-muted" style={{ fontSize: 11, marginLeft: 24, marginTop: 2 }}>
                    Enforces strict independent scrolling for Sidebar, Cockpit, Timeline, and Inspector without body overflow.
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeSection.startsWith('security-') && (
            <div className="panel" style={{ maxWidth: 740 }}>
              <div className="panel-header" style={{ padding: '12px 18px', background: 'var(--bg-subtle)' }}>
                <span className="panel-title">Hardware Security Invariants & Isolation</span>
              </div>
              <div className="panel-body" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div style={{ background: 'var(--green-bg)', border: '1px solid var(--green-border)', padding: 12, borderRadius: 4, fontSize: 12, color: 'var(--green)' }}>
                  ✓ One Project = One Target Scope invariant actively enforced.<br />
                  ✓ Deterministic evidence required for verification closure.<br />
                  ✓ Claude real execution count = 0 policy strictly enforced.
                </div>
              </div>
            </div>
          )}

          {/* DEVELOPMENT LOGGING & RETENTION ENGINE */}
          {activeSection === 'dev-logging' && (
            <div className="panel" style={{ maxWidth: 840 }}>
              <div className="panel-header" style={{ padding: '12px 18px', background: 'var(--bg-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="panel-title">Development Logging & 1.5 GB Retention Engine</span>
                <span className="badge badge-info" style={{ fontSize: 11 }}>SYSTEM LOGS</span>
              </div>
              <div className="panel-body" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 18 }}>
                
                {/* Dual-Level Architecture Directory Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div style={{ padding: 14, background: 'var(--bg-subtle)', border: '1px solid var(--border-dim)', borderRadius: 4 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>
                      Global Application Logs
                    </div>
                    <div className="mono" style={{ fontSize: 12, color: 'var(--blue)', fontWeight: 600, wordBreak: 'break-all' }}>
                      {loggingConfig?.global_log_dir || 'logs/application/'}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                      System-wide lifecycle events, scheduler dispatches, and supervisor decisions.
                    </div>
                  </div>

                  <div style={{ padding: 14, background: 'var(--bg-subtle)', border: '1px solid var(--border-dim)', borderRadius: 4 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>
                      Project & Run Logs
                    </div>
                    <div className="mono" style={{ fontSize: 12, color: 'var(--green)', fontWeight: 600, wordBreak: 'break-all' }}>
                      {loggingConfig?.project_log_root ? `${loggingConfig.project_log_root}/${activeProject?.project_id || 'proj-id'}/` : `logs/projects/${activeProject?.project_id || 'PROJ'}/`}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                      Isolated stdout/stderr, tool traces, and verification transcripts for each project.
                    </div>
                  </div>
                </div>

                {/* Storage Quota Usage & Thresholds */}
                <div style={{ padding: 16, background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 4 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <div>
                      <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)' }}>Global Storage Quota</span>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>1.5 GB System Limit</span>
                    </div>
                    <div className="mono" style={{ fontSize: 12, fontWeight: 700, color: (loggingConfig?.global_usage_pct || 0) >= 90 ? 'var(--red)' : ((loggingConfig?.global_usage_pct || 0) >= 80 ? '#f59e0b' : 'var(--blue)') }}>
                      {((loggingConfig?.global_used_bytes || 0) / (1024 * 1024)).toFixed(2)} MB / 1536.00 MB ({loggingConfig?.global_usage_pct != null ? loggingConfig.global_usage_pct.toFixed(2) : '0.00'}%)
                    </div>
                  </div>

                  {/* Progress Bar with 80% and 90% Markers */}
                  <div style={{ position: 'relative', height: 16, background: 'var(--bg-subtle)', borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border-dim)' }}>
                    <div
                      style={{
                        height: '100%',
                        width: `${Math.min(100, loggingConfig?.global_usage_pct || 1)}%`,
                        background: (loggingConfig?.global_usage_pct || 0) >= 90 ? 'var(--red)' : ((loggingConfig?.global_usage_pct || 0) >= 80 ? '#f59e0b' : 'var(--blue)'),
                        transition: 'width 0.4s ease'
                      }}
                    />
                    <div style={{ position: 'absolute', left: '80%', top: 0, bottom: 0, width: 2, background: 'rgba(245, 158, 11, 0.7)' }} title="80% Warning Limit" />
                    <div style={{ position: 'absolute', left: '90%', top: 0, bottom: 0, width: 2, background: 'rgba(239, 68, 68, 0.7)' }} title="90% Urgent Clean Limit" />
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginTop: 6, fontFamily: 'var(--font-mono)' }}>
                    <span>0 MB</span>
                    <span style={{ color: '#f59e0b' }}>▲ 80% (1.20 GB) Warning</span>
                    <span style={{ color: 'var(--red)' }}>▲ 90% (1.35 GB) Auto-Clean</span>
                    <span>1.50 GB (100%)</span>
                  </div>
                </div>

                {/* Retention Policy Details & Protections */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div style={{ padding: 14, background: 'var(--bg-subtle)', border: '1px solid var(--border-dim)', borderRadius: 4 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)', marginBottom: 6 }}>
                      ⏳ 3-Day Retention Policy
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                      Completed runs and archived execution logs older than <strong>3 days</strong> are eligible for deterministic removal when quota thresholds are reached.
                    </div>
                  </div>

                  <div style={{ padding: 14, background: 'var(--bg-subtle)', border: '1px solid var(--border-dim)', borderRadius: 4 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--green)', marginBottom: 6 }}>
                      🛡️ Protected Invariants
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                      Active runs (PID alive), evidence artifacts, findings dossiers, and SQLite database (<code className="mono">llmorch.db</code>) are <strong>never</strong> pruned.
                    </div>
                  </div>
                </div>

                {/* Cleanup Action Trigger */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 14, background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 4 }}>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)' }}>Manual Quota Enforcement</div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                      Immediately run retention sweep to prune expired logs and compress older runs.
                    </div>
                  </div>
                  <button
                    id="btn-run-log-cleanup"
                    className="btn btn-primary btn-sm"
                    onClick={handleRunCleanup}
                    disabled={cleaningLogs}
                    style={{ fontWeight: 600, padding: '6px 16px' }}
                  >
                    {cleaningLogs ? 'Cleaning...' : '🧹 Run Cleanup Now'}
                  </button>
                </div>

                {cleanupResult && (
                  <div style={{ padding: 12, background: 'var(--bg-elevated)', border: '1px solid var(--green-border)', borderRadius: 4, fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                    <div style={{ color: 'var(--green)', fontWeight: 700, marginBottom: 4 }}>✓ Last Cleanup Result</div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                      <div>Status: <span style={{ color: 'var(--text-bright)' }}>{cleanupResult.status}</span></div>
                      <div>Files Removed: <span style={{ color: 'var(--text-bright)' }}>{cleanupResult.files_removed}</span></div>
                      <div>Freed: <span style={{ color: 'var(--text-bright)' }}>{(cleanupResult.bytes_freed / 1024).toFixed(1)} KB</span></div>
                      <div>Protected Active Runs: <span style={{ color: 'var(--green)' }}>{cleanupResult.active_runs_protected_count || 0}</span></div>
                    </div>
                  </div>
                )}

              </div>
            </div>
          )}

        </div>

      </div>

    </div>
  );
}
