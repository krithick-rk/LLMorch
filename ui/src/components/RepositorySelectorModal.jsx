import React, { useState, useEffect } from 'react';
import api from '../api';

function Mono({ children }) {
  return <span className="mono">{children}</span>;
}

export function RepositorySelectorModal({ isOpen, onClose, onSelected, currentPath = '' }) {
  const [activeTab, setActiveTab] = useState('path'); // 'path' | 'recent' | 'browse'
  const [candidatePath, setCandidatePath] = useState(currentPath);
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);
  const [validationError, setValidationError] = useState(null);

  // Recent repositories
  const [recentRepos, setRecentRepos] = useState([]);
  const [loadingRecent, setLoadingRecent] = useState(false);

  // Directory browser
  const [browsePath, setBrowsePath] = useState('');
  const [browseData, setBrowseData] = useState(null);
  const [loadingBrowse, setLoadingBrowse] = useState(false);
  const [browseError, setBrowseError] = useState(null);

  // Submitting selection
  const [selecting, setSelecting] = useState(false);
  const [selectSuccess, setSelectSuccess] = useState(null);

  useEffect(() => {
    if (isOpen) {
      setCandidatePath(currentPath || '');
      setValidationResult(null);
      setValidationError(null);
      setSelectSuccess(null);
      loadRecent();
      loadBrowse('');
    }
  }, [isOpen, currentPath]);

  const loadRecent = async () => {
    setLoadingRecent(true);
    try {
      const res = await api.recentRepositories();
      setRecentRepos(res.repositories || []);
    } catch {
      setRecentRepos([]);
    } finally {
      setLoadingRecent(false);
    }
  };

  const loadBrowse = async (path) => {
    setLoadingBrowse(true);
    setBrowseError(null);
    try {
      const res = await api.browseDirectory(path ? { path } : {});
      setBrowseData(res);
      setBrowsePath(res.current_path || '');
    } catch (err) {
      setBrowseError(err.message || 'Failed to browse directory');
    } finally {
      setLoadingBrowse(false);
    }
  };

  if (!isOpen) return null;

  const handleValidate = async (pathToValidate) => {
    const p = (pathToValidate || candidatePath).trim();
    if (!p) {
      setValidationError('Please enter or select a repository directory path.');
      return;
    }
    setValidating(true);
    setValidationError(null);
    setValidationResult(null);

    try {
      const res = await api.validateRepository({ repository_path: p });
      if (res.valid) {
        setValidationResult(res);
        setCandidatePath(res.repository_path);
      } else {
        setValidationError(res.error || 'Repository validation failed. Check directory and permissions.');
      }
    } catch (err) {
      setValidationError(err.message || 'Validation request failed');
    } finally {
      setValidating(false);
    }
  };

  const handleConfirmSelect = async () => {
    const targetPath = validationResult?.repository_path || candidatePath.trim();
    if (!targetPath) return;

    setSelecting(true);
    try {
      const res = await api.selectRepository({ repository_path: targetPath });
      setSelectSuccess(res.message || 'Repository successfully selected!');
      if (onSelected) {
        onSelected(res.repository);
      }
      setTimeout(() => {
        onClose();
        setSelectSuccess(null);
      }, 1000);
    } catch (err) {
      setValidationError(err.message || 'Failed to select repository');
    } finally {
      setSelecting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card modal-card-lg" onClick={e => e.stopPropagation()} style={{ maxWidth: '780px' }}>
        <div className="modal-header">
          <div className="modal-title">
            <span>🎯</span> Select Target / Attack Repository
          </div>
          <button className="btn btn-secondary btn-sm" onClick={onClose} disabled={selecting}>✕</button>
        </div>

        <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Method Navigation Tabs */}
          <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border)', paddingBottom: '8px' }}>
            <button
              className={`btn btn-sm ${activeTab === 'path' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setActiveTab('path')}
              type="button"
            >
              ⌨️ Enter Directory
            </button>
            <button
              className={`btn btn-sm ${activeTab === 'recent' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setActiveTab('recent')}
              type="button"
            >
              🕒 Recent Repositories ({recentRepos.length})
            </button>
            <button
              className={`btn btn-sm ${activeTab === 'browse' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setActiveTab('browse')}
              type="button"
            >
              📁 Browse Allowed Roots
            </button>
          </div>

          {/* TAB 1: Enter Path */}
          {activeTab === 'path' && (
            <div>
              <label className="form-label">Repository Directory Path</label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  className="form-control"
                  style={{ flex: 1 }}
                  placeholder="/home/hackdac/Desktop/intern/LLMorch or /path/to/target"
                  value={candidatePath}
                  onChange={e => {
                    setCandidatePath(e.target.value);
                    setValidationResult(null);
                    setValidationError(null);
                  }}
                  disabled={validating || selecting}
                  id="input-repo-path"
                />
                <button
                  className="btn btn-primary"
                  onClick={() => handleValidate()}
                  disabled={validating || selecting || !candidatePath.trim()}
                  id="btn-validate-repo"
                >
                  {validating ? 'Validating…' : 'Validate Repository'}
                </button>
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                Must be an existing readable directory under authorized repository roots.
              </div>
            </div>
          )}

          {/* TAB 2: Recent Repositories */}
          {activeTab === 'recent' && (
            <div>
              <div className="form-label" style={{ marginBottom: '8px' }}>Select from Recently Configured Repositories</div>
              {loadingRecent ? (
                <div style={{ fontSize: '13px', color: 'var(--text-muted)', padding: '12px' }}>Loading recent repositories...</div>
              ) : recentRepos.length === 0 ? (
                <div style={{ padding: '16px', textAlign: 'center', background: 'var(--bg-card)', borderRadius: '6px', color: 'var(--text-muted)', fontSize: '13px' }}>
                  No recent repositories found in history.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '240px', overflowY: 'auto' }}>
                  {recentRepos.map(r => (
                    <div
                      key={r.repository_path}
                      onClick={() => {
                        setCandidatePath(r.repository_path);
                        handleValidate(r.repository_path);
                        setActiveTab('path');
                      }}
                      style={{
                        padding: '10px 12px',
                        background: 'var(--bg-card)',
                        borderRadius: '6px',
                        border: candidatePath === r.repository_path ? '1px solid var(--accent-cyan)' : '1px solid var(--border)',
                        cursor: 'pointer',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        transition: 'border-color 0.15s ease',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
                          {r.repository_name || 'Repository'}
                          {r.is_git && <span className="badge badge-running" style={{ marginLeft: '8px', fontSize: '9px' }}>Git</span>}
                          <span className="badge badge-primary" style={{ marginLeft: '6px', fontSize: '9px' }}>{r.repository_family}</span>
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                          <Mono>{r.repository_path}</Mono>
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <span className={`badge ${r.is_available ? 'badge-success' : 'badge-paused'}`} style={{ fontSize: '10px' }}>
                          {r.is_available ? 'AVAILABLE' : 'INACCESSIBLE'}
                        </span>
                        <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px' }}>
                          {r.file_count || 0} files
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: Secure Local Directory Browser */}
          {activeTab === 'browse' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span className="form-label" style={{ marginBottom: 0 }}>Secure Filesystem Navigator</span>
                {browseData?.parent_path && (
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => loadBrowse(browseData.parent_path)}
                    disabled={loadingBrowse}
                  >
                    ▲ Parent Directory
                  </button>
                )}
              </div>

              {/* Current Path Bar */}
              <div style={{ padding: '6px 10px', background: 'var(--bg-card)', borderRadius: '4px', border: '1px solid var(--border)', fontSize: '12px', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Location:</span>
                <Mono style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {browsePath || 'Top Allowed Roots'}
                </Mono>
                {browsePath && (
                  <button
                    className="btn btn-primary btn-sm"
                    style={{ fontSize: '11px', padding: '2px 8px' }}
                    onClick={() => {
                      setCandidatePath(browsePath);
                      handleValidate(browsePath);
                      setActiveTab('path');
                    }}
                  >
                    Select This Directory
                  </button>
                )}
              </div>

              {browseError && (
                <div style={{ padding: '8px 12px', background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '6px', color: '#f87171', fontSize: '12px', marginBottom: '10px' }}>
                  ⚠️ {browseError}
                </div>
              )}

              {loadingBrowse ? (
                <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                  Browsing directory...
                </div>
              ) : (
                <div style={{ maxHeight: '200px', overflowY: 'auto', border: '1px solid var(--border)', borderRadius: '6px' }}>
                  {(browseData?.entries || []).length === 0 ? (
                    <div style={{ padding: '16px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
                      No subdirectories found in this location.
                    </div>
                  ) : (
                    browseData.entries.map(e => (
                      <div
                        key={e.path}
                        onClick={() => {
                          if (e.is_dir) {
                            loadBrowse(e.path);
                          }
                        }}
                        style={{
                          padding: '8px 12px',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          borderBottom: '1px solid var(--border)',
                          cursor: e.is_dir ? 'pointer' : 'default',
                          background: 'var(--bg-panel)',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span>{e.is_dir ? '📁' : '📄'}</span>
                          <span style={{ fontSize: '13px', fontWeight: e.is_dir ? 500 : 400 }}>{e.name}</span>
                          {e.is_repository && (
                            <span className="badge badge-running" style={{ fontSize: '9px', padding: '2px 6px' }}>
                              Git Repo
                            </span>
                          )}
                        </div>
                        {e.is_dir && (
                          <button
                            className="btn btn-secondary btn-sm"
                            style={{ fontSize: '10px', padding: '2px 6px' }}
                            onClick={(ev) => {
                              ev.stopPropagation();
                              setCandidatePath(e.path);
                              handleValidate(e.path);
                              setActiveTab('path');
                            }}
                          >
                            Select
                          </button>
                        )}
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          )}

          {/* Validation Feedback */}
          {validationError && (
            <div style={{ padding: '10px 14px', background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '6px', color: '#f87171', fontSize: '13px' }}>
              <strong>Validation Failed:</strong> {validationError}
            </div>
          )}

          {selectSuccess && (
            <div style={{ padding: '10px 14px', background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: '6px', color: '#34d399', fontSize: '13px' }}>
              ✓ {selectSuccess}
            </div>
          )}

          {validationResult && (
            <div style={{ padding: '12px 14px', background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.3)', borderRadius: '6px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontWeight: 600, color: 'var(--accent-cyan)', fontSize: '14px' }}>
                  ✓ Repository Validated Successfully
                </span>
                <span className="badge badge-success">READY TO TARGET</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '8px', fontSize: '12px' }}>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Name:</span>{' '}
                  <strong>{validationResult.repository_name}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Family:</span>{' '}
                  <span className="badge badge-primary" style={{ fontSize: '10px' }}>{validationResult.repository_family}</span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Files:</span>{' '}
                  <strong>{validationResult.file_count?.toLocaleString()}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Git Revision:</span>{' '}
                  <Mono>{validationResult.git_revision ? validationResult.git_revision.substring(0, 8) : 'N/A'}</Mono>
                </div>
              </div>
              {(validationResult.languages || []).length > 0 && (
                <div style={{ marginTop: '8px', display: 'flex', gap: '4px', flexWrap: 'wrap', alignItems: 'center' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Languages:</span>
                  {validationResult.languages.map(l => (
                    <span key={l} className="cap-tag" style={{ fontSize: '10px' }}>{l}</span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Selection is authoritative and persists to Run context
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={selecting}>
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleConfirmSelect}
              disabled={selecting || !validationResult?.valid}
              id="btn-confirm-target-repo"
            >
              {selecting ? 'Setting Repository…' : '✓ Set as Target Repository'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default RepositorySelectorModal;
