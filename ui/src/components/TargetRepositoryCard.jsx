import React from 'react';

function Mono({ children }) {
  return <span className="mono">{children}</span>;
}

export function TargetRepositoryCard({ currentRepo, onOpenSelector, onOpenEstimator }) {
  const isSelected = !!currentRepo?.repository_path;

  return (
    <div className="card" style={{ marginBottom: '20px', border: '1px solid var(--accent-cyan)' }}>
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '18px' }}>🎯</span>
          <div>
            <div className="card-title" style={{ color: 'var(--accent-cyan)', letterSpacing: '0.5px' }}>
              TARGET / ATTACK REPOSITORY
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Authoritative target repository context for token estimation, analysis units, and agent investigation
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={onOpenSelector}
            id="btn-change-repo"
          >
            {isSelected ? '📁 Change Repository' : '🎯 Select Target Repository'}
          </button>
          {isSelected && (
            <button
              className="btn btn-primary btn-sm"
              onClick={onOpenEstimator}
              id="btn-estimate-repo-tokens"
            >
              📊 Estimate Tokens
            </button>
          )}
        </div>
      </div>

      <div style={{ padding: '16px' }}>
        {isSelected ? (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px', marginBottom: '12px' }}>
              <div>
                <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
                  {currentRepo.repository_name || 'Repository'}
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                  <Mono>{currentRepo.repository_path}</Mono>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
                <span className="badge badge-success" style={{ padding: '4px 8px', fontSize: '11px' }}>
                  ✓ VALIDATED
                </span>
                <span className="badge badge-primary" style={{ padding: '4px 8px', fontSize: '11px' }}>
                  Family: {currentRepo.repository_family || 'UNKNOWN'}
                </span>
                {currentRepo.is_git && (
                  <span className="badge badge-running" style={{ padding: '4px 8px', fontSize: '11px' }}>
                    Git: {currentRepo.git_revision ? currentRepo.git_revision.substring(0, 8) : 'HEAD'}
                  </span>
                )}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px', background: 'var(--bg-card)', padding: '10px 14px', borderRadius: '6px', border: '1px solid var(--border)' }}>
              <div>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Files Discovered:</span>
                <div style={{ fontSize: '14px', fontWeight: 600 }}>{currentRepo.file_count?.toLocaleString() || 0}</div>
              </div>
              <div>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Security Architecture:</span>
                <div style={{ fontSize: '13px', fontWeight: 600 }}>{currentRepo.repository_family || 'Standard'}</div>
              </div>
              <div>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Revision / Commit:</span>
                <div style={{ fontSize: '12px' }}>
                  <Mono>{currentRepo.git_revision ? currentRepo.git_revision.substring(0, 12) : 'local directory'}</Mono>
                </div>
              </div>
              <div>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Key Languages:</span>
                <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '2px' }}>
                  {(currentRepo.languages || []).length > 0 ? (
                    currentRepo.languages.slice(0, 5).map(l => (
                      <span key={l} className="cap-tag" style={{ fontSize: '10px' }}>{l}</span>
                    ))
                  ) : (
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Auto-detected</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div style={{ padding: '20px', textAlign: 'center', background: 'rgba(0,0,0,0.1)', borderRadius: '6px' }}>
            <div style={{ fontSize: '28px', marginBottom: '8px' }}>📂</div>
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
              No Target / Attack Repository Selected
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '14px', maxWidth: '460px', margin: '0 auto 14px auto' }}>
              Select or browse a target repository to anchor the security analysis units, token estimator, and agent investigation.
            </div>
            <button
              className="btn btn-primary"
              onClick={onOpenSelector}
            >
              🎯 Configure Target Repository
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default TargetRepositoryCard;
