/**
 * shared.jsx — Shared utilities, constants, and micro-components used across
 * the Phase 9.3 analyst console.
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
  return id.length > 16 ? id.slice(0, 10) + '…' : id
}

export function Mono({ children, style }) {
  return <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', ...style }}>{children}</span>
}

export const STATUS_COLOR = {
  PENDING:      '#94a3b8',
  QUEUED:       '#94a3b8',
  RUNNING:      '#38bdf8',
  IN_PROGRESS:  '#38bdf8',
  ANALYZING:    '#38bdf8',
  COMPLETED:    '#4ade80',
  DONE:         '#4ade80',
  FAILED:       '#f87171',
  ERROR:        '#f87171',
  BLOCKED:      '#fb923c',
  SKIPPED:      '#a78bfa',
  AVAILABLE:    '#4ade80',
  IN_USE:       '#38bdf8',
  DISABLED:     '#64748b',
  VALIDATED:    '#4ade80',
  REPRODUCED:   '#a3e635',
  DRAFT:        '#fbbf24',
  REJECTED:     '#f87171',
  INCONCLUSIVE: '#94a3b8',
}

export const SEVERITY_COLOR = {
  CRITICAL: '#ef4444',
  HIGH:     '#f97316',
  MEDIUM:   '#eab308',
  LOW:      '#22c55e',
  INFO:     '#3b82f6',
}

export function StatusPill({ status, style }) {
  const color = STATUS_COLOR[status?.toUpperCase()] || '#94a3b8'
  return (
    <span style={{
      display:'inline-flex',alignItems:'center',gap:4,
      padding:'2px 8px',borderRadius:999,fontSize:10,fontWeight:600,
      background:color+'22',color,border:`1px solid ${color}55`,
      letterSpacing:'0.04em',textTransform:'uppercase', ...style,
    }}>
      <span style={{width:6,height:6,borderRadius:'50%',background:color,flexShrink:0}}/>
      {status||'unknown'}
    </span>
  )
}

export function SeverityBadge({ severity }) {
  const c = SEVERITY_COLOR[severity?.toUpperCase()] || '#94a3b8'
  if (!severity) return null
  return (
    <span style={{
      padding:'1px 6px',borderRadius:4,fontSize:10,fontWeight:700,
      background:c+'22',color:c,border:`1px solid ${c}44`,
    }}>{severity}</span>
  )
}

export function Spinner({ size = 20 }) {
  return (
    <div style={{
      width:size,height:size,border:`2px solid var(--border)`,
      borderTopColor:'var(--accent-blue)',borderRadius:'50%',
      animation:'spin 0.7s linear infinite',display:'inline-block',
    }}/>
  )
}

export function EmptyState({ icon='🔍', title='No data', subtitle='' }) {
  return (
    <div style={{
      display:'flex',flexDirection:'column',alignItems:'center',
      justifyContent:'center',padding:'48px 24px',gap:12,
      color:'var(--text-muted)',textAlign:'center',
    }}>
      <div style={{fontSize:40}}>{icon}</div>
      <div style={{fontSize:14,fontWeight:600,color:'var(--text-secondary)'}}>{title}</div>
      {subtitle&&<div style={{fontSize:12,maxWidth:320,lineHeight:1.6}}>{subtitle}</div>}
    </div>
  )
}

export function SectionHeader({ title, subtitle, actions }) {
  return (
    <div style={{
      display:'flex',justifyContent:'space-between',alignItems:'flex-start',
      gap:12,marginBottom:16,flexWrap:'wrap',
    }}>
      <div>
        <div className="page-title">{title}</div>
        {subtitle&&<div className="page-subtitle">{subtitle}</div>}
      </div>
      {actions&&<div style={{display:'flex',gap:8,alignItems:'center',flexWrap:'wrap'}}>{actions}</div>}
    </div>
  )
}

export function Btn({ onClick, children, variant='secondary', size='sm', disabled, style }) {
  const variants = {
    primary:  { background:'var(--accent-blue)',color:'#fff',border:'none' },
    secondary:{ background:'var(--bg-elevated)',color:'var(--text-secondary)',border:'1px solid var(--border)' },
    danger:   { background:'#ef444422',color:'#f87171',border:'1px solid #ef444444' },
    ghost:    { background:'transparent',color:'var(--text-muted)',border:'1px solid var(--border)' },
    success:  { background:'#4ade8022',color:'#4ade80',border:'1px solid #4ade8044' },
    warning:  { background:'#f59e0b22',color:'#fbbf24',border:'1px solid #f59e0b44' },
  }
  const sizes = {
    xs: { padding:'3px 8px',fontSize:10,borderRadius:5 },
    sm: { padding:'5px 12px',fontSize:11,borderRadius:6 },
    md: { padding:'7px 16px',fontSize:12,borderRadius:7 },
  }
  return (
    <button onClick={onClick} disabled={disabled} style={{
      ...variants[variant],...sizes[size],
      fontWeight:600,cursor:disabled?'not-allowed':'pointer',
      opacity:disabled?0.5:1,transition:'all .15s',
      ...style,
    }}>{children}</button>
  )
}

export function Card({ children, style, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        background:'var(--bg-panel)',border:'1px solid var(--border)',
        borderRadius:10,padding:16,...style,
        cursor:onClick?'pointer':'default',
      }}
    >{children}</div>
  )
}
