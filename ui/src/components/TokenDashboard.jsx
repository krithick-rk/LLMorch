import React, { useState, useEffect, useCallback } from 'react';
import api from '../api';

function Mono({ children }) {
  return <span className="mono">{children}</span>;
}

export function TokenDashboard({ refreshSignal, onOpenEstimateModal }) {
  const [tokensData, setTokensData] = useState(null);
  const [budgetData, setBudgetData] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [t, b] = await Promise.all([
        api.tokens().catch(() => null),
        api.budgets().catch(() => null),
      ]);
      setTokensData(t);
      setBudgetData(b);
    } catch {
      // Silently proceed with fallback
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData, refreshSignal]);

  const summary = tokensData?.summary || {
    total_actual_tokens: 0,
    total_estimated_tokens: 0,
    total_input_tokens: 0,
    total_output_tokens: 0,
    by_agent: {},
    by_model: {},
    by_stage: {},
    active_limit_status: 'AVAILABLE',
  };

  const budget = budgetData?.items?.[0] || {
    budget_limit_tokens: 150000,
    total_consumed_tokens: summary.total_actual_tokens || 0,
    limit_status: summary.active_limit_status || 'AVAILABLE',
  };

  const limitTokens = budget.budget_limit_tokens || 150000;
  const consumedTokens = budget.total_consumed_tokens || summary.total_actual_tokens || 0;
  const pct = Math.min(100, Math.round((consumedTokens / Math.max(1, limitTokens)) * 100));
  const remainingTokens = Math.max(0, limitTokens - consumedTokens);
  const statusKey = (budget.limit_status || 'AVAILABLE').toLowerCase();

  return (
    <div className="card" style={{ marginBottom: '20px', border: '1px solid var(--border-bright)' }}>
      <div className="card-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div className="card-title">🪙 Authoritative Token Accounting & Budget</div>
          <span className={`badge badge-${statusKey}`}>
            {budget.limit_status || 'AVAILABLE'}
          </span>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-primary btn-sm" onClick={onOpenEstimateModal}>
            📊 Estimate Repo Tokens
          </button>
          <button className="btn btn-secondary btn-sm" onClick={loadData}>
            ↺ Refresh
          </button>
        </div>
      </div>

      {/* Progress Bar & Budget Overview */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
          <span style={{ color: 'var(--text-secondary)' }}>
            Consumed: <strong>{consumedTokens.toLocaleString()}</strong> / {limitTokens.toLocaleString()} tokens ({pct}%)
          </span>
          <span style={{ color: 'var(--text-secondary)' }}>
            Remaining: <strong className={pct > 90 ? 'text-red' : pct > 75 ? 'text-amber' : 'text-green'}>{remainingTokens.toLocaleString()}</strong> tokens
          </span>
        </div>

        <div className="progress-track">
          <div
            className={`progress-fill ${statusKey}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Metric Cards */}
      <div className="stat-grid" style={{ marginBottom: '16px' }}>
        <div className="stat-card">
          <div className="stat-label">Actual Consumed</div>
          <div className="stat-value text-blue">{consumedTokens.toLocaleString()}</div>
          <div className="stat-sub">Authoritative tracking</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Estimated Allocation</div>
          <div className="stat-value">{(summary.total_estimated_tokens || 0).toLocaleString()}</div>
          <div className="stat-sub">Pre-dispatch estimate</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Prompt / Completion</div>
          <div className="stat-value text-green">
            {((summary.total_input_tokens || 0) / 1000).toFixed(1)}k / {((summary.total_output_tokens || 0) / 1000).toFixed(1)}k
          </div>
          <div className="stat-sub">Input vs output tokens</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Accuracy Ratio</div>
          <div className="stat-value text-purple">
            {summary.total_estimated_tokens > 0
              ? `${Math.round((summary.total_actual_tokens / summary.total_estimated_tokens) * 100)}%`
              : '100%'}
          </div>
          <div className="stat-sub">Actual vs predicted</div>
        </div>
      </div>

      {/* Breakdowns by Agent, Model, and Stage */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        {/* Agent breakdown */}
        <div style={{ background: 'var(--bg-base)', borderRadius: '6px', padding: '12px', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '8px' }}>
            CONSUMPTION BY AGENT
          </div>
          {Object.keys(summary.by_agent || {}).length === 0 ? (
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>No agent usage recorded yet</div>
          ) : (
            Object.entries(summary.by_agent).map(([agentId, count]) => (
              <div key={agentId} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid var(--border)', fontSize: '12px' }}>
                <Mono>{agentId}</Mono>
                <span style={{ fontWeight: 500 }}>{count.toLocaleString()} tokens</span>
              </div>
            ))
          )}
        </div>

        {/* Model breakdown */}
        <div style={{ background: 'var(--bg-base)', borderRadius: '6px', padding: '12px', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '8px' }}>
            CONSUMPTION BY MODEL
          </div>
          {Object.keys(summary.by_model || {}).length === 0 ? (
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>No model usage recorded yet</div>
          ) : (
            Object.entries(summary.by_model).map(([modelId, count]) => (
              <div key={modelId} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid var(--border)', fontSize: '12px' }}>
                <Mono>{modelId}</Mono>
                <span style={{ fontWeight: 500 }}>{count.toLocaleString()} tokens</span>
              </div>
            ))
          )}
        </div>

        {/* Stage breakdown */}
        <div style={{ background: 'var(--bg-base)', borderRadius: '6px', padding: '12px', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '8px' }}>
            CONSUMPTION BY PIPELINE STAGE
          </div>
          {Object.keys(summary.by_stage || {}).length === 0 ? (
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>No stage breakdown recorded yet</div>
          ) : (
            Object.entries(summary.by_stage).map(([stage, count]) => (
              <div key={stage} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid var(--border)', fontSize: '12px' }}>
                <span style={{ textTransform: 'capitalize' }}>{stage}</span>
                <span style={{ fontWeight: 500 }}>{count.toLocaleString()} tokens</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
