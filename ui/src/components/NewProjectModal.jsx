/**
 * NewProjectModal.jsx — Professional Project Creation Modal
 * Section 4:
 * - Project Name (Optional — defaults to "Untitled Project 001", etc.)
 * - Target directory (/path/to/repository, e.g. /tmp/test)
 * - Deterministic intake performed immediately on creation
 */

import { useState } from 'react'
import api from '../api'

export default function NewProjectModal({ isOpen, onClose, onProjectCreated }) {
  const [projectName, setProjectName] = useState('')
  const [targetDir, setTargetDir] = useState('/home/hackdac/Desktop/intern/LLMorch')
  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  if (!isOpen) return null

  const handleCreate = async () => {
    try {
      setLoading(true)
      setErrorMsg('')
      const created = await api.createProject({
        name: projectName.trim() || null,
        target_directory: targetDir.trim() || '/tmp/test'
      })
      if (onProjectCreated) onProjectCreated(created)
      onClose()
    } catch (err) {
      setErrorMsg(err.message || 'Failed to create project')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose} style={{ zIndex: 1100 }}>
      <div
        className="modal-content"
        onClick={e => e.stopPropagation()}
        style={{
          width: 540,
          background: 'var(--bg-surface)',
          borderRadius: 4,
          boxShadow: '0 8px 30px rgba(0,0,0,0.18)',
          border: '1px solid var(--border)'
        }}
      >
        <div className="modal-header" style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-bright)' }}>
              Create New Project Workspace
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
              Isolated environment for repository intake, verification plans, tasks, and findings
            </div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>

        <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {errorMsg && (
            <div style={{ padding: '8px 12px', background: 'var(--red-bg)', color: 'var(--red)', fontSize: 12, borderRadius: 3 }}>
              ⚠ {errorMsg}
            </div>
          )}

          <div className="form-group">
            <label className="form-label" style={{ fontSize: 13 }}>
              Project Name <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>(Optional)</span>
            </label>
            <input
              type="text"
              className="form-control"
              placeholder="e.g. OpenTitan Security Review (Leave blank for Untitled Project)"
              value={projectName}
              onChange={e => setProjectName(e.target.value)}
              style={{ fontSize: 13 }}
              autoFocus
            />
            <div className="form-hint" style={{ fontSize: 11 }}>
              If left blank, LLMorch automatically generates an identifier like Untitled Project 001.
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" style={{ fontSize: 13 }}>
              Target Directory *
            </label>
            <input
              type="text"
              className="form-control mono"
              placeholder="/home/user/repo or /tmp/test"
              value={targetDir}
              onChange={e => setTargetDir(e.target.value)}
              style={{ fontSize: 13 }}
            />
            <div className="form-hint" style={{ fontSize: 11 }}>
              Filesystem directory containing RTL, firmware, or test scripts.
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setTargetDir('/home/hackdac/Desktop/intern/LLMorch')}
            >
              Default (LLMorch)
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setTargetDir('/tmp/test')}
            >
              Test Directory (/tmp/test)
            </button>
          </div>
        </div>

        <div className="modal-footer" style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button className="btn btn-secondary btn-md" onClick={onClose} disabled={loading}>
            Cancel
          </button>
          <button
            id="btn-confirm-create-project"
            className="btn btn-primary btn-md"
            onClick={handleCreate}
            disabled={loading}
            style={{ fontWeight: 600, minWidth: 120 }}
          >
            {loading ? 'Initializing...' : 'Create Project'}
          </button>
        </div>
      </div>
    </div>
  )
}
