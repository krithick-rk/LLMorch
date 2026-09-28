/**
 * shared.jsx — Shared utilities, constants, and micro-components
 * Enterprise EDA Workstation styling.
 */

export function fmt(dt) {
  if (!dt) return '—'
  try { return new Date(dt).toLocaleString() } catch { return dt }
}

export function fmtDuration(ms) {
  if (ms == null) return '—'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms/1000).toFixed(1)}s`
  return `${Math.floor(ms/60000)}m ${Math.floor((ms%60000)/1000)}s`
}

export function shortId(id) {
  if (!id) return '—'
  return id.length > 18 ? id.slice(0, 12) + '…' : id
}

export function fmtElapsed(seconds) {
  if (seconds == null || isNaN(seconds)) return '0:00'
  const sTotal = Math.max(0, Math.floor(seconds))
  const h = Math.floor(sTotal / 3600)
  const m = Math.floor((sTotal % 3600) / 60)
  const s = Math.floor(sTotal % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export function StatusBadge({ status }) {
  const s = (status || 'unknown').toLowerCase().replace(/ /g, '_')
  return <span className={`badge badge-${s}`}>{status || '—'}</span>
}

export function Mono({ children, style }) {
  return <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-code)', ...style }}>{children}</span>
}

export const STATUS_STYLE = {
  RUNNING:      { bg: 'var(--blue-bg)', text: 'var(--blue)', border: 'var(--blue-border)' },
  IN_PROGRESS:  { bg: 'var(--blue-bg)', text: 'var(--blue)', border: 'var(--blue-border)' },
  ANALYZING:    { bg: 'var(--blue-bg)', text: 'var(--blue)', border: 'var(--blue-border)' },
  COMPLETED:    { bg: 'var(--green-bg)', text: 'var(--green)', border: 'var(--green-border)' },
  DONE:         { bg: 'var(--green-bg)', text: 'var(--green)', border: 'var(--green-border)' },
  COVERED:      { bg: 'var(--green-bg)', text: 'var(--green)', border: 'var(--green-border)' },
  READY:        { bg: 'var(--green-bg)', text: 'var(--green)', border: 'var(--green-border)' },
  AVAILABLE:    { bg: 'var(--green-bg)', text: 'var(--green)', border: 'var(--green-border)' },
  PAUSED:       { bg: 'var(--amber-bg)', text: 'var(--amber)', border: 'var(--amber-border)' },
  PARTIAL:      { bg: 'var(--amber-bg)', text: 'var(--amber)', border: 'var(--amber-border)' },
  PENDING:      { bg: 'var(--amber-bg)', text: 'var(--amber)', border: 'var(--amber-border)' },
  FAILED:       { bg: 'var(--red-bg)', text: 'var(--red)', border: 'var(--red-border)' },
  ERROR:        { bg: 'var(--red-bg)', text: 'var(--red)', border: 'var(--red-border)' },
  BLOCKED:      { bg: 'var(--red-bg)', text: 'var(--red)', border: 'var(--red-border)' },
  STOPPED:      { bg: 'var(--gray-bg)', text: 'var(--gray)', border: 'var(--gray-border)' },
  DISABLED:     { bg: 'var(--gray-bg)', text: 'var(--gray)', border: 'var(--gray-border)' },
  UNKNOWN:      { bg: 'var(--gray-bg)', text: 'var(--gray)', border: 'var(--gray-border)' },
}

export const STATUS_COLOR = {
  PENDING:      '#57606a',
  QUEUED:       '#57606a',
  RUNNING:      '#0969da',
  IN_PROGRESS:  '#0969da',
  ANALYZING:    '#0969da',
  COMPLETED:    '#1a7f37',
  DONE:         '#1a7f37',
  FAILED:       '#cf222e',
  ERROR:        '#cf222e',
  BLOCKED:      '#9a6700',
  SKIPPED:      '#8250df',
  AVAILABLE:    '#1a7f37',
  IN_USE:       '#0969da',
  DISABLED:     '#57606a',
  VALIDATED:    '#1a7f37',
  REPRODUCED:   '#8250df',
  DRAFT:        '#9a6700',
  REJECTED:     '#cf222e',
  INCONCLUSIVE: '#57606a',
}

export function StatusPill({ status, style }) {
  const st = (status || 'UNKNOWN').toUpperCase()
  const conf = STATUS_STYLE[st] || STATUS_STYLE.UNKNOWN
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '1px 6px', borderRadius: 'var(--radius-sm)', fontSize: 10, fontWeight: 600,
      background: conf.bg, color: conf.text, border: `1px solid ${conf.border}`,
      letterSpacing: '0.03em', textTransform: 'uppercase', fontFamily: 'var(--font-mono)', ...style,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: conf.text, flexShrink: 0 }} />
      {status || 'UNKNOWN'}
    </span>
  )
}

export const SEVERITY_STYLE = {
  CRITICAL: { bg: '#ffebe9', text: '#cf222e', border: '#ff8182' },
  HIGH:     { bg: '#ffebe9', text: '#cf222e', border: '#ff8182' },
  MEDIUM:   { bg: '#fff8c5', text: '#9a6700', border: '#d4a72c' },
  LOW:      { bg: '#dafbe1', text: '#1a7f37', border: '#4ac26b' },
  INFO:     { bg: '#ddf4ff', text: '#0969da', border: '#54aeff' },
}

export const SEVERITY_COLOR = {
  CRITICAL: '#cf222e',
  HIGH:     '#cf222e',
  MEDIUM:   '#9a6700',
  LOW:      '#1a7f37',
  INFO:     '#0969da',
}

export function SeverityBadge({ severity }) {
  if (!severity) return null
  const s = severity.toUpperCase()
  const conf = SEVERITY_STYLE[s] || { bg: '#f6f8fa', text: '#57606a', border: '#d0d7de' }
  return (
    <span style={{
      padding: '1px 5px', borderRadius: 'var(--radius-sm)', fontSize: 10, fontWeight: 700,
      background: conf.bg, color: conf.text, border: `1px solid ${conf.border}`,
      fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', textTransform: 'uppercase'
    }}>{severity}</span>
  )
}

export function Spinner({ size = 16 }) {
  return (
    <div style={{
      width: size, height: size, border: `2px solid var(--border)`,
      borderTopColor: 'var(--blue)', borderRadius: '50%',
      animation: 'spin 0.6s linear infinite', display: 'inline-block',
    }} />
  )
}

export function EmptyState({ icon = '🔍', title = 'No data', subtitle = '' }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: '36px 16px', gap: 8,
      color: 'var(--text-muted)', textAlign: 'center', background: 'var(--bg-surface)',
      border: '1px dashed var(--border)', borderRadius: 'var(--radius)'
    }}>
      <div style={{ fontSize: 24, opacity: 0.6 }}>{icon}</div>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{title}</div>
      {subtitle && <div style={{ fontSize: 11, maxWidth: 360, lineHeight: 1.5, color: 'var(--text-secondary)' }}>{subtitle}</div>}
    </div>
  )
}

export function SectionHeader({ title, subtitle, actions }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
      gap: 12, marginBottom: 12, flexWrap: 'wrap',
    }}>
      <div>
        <div className="page-title">{title}</div>
        {subtitle && <div className="page-subtitle">{subtitle}</div>}
      </div>
      {actions && <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>{actions}</div>}
    </div>
  )
}

export function Btn({ onClick, children, variant = 'secondary', size = 'sm', disabled, style, id }) {
  const cls = `btn btn-${variant} btn-${size}`
  return (
    <button id={id} className={cls} onClick={onClick} disabled={disabled} style={style}>
      {children}
    </button>
  )
}

export function Card({ children, style, onClick, className }) {
  return (
    <div
      onClick={onClick}
      className={`panel ${className || ''}`}
      style={{
        padding: 12,
        cursor: onClick ? 'pointer' : 'default',
        ...style,
      }}
    >{children}</div>
  )
}
