/**
 * LLMorch API client (Phase 9.1).
 * All state flows through this — no direct DB access from the browser.
 */

const BASE = '/api';

async function req(path, opts = {}) {
  const token = sessionStorage.getItem('llmorch_token');
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (token) headers['X-Session-Token'] = token;
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = j.detail || detail; } catch {}
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export const api = {
  health: () => req('/health'),
  session: () => req('/session'),

  // Tasks
  tasks: (params = {}) => req('/tasks?' + new URLSearchParams(params)),
  task:  (id) => req(`/tasks/${id}`),
  createTask: (body) => req('/tasks', { method: 'POST', body: JSON.stringify(body) }),

  // Agents
  agents: (params = {}) => req('/agents?' + new URLSearchParams(params)),
  getAgents: (params = {}) => req('/agents?' + new URLSearchParams(params)),
  agent:  (id) => req(`/agents/${id}`),
  agentModels: (agentId) => req(`/agents/${agentId}/models`),
  getAgentModels: (agentId) => req(`/agents/${agentId}/models`),

  // Models (Phase 9.1)
  models: (params = {}) => req('/models?' + new URLSearchParams(params)),
  getModels: (params = {}) => req('/models?' + new URLSearchParams(params)),
  model:  (id) => req(`/models/${id}`),

  // Findings
  findings: (params = {}) => req('/findings?' + new URLSearchParams(params)),
  finding:  (id) => req(`/findings/${id}`),

  // Evidence
  evidence:     (params = {}) => req('/evidence?' + new URLSearchParams(params)),
  evidenceItem: (id) => req(`/evidence/${id}`),

  // Timeline
  timeline: (params = {}) => req('/timeline?' + new URLSearchParams(params)),

  // Repository & Intake (Phase 9.2)
  repositories: (params = {}) => req('/repositories?' + new URLSearchParams(params)),
  currentRepository: () => req('/repositories/current'),
  recentRepositories: (params = {}) => req('/repositories/recent?' + new URLSearchParams(params)),
  validateRepository: (body) => req('/repositories/validate', { method: 'POST', body: JSON.stringify(body) }),
  selectRepository: (body) => req('/repositories/select', { method: 'POST', body: JSON.stringify(body) }),
  browseDirectory: (params = {}) => req('/repositories/browse?' + new URLSearchParams(params)),
  snapshot:     (id) => req(`/snapshots/${id}`),
  analysisUnits:(params = {}) => req('/analysis-units?' + new URLSearchParams(params)),
  analysisUnit: (id) => req(`/analysis-units/${id}`),
  securitySurface: (unitId) => req(`/analysis-units/${unitId}/security-surface`),

  // Repository Token Estimation (Phase 9.1)
  estimateRepository: (body) => req('/repository/estimate', { method: 'POST', body: JSON.stringify(body) }),
  getEstimate: (id) => req(`/repository/estimate/${id}`),

  // Token Tracking & Budgets (Phase 9.1)
  tokens: (params = {}) => req('/tokens?' + new URLSearchParams(params)),
  tokenHistory: (params = {}) => req('/tokens/history?' + new URLSearchParams(params)),
  budgets: (params = {}) => req('/budgets?' + new URLSearchParams(params)),
  updateBudget: (body) => req('/budgets', { method: 'PUT', body: JSON.stringify(body) }),

  // Validation & Reproducers
  validations:   (params = {}) => req('/validation?' + new URLSearchParams(params)),
  validation:    (id) => req(`/validation/${id}`),
  reproducers:   (params = {}) => req('/reproducers?' + new URLSearchParams(params)),
  reproducer:    (id) => req(`/reproducers/${id}`),

  // Controls & Switching (Phase 9.1)
  action: (body) => req('/controls/action', { method: 'POST', body: JSON.stringify(body) }),
  feedback: (body) => req('/controls/feedback', { method: 'POST', body: JSON.stringify(body) }),
  audit: (params = {}) => req('/controls/audit?' + new URLSearchParams(params)),
  agentSwitch: (body) => req('/controls/agent-switch', { method: 'POST', body: JSON.stringify(body) }),
  modelSwitch: (body) => req('/controls/model-switch', { method: 'POST', body: JSON.stringify(body) }),
  switchModel: (body) => req('/controls/model-switch', { method: 'POST', body: JSON.stringify(body) }),
  switches: (params = {}) => req('/controls/switches?' + new URLSearchParams(params)),

  // Settings & Configuration (Phase 9.1)
  settings: () => req('/settings'),
  updateSettings: (body) => req('/settings', { method: 'PUT', body: JSON.stringify(body) }),
  config: () => req('/config'),
};

export default api;
