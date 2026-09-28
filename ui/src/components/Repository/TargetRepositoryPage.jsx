/**
 * TargetRepositoryPage.jsx — Professional SoC Repository Intake & Inventory
 * Section 10: Answers clearly:
 * 1. What is this repository?
 * 2. What did LLMorch discover?
 * 3. Can it actually be analyzed?
 * 4. What should happen next?
 */

import { useState, useEffect, useCallback } from 'react'
import api from '../../api'
import { StatusPill, Spinner, fmt, Mono } from '../shared'
import { RepositorySelectorModal } from '../RepositorySelectorModal'

export function TargetRepositoryPage({ repoId, onNavigate }) {
  const [currentRepo, setCurrentRepo] = useState(null)
  const [preflight, setPreflight] = useState(null)
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState(null)
  const [isRepoSelectorOpen, setIsRepoSelectorOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('inventory')

  const loadRepoData = useCallback(async () => {
    try {
      setLoading(true)
      const cur = await api.currentRepository().catch(() => null)
      const repo = cur?.repository || null
      setCurrentRepo(repo)

      // Query deterministic preflight report
      const pf = await api.repositoryPreflight(repo?.repository_path).catch(() => null)
      setPreflight(pf)
      setError(null)
    } catch (err) {
      setError(err.message || 'Failed to load repository status')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadRepoData()
  }, [loadRepoData])

  const handleRunAnalysis = async () => {
    if (analyzing) return
    setAnalyzing(true)
    try {
      await api.analyzeRepository({ repository_path: currentRepo?.repository_path })
      await loadRepoData()
      if (onNavigate) {
        onNavigate('verification-plan')
      }
    } catch (err) {
      alert(`Analysis Initiation Failed: ${err.message}`)
    } finally {
      setAnalyzing(false)
    }
  }

  if (loading && !currentRepo && !preflight) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', padding: 40 }}>
        <Spinner size={24} />
      </div>
    )
  }

  const repoName = currentRepo?.repository_name || preflight?.repository_name || (currentRepo?.repository_path ? currentRepo.repository_path.split('/').pop() : 'No Target Selected')
  const repoPath = currentRepo?.repository_path || preflight?.repository_path || '—'
  const isAnalyzable = preflight?.analyzable_files_count > 0 || (preflight?.total_files > 0 && !preflight?.is_terminal)
  const classification = preflight?.classification || (isAnalyzable ? 'HARDWARE_AND_SOFTWARE' : 'EMPTY_REPOSITORY')
  const isEmpty = !isAnalyzable && (preflight?.total_files === 0 || preflight?.analyzable_files_count === 0)

  // Language inventory breakdowns
  const fileInventory = preflight?.file_inventory || []
  const rtlFiles = fileInventory.filter(f => f.language === 'SystemVerilog' || f.language === 'Verilog' || f.language === 'VHDL')
  const swFiles = fileInventory.filter(f => ['C', 'C++', 'Rust', 'Go', 'Python'].includes(f.language))
  const specFiles = fileInventory.filter(f => ['PDF', 'Markdown', 'SVD', 'YAML', 'JSON', 'Hjson'].includes(f.language))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      {/* ── Top Header ──────────────────────────────────────────────────────── */}
      <div className="page-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-bright)' }}>
              Target Repository Intake
            </span>
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: 11, padding: '1px 6px',
              background: isAnalyzable ? 'var(--green-bg)' : 'var(--red-bg)',
              color: isAnalyzable ? 'var(--green)' : 'var(--red)',
              border: `1px solid ${isAnalyzable ? 'var(--green-border)' : 'var(--red-border)'}`,
              borderRadius: 2, fontWeight: 600
            }}>
              {isAnalyzable ? 'ANALYSIS READY' : 'NON-ANALYZABLE'}
            </span>
          </div>
          <div className="page-subtitle">
            Deterministic preflight verification, structural inventory, and capability readiness
          </div>
        </div>

        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn btn-secondary btn-sm" onClick={() => setIsRepoSelectorOpen(true)}>
            Switch Repository
          </button>
          <button className="btn btn-secondary btn-sm" onClick={loadRepoData}>
            ↺ Re-scan
          </button>
          {isAnalyzable && (
            <button
              id="btn-analyze-repo-top"
              className="btn btn-primary btn-sm"
              onClick={handleRunAnalysis}
              disabled={analyzing}
            >
              {analyzing ? 'Analyzing...' : 'Analyze Repository'}
            </button>
          )}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* ── Section 10: 4 Core Questions Strip ──────────────────────────────── */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          {/* 1. What is this repository? */}
          <div className="stat-tile blue">
            <div className="stat-label">1. Target Identity</div>
            <div className="stat-value truncate" style={{ fontSize: 15 }} title={repoName}>
              {repoName}
            </div>
            <div className="stat-sub truncate mono" title={repoPath}>
              {repoPath}
            </div>
          </div>

          {/* 2. What did LLMorch discover? */}
          <div className="stat-tile blue">
            <div className="stat-label">2. Discovered Content</div>
            <div className="stat-value">
              {preflight?.total_files ?? currentRepo?.file_count ?? 0} files
            </div>
            <div className="stat-sub">
              RTL: {rtlFiles.length} | SW: {swFiles.length} | Specs: {preflight?.specifications_count ?? specFiles.length}
            </div>
          </div>

          {/* 3. Can it actually be analyzed? */}
          <div className={`stat-tile ${isAnalyzable ? 'green' : 'red'}`}>
            <div className="stat-label">3. Analysis Feasibility</div>
            <div className="stat-value" style={{ color: isAnalyzable ? 'var(--green)' : 'var(--red)' }}>
              {isAnalyzable ? 'FEASIBLE' : 'NOT ANALYZABLE'}
            </div>
            <div className="stat-sub truncate">
              {preflight?.analysis_feasibility || (isAnalyzable ? 'High SoC Feasibility' : 'Insufficient material')}
            </div>
          </div>

          {/* 4. Classification & Build */}
          <div className="stat-tile blue">
            <div className="stat-label">4. System Classification</div>
            <div className="stat-value" style={{ fontSize: 13, textTransform: 'uppercase' }}>
              {classification.replace(/_/g, ' ')}
            </div>
            <div className="stat-sub">
              Build: {preflight?.build_system_detected ? (preflight.build_systems?.join(', ') || 'Detected') : 'None'}
            </div>
          </div>
        </div>

        {/* ── Empty / Non-Analyzable Warning Box ──────────────────────────────── */}
        {isEmpty && (
          <div className="diag-box" style={{ borderLeftColor: 'var(--amber)', background: '#fffbeb' }}>
            <div className="diag-header">
              <span className="diag-title" style={{ color: 'var(--amber)' }}>
                ⚠ NO ANALYZABLE SOURCE MATERIAL WAS FOUND
              </span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--amber)', fontWeight: 600 }}>
                Classification: EMPTY / NON-ANALYZABLE
              </span>
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5 }}>
              The target path contains no supported RTL modules (SystemVerilog/Verilog), software code, or specification documents.
              Zero-cost preflight terminated to prevent infinite loops and runaway token estimates.
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>
                Next Actions:
              </span>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsRepoSelectorOpen(true)}>
                Switch to Valid Target Directory
              </button>
              <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('specifications')}>
                + Ingest Specification Document
              </button>
              <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('tasks')}>
                + Create Custom Task
              </button>
            </div>
          </div>
        )}

        {/* ── Primary Action Banner for Analyzable Repositories ───────────────── */}
        {!isEmpty && (
          <div className="panel" style={{ background: '#f8fafc', borderLeft: '4px solid var(--blue)' }}>
            <div className="panel-body" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-bright)' }}>
                  Recommended Next Step: Run 23-Bucket SoC Verification Workflow
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                  Deterministic preflight verified {preflight?.analyzable_files_count || rtlFiles.length} analyzable source files.
                  Estimated budget: ~{preflight?.estimated_tokens ? (preflight.estimated_tokens / 1000).toFixed(0) : 120}k tokens across structural, formal, and security domains.
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                <button
                  id="btn-analyze-repo-action"
                  className="btn btn-primary btn-md"
                  onClick={handleRunAnalysis}
                  disabled={analyzing}
                >
                  {analyzing ? 'Analyzing Repository...' : 'Analyze Repository'}
                </button>
                <button className="btn btn-secondary btn-md" onClick={() => onNavigate('verification-plan')}>
                  Open Verification Plan
                </button>
                <button className="btn btn-secondary btn-md" onClick={() => onNavigate('specifications')}>
                  Add Specification
                </button>
                <button className="btn btn-secondary btn-md" onClick={() => onNavigate('tasks')}>
                  Create Custom Task
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Tabs for Repository Inventory and Readiness ─────────────────────── */}
        <div className="tab-bar" style={{ background: 'transparent', padding: 0 }}>
          <div
            className={`tab-item ${activeTab === 'inventory' ? 'active' : ''}`}
            onClick={() => setActiveTab('inventory')}
          >
            File Inventory ({fileInventory.length})
          </div>
          <div
            className={`tab-item ${activeTab === 'details' ? 'active' : ''}`}
            onClick={() => setActiveTab('details')}
          >
            Readiness & Capability Report
          </div>
        </div>

        {activeTab === 'inventory' && (
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Relative Path</th>
                  <th style={{ width: 140 }}>Language / Type</th>
                  <th style={{ width: 100 }}>Size</th>
                  <th style={{ width: 120 }}>Analyzable</th>
                </tr>
              </thead>
              <tbody>
                {fileInventory.length === 0 ? (
                  <tr>
                    <td colSpan={4} style={{ textAlign: 'center', padding: 24, color: 'var(--text-muted)' }}>
                      No files discovered in repository path.
                    </td>
                  </tr>
                ) : (
                  fileInventory.map((f, i) => (
                    <tr key={i}>
                      <td className="mono" style={{ color: 'var(--text-primary)' }}>
                        {f.path}
                      </td>
                      <td>
                        <span style={{
                          fontFamily: 'var(--font-mono)', fontSize: 11,
                          padding: '1px 5px', background: 'var(--bg-subtle)',
                          border: '1px solid var(--border-dim)', borderRadius: 2
                        }}>
                          {f.language || 'Unknown'}
                        </span>
                      </td>
                      <td className="mono">
                        {f.size_bytes != null ? `${(f.size_bytes / 1024).toFixed(1)} KB` : '—'}
                      </td>
                      <td>
                        {f.is_analyzable ? (
                          <span style={{ color: 'var(--green)', fontWeight: 600, fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                            ✓ YES
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                            — NO
                          </span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'details' && (
          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">Preflight Audit Metadata</span>
            </div>
            <div className="panel-body" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
              <div className="kv-row"><span className="kv-key">Repository Path</span><span className="kv-val mono">{repoPath}</span></div>
              <div className="kv-row"><span className="kv-key">Classification</span><span className="kv-val mono">{classification}</span></div>
              <div className="kv-row"><span className="kv-key">Total Files</span><span className="kv-val mono">{preflight?.total_files ?? 0}</span></div>
              <div className="kv-row"><span className="kv-key">Zero-byte Files</span><span className="kv-val mono">{preflight?.zero_byte_files_count ?? 0}</span></div>
              <div className="kv-row"><span className="kv-key">Analyzable Files</span><span className="kv-val mono">{preflight?.analyzable_files_count ?? 0}</span></div>
              <div className="kv-row"><span className="kv-key">Build Systems</span><span className="kv-val mono">{preflight?.build_systems?.join(', ') || 'None'}</span></div>
              <div className="kv-row"><span className="kv-key">Estimated Tokens</span><span className="kv-val mono">{preflight?.estimated_tokens ? `${preflight.estimated_tokens} tokens` : '0'}</span></div>
              <div className="kv-row"><span className="kv-key">Preflight Terminal Status</span><span className="kv-val mono">{preflight?.terminal_status || 'READY_FOR_ANALYSIS'}</span></div>
            </div>
          </div>
        )}

      </div>

      {isRepoSelectorOpen && (
        <RepositorySelectorModal
          isOpen={isRepoSelectorOpen}
          onClose={() => setIsRepoSelectorOpen(false)}
          onSelect={(selected) => {
            setIsRepoSelectorOpen(false)
            loadRepoData()
          }}
        />
      )}
    </div>
  )
}
export default TargetRepositoryPage
