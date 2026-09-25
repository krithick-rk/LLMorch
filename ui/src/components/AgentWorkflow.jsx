/**
 * AgentWorkflow.jsx  — Phase 9.3
 * Primary workflow visualization: Orchestrator → Agent → Task → Tool → Evidence
 */
import { useState, useEffect, useCallback } from 'react'
import api from '../api'

// ── helpers ───────────────────────────────────────────────────────────────────

function fmt(dt) {
  if (!dt) return '—'
  try { return new Date(dt).toLocaleString() } catch { return dt }
}
function shortId(id) {
  if (!id) return '—'
  return id.length > 16 ? id.slice(0, 10) + '…' : id
}
function Mono({ children, style }) {
  return <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', ...style }}>{children}</span>
}

const STATUS_COLOR = {
  PENDING:   '#94a3b8',
  RUNNING:   '#38bdf8',
  COMPLETED: '#4ade80',
  FAILED:    '#f87171',
  BLOCKED:   '#fb923c',
  SKIPPED:   '#a78bfa',
}

const SEVERITY_COLOR = {
  CRITICAL: '#ef4444',
  HIGH:     '#f97316',
  MEDIUM:   '#eab308',
  LOW:      '#22c55e',
  INFO:     '#3b82f6',
}

function StatusPill({ status }) {
  const color = STATUS_COLOR[status?.toUpperCase()] || '#94a3b8'
  return (
    <span style={{
      display:'inline-flex',alignItems:'center',gap:4,
      padding:'2px 8px',borderRadius:999,fontSize:10,fontWeight:600,
      background:color+'22',color,border:`1px solid ${color}55`,
      letterSpacing:'0.04em',textTransform:'uppercase',
    }}>
      <span style={{width:6,height:6,borderRadius:'50%',background:color,display:'inline-block'}}/>
      {status||'unknown'}
    </span>
  )
}

function btnStyle(variant, disabled) {
  const base = {
    border:'none',borderRadius:6,padding:'6px 14px',fontSize:11,
    fontWeight:600,cursor:disabled?'not-allowed':'pointer',
    opacity:disabled?0.5:1,transition:'opacity .15s',
  }
  const variants = {
    blue:  {background:'#2563eb22',color:'#60a5fa',border:'1px solid #2563eb44'},
    amber: {background:'#d9770622',color:'#fbbf24',border:'1px solid #d9770644'},
    green: {background:'#16a34a22',color:'#4ade80',border:'1px solid #16a34a44'},
    ghost: {background:'var(--bg-elevated)',color:'var(--text-muted)',border:'1px solid var(--border)'},
  }
  return {...base,...variants[variant]}
}

function agentPillStyle(active) {
  return {
    padding:'4px 12px',borderRadius:999,border:'1px solid var(--border)',
    fontSize:11,fontWeight:600,cursor:'pointer',whiteSpace:'nowrap',
    background:active?'var(--accent-blue)':'var(--bg-elevated)',
    color:active?'#fff':'var(--text-secondary)',transition:'all .15s',
  }
}

// ── Analyst Instruction Panel ─────────────────────────────────────────────────

function AnalystInstructionPanel({ taskId, attempts, onSubmit }) {
  const [text, setText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const submit = async () => {
    if (!text.trim()) return
    setSubmitting(true); setError(null)
    try {
      await api.submitAnalystInstruction({ task_id: taskId, instruction: text.trim() })
      setText(''); onSubmit && onSubmit()
    } catch (e) { setError(e.message) }
    finally { setSubmitting(false) }
  }

  return (
    <div style={{display:'flex',flexDirection:'column',gap:8}}>
      <div style={{fontSize:11,color:'var(--text-muted)',fontWeight:600,letterSpacing:'0.06em',textTransform:'uppercase'}}>
        Analyst Instruction
      </div>
      <div style={{fontSize:11,color:'var(--text-muted)',lineHeight:1.6}}>
        Submitting an instruction creates a new task attempt (lineage preserved).
        Previous attempt output remains as evidence.
      </div>
      <textarea
        value={text}
        onChange={e=>setText(e.target.value)}
        placeholder="e.g. Focus on the AXI4-Lite write-response path. Check if valid is held high without checking ready…"
        style={{
          width:'100%',minHeight:80,resize:'vertical',
          background:'var(--bg-base)',border:'1px solid var(--border)',
          borderRadius:6,padding:'8px 10px',fontSize:12,
          color:'var(--text-primary)',fontFamily:'inherit',lineHeight:1.5,
          boxSizing:'border-box',
        }}
        onKeyDown={e=>{if(e.ctrlKey&&e.key==='Enter')submit()}}
      />
      {error&&<div style={{color:'#f87171',fontSize:11}}>⚠ {error}</div>}
      <button onClick={submit} disabled={submitting||!text.trim()} style={{
        alignSelf:'flex-end',
        background:submitting?'var(--bg-elevated)':'var(--accent-blue)',
        color:'#fff',border:'none',borderRadius:6,padding:'6px 16px',
        fontSize:12,fontWeight:600,cursor:submitting?'not-allowed':'pointer',
        opacity:(submitting||!text.trim())?0.5:1,transition:'opacity .15s',
      }}>
        {submitting?'Submitting…':'⏎ Submit  (Ctrl+↩)'}
      </button>

      {attempts&&attempts.length>0&&(
        <div style={{marginTop:8}}>
          <div style={{fontSize:11,fontWeight:600,color:'var(--text-muted)',textTransform:'uppercase',letterSpacing:'0.06em',marginBottom:6}}>
            Attempt Lineage ({attempts.length})
          </div>
          <div style={{display:'flex',flexDirection:'column',gap:4,maxHeight:200,overflowY:'auto'}}>
            {attempts.map((a,i)=>(
              <div key={a.attempt_id||i} style={{
                background:'var(--bg-base)',borderRadius:5,padding:'6px 10px',
                border:'1px solid var(--border)',fontSize:11,
              }}>
                <div style={{display:'flex',justifyContent:'space-between',marginBottom:3}}>
                  <span style={{fontWeight:600,color:'var(--text-secondary)'}}>Attempt #{a.attempt_number||(i+1)}</span>
                  <StatusPill status={a.status}/>
                </div>
                {a.instruction_text&&(
                  <div style={{color:'var(--text-muted)',lineHeight:1.5,fontStyle:'italic'}}>
                    "{a.instruction_text.slice(0,120)}{a.instruction_text.length>120?'…':''}"
                  </div>
                )}
                <div style={{color:'var(--text-muted)',marginTop:4,fontSize:10}}>{fmt(a.started_at)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── PoC Lifecycle Panel ───────────────────────────────────────────────────────

function PoCLifecyclePanel({ finding, onRefresh }) {
  const [poc, setPoc] = useState(null)
  const [loading, setLoading] = useState(false)
  const [validating, setValidating] = useState(false)
  const [error, setError] = useState(null)

  const generatePoC = async () => {
    setLoading(true); setError(null)
    try { const r=await api.generatePoC({finding_id:finding.finding_id}); setPoc(r) }
    catch(e){setError(e.message)} finally{setLoading(false)}
  }
  const executePoC = async () => {
    setLoading(true); setError(null)
    try { const r=await api.executePoC({reproducer_id:poc.reproducer_id}); setPoc(r) }
    catch(e){setError(e.message)} finally{setLoading(false)}
  }
  const validatePoC = async () => {
    setValidating(true); setError(null)
    try { const r=await api.validatePoC({reproducer_id:poc.reproducer_id}); setPoc(r); onRefresh&&onRefresh() }
    catch(e){setError(e.message)} finally{setValidating(false)}
  }

  const STATE_STEP = {DRAFT:0,REPRODUCED:1,VALIDATED:2,REJECTED:-1}
  const step = STATE_STEP[poc?.state]??-2

  const StepDot = ({label,n,active,done,failed})=>(
    <div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:4,flex:1}}>
      <div style={{
        width:28,height:28,borderRadius:'50%',display:'flex',alignItems:'center',justifyContent:'center',
        fontSize:12,fontWeight:700,
        background:failed?'#ef444422':done?'#4ade8022':active?'#38bdf822':'var(--bg-base)',
        color:failed?'#ef4444':done?'#4ade80':active?'#38bdf8':'var(--text-muted)',
        border:`2px solid ${failed?'#ef4444':done?'#4ade80':active?'#38bdf8':'var(--border)'}`,
        transition:'all .2s',
      }}>{done&&!failed?'✓':failed?'✗':n}</div>
      <span style={{fontSize:10,color:active||done?'var(--text-secondary)':'var(--text-muted)',textAlign:'center'}}>{label}</span>
    </div>
  )

  return (
    <div style={{display:'flex',flexDirection:'column',gap:10}}>
      <div style={{fontSize:11,fontWeight:600,color:'var(--text-muted)',textTransform:'uppercase',letterSpacing:'0.06em'}}>
        PoC / Reproducer Lifecycle
      </div>
      <div style={{
        background:'#f59e0b11',border:'1px solid #f59e0b44',borderRadius:6,padding:'8px 10px',
        fontSize:11,color:'#f59e0b',lineHeight:1.6,
      }}>
        ⚠ Agent-generated PoC is a <strong>DRAFT</strong>. Only Validator confirmation produces
        authoritative VALIDATED status. Sandbox execution is required before validation.
      </div>

      <div style={{display:'flex',alignItems:'flex-start',gap:0,padding:'8px 0'}}>
        <StepDot label="Generate" n={1} active={!poc} done={step>=0}/>
        <div style={{flex:'none',width:32,height:2,background:step>=1?'#4ade80':'var(--border)',marginTop:14,transition:'background .3s'}}/>
        <StepDot label="Execute" n={2} active={step===0} done={step>=1}/>
        <div style={{flex:'none',width:32,height:2,background:step>=2?'#4ade80':'var(--border)',marginTop:14,transition:'background .3s'}}/>
        <StepDot label="Validate" n={3} active={step===1} done={step>=2} failed={poc?.state==='REJECTED'}/>
      </div>

      {poc&&(
        <div style={{
          background:'var(--bg-base)',border:'1px solid var(--border)',
          borderRadius:6,padding:10,fontSize:11,fontFamily:'var(--font-mono)',
          maxHeight:160,overflowY:'auto',color:'var(--text-secondary)',lineHeight:1.6,
          whiteSpace:'pre-wrap',wordBreak:'break-all',
        }}>{poc.code||poc.content||'(no code available)'}</div>
      )}
      {error&&<div style={{color:'#f87171',fontSize:11}}>⚠ {error}</div>}

      <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
        {!poc&&<button onClick={generatePoC} disabled={loading} style={btnStyle('blue',loading)}>{loading?'…':'⚡ Generate PoC'}</button>}
        {poc&&step===0&&<button onClick={executePoC} disabled={loading} style={btnStyle('amber',loading)}>{loading?'…':'▶ Execute in Sandbox'}</button>}
        {poc&&step===1&&<button onClick={validatePoC} disabled={validating} style={btnStyle('green',validating)}>{validating?'…':'✓ Request Validation'}</button>}
        {poc&&<button onClick={generatePoC} disabled={loading} style={btnStyle('ghost',loading)}>↺ Regenerate</button>}
      </div>

      {poc&&(
        <div style={{display:'flex',justifyContent:'space-between',fontSize:10,color:'var(--text-muted)'}}>
          <span>State: <strong style={{color:step>=2?'#4ade80':poc?.state==='REJECTED'?'#f87171':'var(--text-secondary)'}}>{poc.state}</strong></span>
          <span>v{poc.version||1}</span>
          <span>ID: <Mono>{shortId(poc.reproducer_id)}</Mono></span>
        </div>
      )}
    </div>
  )
}

// ── Tool Feed ─────────────────────────────────────────────────────────────────

function ToolFeed({ tools }) {
  if(!tools||tools.length===0) return (
    <div style={{color:'var(--text-muted)',fontSize:12,padding:'8px 0'}}>No tool executions recorded yet.</div>
  )
  return (
    <div style={{display:'flex',flexDirection:'column',gap:4,maxHeight:200,overflowY:'auto'}}>
      {tools.map((t,i)=>(
        <div key={t.execution_id||i} style={{
          background:'var(--bg-base)',borderRadius:5,padding:'6px 10px',
          border:'1px solid var(--border)',fontSize:11,display:'flex',alignItems:'flex-start',gap:8,
        }}>
          <span style={{fontSize:16,flexShrink:0}}>🔧</span>
          <div style={{flex:1,minWidth:0}}>
            <div style={{fontWeight:600,color:'var(--text-secondary)'}}>{t.tool_name||'—'}</div>
            {t.command&&<div style={{color:'var(--text-muted)',fontFamily:'var(--font-mono)',fontSize:10,marginTop:2}}>{t.command.slice(0,120)}</div>}
            <div style={{display:'flex',gap:8,marginTop:4}}>
              <span style={{color:t.exit_code===0?'#4ade80':'#f87171',fontSize:10}}>exit:{t.exit_code??'?'}</span>
              <span style={{color:'var(--text-muted)',fontSize:10}}>{fmt(t.started_at)}</span>
              {t.duration_ms&&<span style={{color:'var(--text-muted)',fontSize:10}}>{t.duration_ms}ms</span>}
            </div>
          </div>
          <div style={{
            flexShrink:0,padding:'2px 6px',borderRadius:4,fontSize:10,
            background:t.exit_code===0?'#4ade8022':'#f8717122',
            color:t.exit_code===0?'#4ade80':'#f87171',
          }}>{t.exit_code===0?'OK':'FAIL'}</div>
        </div>
      ))}
    </div>
  )
}

// ── Agent Workroom ────────────────────────────────────────────────────────────

function AgentWorkroom({ task, finding, agents, onClose, onRefresh }) {
  const [tab, setTab] = useState('overview')
  const [attempts, setAttempts] = useState([])
  const [tools, setTools] = useState([])
  const [loading, setLoading] = useState(false)

  const loadDetails = useCallback(async () => {
    if(!task) return
    setLoading(true)
    try {
      const [att, te] = await Promise.all([
        api.taskAttempts(task.task_id).catch(()=>({items:[]})),
        api.toolExecutions({task_id:task.task_id}).catch(()=>({items:[]})),
      ])
      setAttempts(att.items||[])
      setTools(te.items||[])
    } finally { setLoading(false) }
  }, [task])

  useEffect(()=>{loadDetails()},[loadDetails])

  if(!task) return null
  const assignedAgent = agents?.find(a=>a.agent_id===task.agent_id)
  const TABS = ['overview','instructions','tools','poc']

  return (
    <div style={{
      width:400,flexShrink:0,background:'var(--bg-panel)',
      border:'1px solid var(--border)',borderRadius:10,display:'flex',
      flexDirection:'column',overflow:'hidden',
      boxShadow:'0 0 40px rgba(0,0,0,0.4)',
    }}>
      {/* Header */}
      <div style={{
        padding:'14px 16px',borderBottom:'1px solid var(--border)',
        background:'var(--bg-elevated)',display:'flex',justifyContent:'space-between',alignItems:'flex-start',
      }}>
        <div>
          <div style={{fontSize:13,fontWeight:700,color:'var(--text-primary)',marginBottom:4}}>🔬 Agent Workroom</div>
          <Mono style={{color:'var(--text-muted)'}}>{shortId(task.task_id)}</Mono>
        </div>
        <button onClick={onClose} style={{background:'none',border:'none',color:'var(--text-muted)',cursor:'pointer',fontSize:16,padding:'0 4px'}}>✕</button>
      </div>

      {/* Task summary */}
      <div style={{padding:'12px 16px',borderBottom:'1px solid var(--border)'}}>
        <div style={{fontSize:13,fontWeight:600,color:'var(--text-primary)',marginBottom:6,lineHeight:1.5}}>
          {task.name||task.task_name||'Unnamed Task'}
        </div>
        <div style={{display:'flex',gap:8,flexWrap:'wrap',alignItems:'center'}}>
          <StatusPill status={task.status}/>
          {assignedAgent&&(
            <span style={{fontSize:10,padding:'2px 8px',borderRadius:999,background:'var(--bg-elevated)',color:'var(--text-secondary)',border:'1px solid var(--border)'}}>
              🤖 {assignedAgent.name||shortId(assignedAgent.agent_id)}
            </span>
          )}
        </div>
        {task.description&&(
          <div style={{marginTop:8,fontSize:11,color:'var(--text-muted)',lineHeight:1.6}}>
            {task.description.slice(0,200)}{task.description.length>200?'…':''}
          </div>
        )}
        {finding&&(
          <div style={{
            marginTop:8,padding:'6px 10px',borderRadius:6,
            background:(SEVERITY_COLOR[finding.severity]||'#3b82f6')+'11',
            border:`1px solid ${(SEVERITY_COLOR[finding.severity]||'#3b82f6')}33`,
            fontSize:11,color:SEVERITY_COLOR[finding.severity]||'#3b82f6',
          }}>
            🎯 {finding.severity||'Finding'}: {(finding.hypothesis||finding.title||'').slice(0,100)}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div style={{display:'flex',borderBottom:'1px solid var(--border)',background:'var(--bg-base)'}}>
        {TABS.map(t=>(
          <button key={t} onClick={()=>setTab(t)} style={{
            flex:1,padding:'8px 4px',border:'none',cursor:'pointer',fontSize:11,fontWeight:600,
            background:tab===t?'var(--bg-panel)':'transparent',
            color:tab===t?'var(--accent-blue)':'var(--text-muted)',
            borderBottom:tab===t?'2px solid var(--accent-blue)':'2px solid transparent',
            textTransform:'uppercase',letterSpacing:'0.04em',transition:'all .15s',
          }}>
            {t==='overview'?'📋 Info':t==='instructions'?'📝 Instruct':t==='tools'?'🔧 Tools':'⚡ PoC'}
          </button>
        ))}
      </div>

      {/* Tab body */}
      <div style={{flex:1,overflowY:'auto',padding:'14px 16px'}}>
        {tab==='overview'&&(
          <div style={{display:'flex',flexDirection:'column',gap:12}}>
            <dl style={{display:'grid',gridTemplateColumns:'110px 1fr',gap:'6px 10px',fontSize:12}}>
              <dt style={{color:'var(--text-muted)'}}>Task ID</dt><dd><Mono>{shortId(task.task_id)}</Mono></dd>
              <dt style={{color:'var(--text-muted)'}}>Status</dt><dd><StatusPill status={task.status}/></dd>
              <dt style={{color:'var(--text-muted)'}}>Agent</dt><dd style={{color:'var(--text-secondary)'}}>{assignedAgent?.name||task.agent_id||'—'}</dd>
              <dt style={{color:'var(--text-muted)'}}>Created</dt><dd style={{color:'var(--text-muted)'}}>{fmt(task.created_at)}</dd>
              <dt style={{color:'var(--text-muted)'}}>Started</dt><dd style={{color:'var(--text-muted)'}}>{fmt(task.started_at)}</dd>
              <dt style={{color:'var(--text-muted)'}}>Attempts</dt><dd style={{color:'var(--text-secondary)'}}>{attempts.length||1}</dd>
            </dl>
            {task.error&&(
              <div style={{background:'#f8717111',border:'1px solid #f8717133',borderRadius:6,padding:'8px 10px',fontSize:11,color:'#f87171'}}>
                ⚠ {task.error}
              </div>
            )}
          </div>
        )}
        {tab==='instructions'&&task?.task_id&&(
          <AnalystInstructionPanel taskId={task.task_id} attempts={attempts} onSubmit={()=>{loadDetails();onRefresh&&onRefresh()}}/>
        )}
        {tab==='tools'&&(loading?<div style={{color:'var(--text-muted)',fontSize:12}}>Loading…</div>:<ToolFeed tools={tools}/>)}
        {tab==='poc'&&finding&&<PoCLifecyclePanel finding={finding} onRefresh={onRefresh}/>}
        {tab==='poc'&&!finding&&(
          <div style={{color:'var(--text-muted)',fontSize:12}}>No finding linked to this task. PoC lifecycle requires an associated finding.</div>
        )}
      </div>
    </div>
  )
}

// ── Workflow Node Card ────────────────────────────────────────────────────────

function WorkflowNode({ task, agents, finding, isSelected, onClick }) {
  const agent = agents?.find(a=>a.agent_id===task.agent_id)
  const color = STATUS_COLOR[task.status?.toUpperCase()]||'#94a3b8'
  const fcolor = finding?(SEVERITY_COLOR[finding.severity]||'#3b82f6'):null

  return (
    <div onClick={()=>onClick(task)} style={{
      minWidth:260,maxWidth:300,background:'var(--bg-panel)',
      border:`1.5px solid ${isSelected?'var(--accent-blue)':'var(--border)'}`,
      borderRadius:10,padding:'12px 14px',cursor:'pointer',
      boxShadow:isSelected?'0 0 0 2px #2563eb44,0 4px 20px rgba(0,0,0,0.3)':'0 2px 8px rgba(0,0,0,0.2)',
      transition:'all .18s',transform:isSelected?'scale(1.02)':'scale(1)',
      position:'relative',overflow:'hidden',
    }}>
      <div style={{position:'absolute',top:0,left:0,right:0,height:3,background:color,borderRadius:'10px 10px 0 0'}}/>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:8,marginTop:2}}>
        <div style={{fontSize:12,fontWeight:700,color:'var(--text-primary)',flex:1,paddingRight:8,lineHeight:1.4}}>
          {task.name||task.task_name||'Task'}
        </div>
        <StatusPill status={task.status}/>
      </div>
      <Mono style={{color:'var(--text-muted)',display:'block',marginBottom:8}}>{shortId(task.task_id)}</Mono>
      {agent&&(
        <div style={{display:'flex',alignItems:'center',gap:6,marginBottom:6}}>
          <span style={{fontSize:14}}>🤖</span>
          <span style={{fontSize:11,color:'var(--text-secondary)'}}>{agent.name||shortId(agent.agent_id)}</span>
          {agent.health==='AVAILABLE'&&<span style={{width:6,height:6,borderRadius:'50%',background:'#4ade80',display:'inline-block'}}/>}
        </div>
      )}
      {finding&&fcolor&&(
        <div style={{
          marginTop:6,padding:'4px 8px',borderRadius:5,fontSize:10,
          background:fcolor+'11',color:fcolor,border:`1px solid ${fcolor}33`,
        }}>
          🎯 {finding.severity||'Finding'}: {(finding.hypothesis||finding.title||'').slice(0,60)}…
        </div>
      )}
    </div>
  )
}

// ── Orchestrator Header ───────────────────────────────────────────────────────

function OrchestratorHeader({ agents, currentRepo, tasks }) {
  const orchestrator = agents?.find(a=>a.role==='orchestrator'||a.name?.toLowerCase().includes('orchestrator'))
  const runningTasks = tasks?.filter(t=>t.status==='RUNNING').length||0
  const totalTasks = tasks?.length||0

  return (
    <div style={{
      background:'var(--bg-elevated)',border:'1px solid var(--border)',
      borderRadius:10,padding:'14px 18px',marginBottom:20,
      display:'flex',alignItems:'center',gap:16,flexWrap:'wrap',
    }}>
      <div style={{
        display:'flex',alignItems:'center',gap:10,padding:'8px 14px',
        background:'#2563eb11',border:'1.5px solid #2563eb44',borderRadius:8,
      }}>
        <span style={{fontSize:20}}>🧠</span>
        <div>
          <div style={{fontSize:12,fontWeight:700,color:'#60a5fa'}}>{orchestrator?.name||'Orchestrator'}</div>
          <div style={{fontSize:10,color:'var(--text-muted)'}}>{orchestrator?(orchestrator.health||'unknown'):'Not assigned'}</div>
        </div>
      </div>
      <div style={{color:'var(--text-muted)',fontSize:12}}>→</div>
      {currentRepo&&(
        <>
          <div style={{
            display:'flex',alignItems:'center',gap:8,padding:'8px 12px',
            background:'var(--bg-base)',border:'1px solid var(--border)',borderRadius:8,
          }}>
            <span style={{fontSize:16}}>🎯</span>
            <div>
              <div style={{fontSize:11,fontWeight:600,color:'var(--text-primary)'}}>
                {currentRepo.name||currentRepo.path?.split('/').pop()||'Target Repository'}
              </div>
              <div style={{fontSize:10,color:'var(--text-muted)',fontFamily:'var(--font-mono)'}}>
                {(currentRepo.path||'').slice(0,40)}
              </div>
            </div>
          </div>
          <div style={{color:'var(--text-muted)',fontSize:12}}>→</div>
        </>
      )}
      <div style={{display:'flex',gap:16,marginLeft:'auto'}}>
        {[{label:'Running',count:runningTasks,color:'#38bdf8'},{label:'Total',count:totalTasks,color:'var(--text-muted)'}].map(({label,count,color})=>(
          <div key={label} style={{textAlign:'center'}}>
            <div style={{fontSize:22,fontWeight:700,color}}>{count}</div>
            <div style={{fontSize:10,color:'var(--text-muted)'}}>{label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Main Page Export ──────────────────────────────────────────────────────────

export function AgentWorkflowPage({ refreshSignal }) {
  const [tasks, setTasks] = useState(null)
  const [agents, setAgents] = useState(null)
  const [findings, setFindings] = useState(null)
  const [currentRepo, setCurrentRepo] = useState(null)
  const [selectedTask, setSelectedTask] = useState(null)
  const [selectedFinding, setSelectedFinding] = useState(null)
  const [filter, setFilter] = useState('ALL')
  const [agentFilter, setAgentFilter] = useState('ALL')

  const load = useCallback(async () => {
    const [t, a, f, r] = await Promise.all([
      api.tasks({limit:200}),
      api.agents({limit:50}),
      api.findings({limit:200}),
      api.currentRepository().catch(()=>null),
    ])
    setTasks(t); setAgents(a); setFindings(f)
    if(r?.repository) setCurrentRepo(r.repository)
  },[])

  useEffect(()=>{load()},[load,refreshSignal])

  const handleSelectTask = (task) => {
    setSelectedTask(task)
    const linked = findings?.items?.find(f=>f.task_id===task.task_id)
    setSelectedFinding(linked||null)
  }

  const allTasks = tasks?.items||[]
  const allAgents = agents?.items||[]
  const taskAgentIds = [...new Set(allTasks.map(t=>t.agent_id).filter(Boolean))]
  const uniqueAgentsInTasks = allAgents.filter(a=>taskAgentIds.includes(a.agent_id))

  const STATUSES = ['ALL','RUNNING','PENDING','COMPLETED','FAILED']

  const filteredTasks = allTasks.filter(t=>{
    const statusOk = filter==='ALL'||t.status?.toUpperCase()===filter
    const agentOk = agentFilter==='ALL'||t.agent_id===agentFilter
    return statusOk&&agentOk
  })

  const byAgent = {}
  filteredTasks.forEach(t=>{
    const k = t.agent_id||'unassigned'
    if(!byAgent[k]) byAgent[k]=[]
    byAgent[k].push(t)
  })

  if(!tasks) return (
    <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:300,color:'var(--text-muted)'}}>
      <div style={{textAlign:'center'}}>
        <div style={{fontSize:32,marginBottom:12}}>⚙️</div>
        <div>Loading agent workflow…</div>
      </div>
    </div>
  )

  return (
    <div style={{display:'flex',flexDirection:'column',height:'100%',gap:0,overflow:'hidden'}}>
      {/* Page header */}
      <div style={{paddingBottom:16,flexShrink:0}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',flexWrap:'wrap',gap:12,marginBottom:16}}>
          <div>
            <div className="page-title">⚡ Agent Workflow</div>
            <div className="page-subtitle">Live orchestrator → agent → task → tool → evidence pipeline</div>
          </div>
          <div style={{display:'flex',gap:8,flexWrap:'wrap',alignItems:'center'}}>
            <div style={{display:'flex',gap:4,background:'var(--bg-base)',padding:4,borderRadius:8,border:'1px solid var(--border)'}}>
              {STATUSES.map(s=>(
                <button key={s} onClick={()=>setFilter(s)} style={{
                  padding:'4px 10px',border:'none',borderRadius:5,cursor:'pointer',
                  fontSize:10,fontWeight:600,letterSpacing:'0.04em',
                  background:filter===s?'var(--accent-blue)':'transparent',
                  color:filter===s?'#fff':'var(--text-muted)',transition:'all .15s',
                }}>{s}</button>
              ))}
            </div>
            <button onClick={load} style={{
              padding:'6px 12px',borderRadius:7,border:'1px solid var(--border)',
              background:'var(--bg-elevated)',color:'var(--text-secondary)',
              cursor:'pointer',fontSize:11,fontWeight:600,
            }}>↺ Refresh</button>
          </div>
        </div>

        <OrchestratorHeader agents={allAgents} currentRepo={currentRepo} tasks={allTasks}/>

        {uniqueAgentsInTasks.length>0&&(
          <div style={{display:'flex',gap:6,overflowX:'auto',paddingBottom:4}}>
            <button onClick={()=>setAgentFilter('ALL')} style={agentPillStyle(agentFilter==='ALL')}>All Agents</button>
            {uniqueAgentsInTasks.map(a=>(
              <button key={a.agent_id} onClick={()=>setAgentFilter(a.agent_id)} style={agentPillStyle(agentFilter===a.agent_id)}>
                🤖 {a.name||shortId(a.agent_id)}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Workflow canvas + workroom */}
      <div style={{display:'flex',flex:1,gap:16,overflow:'hidden',minHeight:0}}>
        {/* Canvas */}
        <div style={{flex:1,overflowY:'auto',overflowX:'auto'}}>
          {filteredTasks.length===0?(
            <div style={{display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',height:240,gap:12,color:'var(--text-muted)'}}>
              <div style={{fontSize:40}}>🤖</div>
              <div style={{fontSize:14}}>No tasks match the current filter</div>
              <div style={{fontSize:12}}>Try changing the status or agent filter above</div>
            </div>
          ):(
            <div style={{display:'flex',flexDirection:'column',gap:24}}>
              {Object.entries(byAgent).map(([agentId,agentTasks])=>{
                const agent = allAgents.find(a=>a.agent_id===agentId)
                const agentColor = agent?.health==='AVAILABLE'?'#4ade80':'#94a3b8'
                return (
                  <div key={agentId}>
                    <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:10,paddingBottom:8,borderBottom:'1px solid var(--border)'}}>
                      <span style={{width:8,height:8,borderRadius:'50%',background:agentColor,display:'inline-block'}}/>
                      <span style={{fontSize:12,fontWeight:700,color:'var(--text-secondary)'}}>
                        {agent?.name||(agentId==='unassigned'?'Unassigned':shortId(agentId))}
                      </span>
                      <span style={{fontSize:10,color:'var(--text-muted)'}}>
                        {agent?.role||''} • {agentTasks.length} task{agentTasks.length!==1?'s':''}
                      </span>
                    </div>
                    <div style={{display:'flex',gap:0,overflowX:'auto',paddingBottom:8,alignItems:'flex-start'}}>
                      {agentTasks.map((task,idx)=>{
                        const linkedFinding = findings?.items?.find(f=>f.task_id===task.task_id)
                        return (
                          <div key={task.task_id} style={{display:'flex',alignItems:'flex-start',gap:0}}>
                            <WorkflowNode
                              task={task} agents={allAgents} finding={linkedFinding}
                              isSelected={selectedTask?.task_id===task.task_id}
                              onClick={handleSelectTask}
                            />
                            {idx<agentTasks.length-1&&(
                              <div style={{display:'flex',alignItems:'center',height:80}}>
                                <div style={{width:24,height:1,background:'var(--border)'}}/>
                                <span style={{color:'var(--text-muted)',fontSize:10}}>▶</span>
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Workroom */}
        {selectedTask&&(
          <AgentWorkroom
            task={selectedTask} finding={selectedFinding} agents={allAgents}
            onClose={()=>{setSelectedTask(null);setSelectedFinding(null)}}
            onRefresh={load}
          />
        )}
      </div>
    </div>
  )
}
