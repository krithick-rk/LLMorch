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

  // Run Control (Phase 9.4 state machine)
  runs: (params = {}) => req('/runs?' + new URLSearchParams(params)),
  currentRun: (params = {}) => req('/runs/current' + (Object.keys(params).length ? '?' + new URLSearchParams(params) : '')),
  runDetail: (id) => req(`/runs/${id}`),
  pauseRun: (id, body = {}) => req(`/runs/${id}/pause`, { method: 'POST', body: JSON.stringify(body) }),
  resumeRun: (id, body = {}) => req(`/runs/${id}/resume`, { method: 'POST', body: JSON.stringify(body) }),
  stopRun: (id, body = {}) => req(`/runs/${id}/stop`, { method: 'POST', body: JSON.stringify(body) }),
  emergencyStop: (id, body = {}) => req(`/runs/${id}/emergency-stop`, { method: 'POST', body: JSON.stringify({ ...body, emergency: true }) }),
  runEvents: (id, params = {}) => req(`/runs/${id}/events?` + new URLSearchParams(params)),

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

  // Phase 9.3 — Agent Workflow, Analyst Instructions, PoC Lifecycle
  taskAttempts: (taskId) => req(`/tasks/${taskId}/attempts`),
  toolExecutions: (params = {}) => req('/tools/executions?' + new URLSearchParams(params)),
  // Submit instruction: POST /api/tasks/{task_id}/instructions
  submitAnalystInstruction: (body) =>
    req(`/tasks/${body.task_id}/instructions`, { method: 'POST', body: JSON.stringify({ message: body.instruction }) }),
  agentRoles: () => req('/agents/roles'),
  assignAgentRole: (body) => req('/agents/roles/assign', { method: 'POST', body: JSON.stringify(body) }),

  // PoC / Reproducer lifecycle — routes are /{finding_id}/poc/{action}
  generatePoC: (body) => req(`/findings/${body.finding_id}/poc/generate`, { method: 'POST', body: JSON.stringify(body) }),
  executePoC:  (body) => req(`/findings/${body.finding_id}/poc/${body.version_id || body.reproducer_id}/execute`, { method: 'POST', body: JSON.stringify(body) }),
  validatePoC: (body) => req(`/findings/${body.finding_id}/poc/${body.version_id || body.reproducer_id}/validate`, { method: 'POST', body: JSON.stringify(body) }),
  findingDossier: (id) => req(`/findings/${id}/dossier`),

  // Phase 9.3 — Analysis Lifecycle
  preValidateAnalysis: () => req('/analysis/pre-validate', { method: 'POST' }),
  startAnalysis: (body) => req('/analysis/start', { method: 'POST', body: JSON.stringify(body) }),

  // Tool Registry
  tools: (params = {}) => req('/tools?' + new URLSearchParams(params)),
  toolDetail: (name) => req(`/tools/${name}`),
  toolExecHistory: (name, params = {}) => req(`/tools/${name}/executions?` + new URLSearchParams(params)),

  // Phase 9.5 — Questions & Decision Inbox
  questions: (params = {}) => req('/questions?' + new URLSearchParams(params)),
  question: (id) => req(`/questions/${id}`),
  answerQuestion: (id, body) => req(`/questions/${id}/answer`, { method: 'POST', body: JSON.stringify(body) }),
  dismissQuestion: (id, body = {}) => req(`/questions/${id}/dismiss`, { method: 'POST', body: JSON.stringify(body) }),

  // Phase 9.5 — Repository Intake & Capability Report
  analyzeRepository: (body = {}) => req('/repositories/analyze', { method: 'POST', body: JSON.stringify(body) }),
  currentRepoOverview: () => req('/repositories/current/overview'),
  repositoryPreflight: (path) => req('/repositories/preflight' + (path ? `?path=${encodeURIComponent(path)}` : '')),

  // Phase 9.5 — Agent Runtime & Local Terminal Guidance
  agentRuntimeStatus: () => req('/agents/runtime/status'),
  refreshAgentRuntimeStatus: () => req('/agents/runtime/refresh', { method: 'POST' }),
  openTerminal: (body = {}) => req('/agents/runtime/terminal', { method: 'POST', body: JSON.stringify(body) }),

  // Phase 9.5 — Attempt Detail
  attemptDetail: (id) => req(`/attempts/${id}`),

  // Phase 9.6 — Dual Agent Chat & Entity Details
  taskChatHistory: (taskId) => req(`/chat/task/${taskId}`),
  sendTaskInstruction: (taskId, body) => req(`/chat/task/${taskId}`, { method: 'POST', body: JSON.stringify(body) }),
  investigationChatHistory: (runId) => req(`/chat/investigation${runId ? `?run_id=${runId}` : ''}`),
  sendInvestigationQuery: (body, runId) => req(`/chat/investigation${runId ? `?run_id=${runId}` : ''}`, { method: 'POST', body: JSON.stringify(body) }),
  taskDetail: (taskId) => req(`/tasks/${taskId}`),
  repositoryDetail: (repoId) => req(`/repository/${repoId}`),

  // Phase 10 — SoC Verification Platform
  // Supervisor & Verification Plans
  generateVerificationPlan: (body = {}) => req('/supervisor/plan', { method: 'POST', body: JSON.stringify(body) }),
  listVerificationPlans: (params = {}) => req('/supervisor/plans?' + new URLSearchParams(params)),
  getVerificationPlan: (planId) => req(`/supervisor/plan/${planId}`),
  approveVerificationPlan: (planId) => req(`/supervisor/plan/${planId}/approve`, { method: 'POST' }),
  rejectVerificationPlan: (planId) => req(`/supervisor/plan/${planId}/reject`, { method: 'POST' }),
  replanVerificationPlan: (planId, body) => req(`/supervisor/plan/${planId}/replan`, { method: 'POST', body: JSON.stringify(body) }),

  // Specifications
  ingestSpecification: (body) => req('/specifications/ingest', { method: 'POST', body: JSON.stringify(body) }),
  listSpecifications: () => req('/specifications'),
  listSpecRequirements: (specId) => req(`/specifications/${specId}/requirements`),

  // Closure & Traceability
  getClosure: (planId, params = {}) => req(planId ? `/closure/${planId}` : ('/closure?' + new URLSearchParams(params))),
  recordWaiver: (planId, body) => req(`/closure/${planId}/waiver`, { method: 'POST', body: JSON.stringify(body) }),
  recordGap: (planId, body) => req(`/closure/${planId}/gap`, { method: 'POST', body: JSON.stringify(body) }),

  // Policies (SoCureLLM-inspired)
  listPolicies: (status) => req(`/policies${status ? `?status=${status}` : ''}`),
  createPolicy: (body) => req('/policies', { method: 'POST', body: JSON.stringify(body) }),
  reviewPolicy: (policyId, body) => req(`/policies/${policyId}/review`, { method: 'POST', body: JSON.stringify(body) }),

  // Context Fabric
  getContextSummary: () => req('/context-fabric/summary'),
  getContextPack: (taskId) => req(`/context-fabric/pack/${taskId}`),

  // User Tasks, Diagnostics & Actionable Overrides
  createUserTask: (body) => req('/tasks/create', { method: 'POST', body: JSON.stringify(body) }),
  retryTaskWithOverrides: (taskId, body) => req(`/tasks/${taskId}/retry`, { method: 'POST', body: JSON.stringify(body) }),
  getTaskDiagnostics: (taskId) => req(`/tasks/${taskId}/diagnostics`),
  // Project Workspace & Natural Instruction Model
  projects: () => req('/projects'),
  activeProject: () => req('/projects/active'),
  createProject: (body) => req('/projects', { method: 'POST', body: JSON.stringify(body) }),
  activateProject: (id) => req(`/projects/${id}/activate`, { method: 'POST' }),
  projectDetail: (id) => req(`/projects/${id}`),
  projectSummary: (id) => req(`/projects/${id}/summary`),
  archiveProject: (id) => req(`/projects/${id}/archive`, { method: 'POST' }),
  projectBriefing: (id) => req(`/projects/${id}/briefing`),
  interpretInstruction: (id, body) => req(`/projects/${id}/interpret`, { method: 'POST', body: JSON.stringify(body) }),
};

export default api;
