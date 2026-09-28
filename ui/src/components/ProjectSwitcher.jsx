/**
 * ProjectSwitcher.jsx — Professional Engineering Project Switcher
 * Section 7:
 * - Top-left / top-bar dropdown
 * - Displays active project name with dropdown arrow
 * - Lists existing projects with status, last activity, repo path
 * - Quick triggers for "Create New Project" and "Open Existing Project"
 */

import { useState, useEffect, useRef } from 'react'
import api from '../api'

export default function ProjectSwitcher({ activeProject, onProjectSelected, onOpenNewProject }) {
  const [isOpen, setIsOpen] = useState(false)
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(false)
  const dropdownRef = useRef(null)

  const loadProjects = async () => {
    try {
      setLoading(true)
      const res = await api.projects().catch(() => ({ projects: [] }))
      setProjects(res.projects || [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadProjects()
  }, [activeProject])

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSelect = async (p) => {
    try {
      await api.activateProject(p.project_id).catch(() => null)
      if (onProjectSelected) onProjectSelected(p)
      setIsOpen(false)
    } catch (err) {
      console.error('Failed to activate project:', err)
    }
  }

  return (
    <div ref={dropdownRef} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        id="btn-project-switcher"
        onClick={() => {
          setIsOpen(!isOpen)
          if (!isOpen) loadProjects()
        }}
        className="btn btn-secondary btn-sm"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          background: 'var(--bg-elevated)',
          borderColor: 'var(--border)',
          fontWeight: 600,
          fontSize: 13,
          padding: '4px 10px',
          color: 'var(--text-primary)'
        }}
        title="Switch active isolated project workspace"
      >
        <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>Project:</span>
        <span style={{ color: 'var(--text-bright)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {activeProject?.name || 'Untitled Project 001'}
        </span>
        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>▾</span>
      </button>

      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: 0,
            width: 380,
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            borderRadius: 4,
            boxShadow: '0 6px 24px rgba(0,0,0,0.14)',
            zIndex: 1000,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
          }}
        >
          {/* Header */}
          <div style={{ padding: '8px 12px', background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border-dim)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Isolated Project Workspaces
            </span>
            <span className="mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>
              {projects.length} Total
            </span>
          </div>

          {/* Project List */}
          <div style={{ maxHeight: 260, overflowY: 'auto' }}>
            {projects.map(p => {
              const isActive = p.project_id === activeProject?.project_id
              return (
                <div
                  key={p.project_id}
                  onClick={() => handleSelect(p)}
                  style={{
                    padding: '9px 12px',
                    borderBottom: '1px solid var(--border-dim)',
                    cursor: 'pointer',
                    background: isActive ? 'var(--blue-bg)' : '#ffffff',
                    borderLeft: isActive ? '3px solid var(--blue)' : '3px solid transparent',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 2
                  }}
                  onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'var(--bg-elevated)' }}
                  onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = '#ffffff' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 13, fontWeight: isActive ? 700 : 600, color: isActive ? 'var(--blue)' : 'var(--text-primary)' }}>
                      {p.name}
                    </span>
                    <span className={`badge badge-${(p.status || 'READY').toLowerCase()}`} style={{ fontSize: 10 }}>
                      {p.status || 'READY'}
                    </span>
                  </div>
                  <div className="mono text-muted truncate" style={{ fontSize: 11 }}>
                    {p.target_directory}
                  </div>
                  {p.metadata?.classification && (
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                      {p.metadata.classification}
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* Actions Footer */}
          <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)', background: 'var(--bg-surface)', display: 'flex', gap: 8 }}>
            <button
              id="btn-new-project-trigger"
              className="btn btn-primary btn-sm"
              style={{ flex: 1, fontSize: 12 }}
              onClick={() => {
                setIsOpen(false)
                if (onOpenNewProject) onOpenNewProject()
              }}
            >
              + Create New Project
            </button>
            <button
              className="btn btn-secondary btn-sm"
              style={{ fontSize: 12 }}
              onClick={() => {
                setIsOpen(false)
                if (onOpenNewProject) onOpenNewProject()
              }}
            >
              📂 Open Existing
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
