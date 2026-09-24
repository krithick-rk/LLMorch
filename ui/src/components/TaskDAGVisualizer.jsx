import React, { useState, useMemo } from 'react';

function Mono({ children }) {
  return <span className="mono">{children}</span>;
}

function StatusBadge({ status }) {
  const s = (status || 'unknown').toLowerCase().replace(/ /g, '_');
  return <span className={`badge badge-${s}`}>{status || '—'}</span>;
}

export function TaskDAGVisualizer({ tasks = [], selectedTaskId, onSelectTask, onSwitchAgentClick }) {
  const [zoomLevel, setZoomLevel] = useState(1);

  // Compute topological columns for layout
  const layout = useMemo(() => {
    if (!tasks || tasks.length === 0) return { nodes: [], edges: [], width: 800, height: 400 };

    const taskMap = new Map();
    tasks.forEach(t => taskMap.set(t.task_id, t));

    // Calculate level (depth) for each node
    const levels = new Map();
    const getLevel = (id, visited = new Set()) => {
      if (visited.has(id)) return 0;
      if (levels.has(id)) return levels.get(id);
      visited.add(id);
      const t = taskMap.get(id);
      if (!t || !t.dependencies || t.dependencies.length === 0) {
        levels.set(id, 0);
        return 0;
      }
      let maxParent = -1;
      for (const pId of t.dependencies) {
        maxParent = Math.max(maxParent, getLevel(pId, visited));
      }
      const lvl = maxParent + 1;
      levels.set(id, lvl);
      return lvl;
    };

    tasks.forEach(t => getLevel(t.task_id));

    // Group nodes by level
    const levelGroups = [];
    tasks.forEach(t => {
      const lvl = levels.get(t.task_id) || 0;
      if (!levelGroups[lvl]) levelGroups[lvl] = [];
      levelGroups[lvl].push(t);
    });

    const NODE_WIDTH = 220;
    const NODE_HEIGHT = 100;
    const GAP_X = 100;
    const GAP_Y = 30;
    const PADDING = 40;

    const positionedNodes = [];
    const nodeCoords = new Map();

    levelGroups.forEach((group, colIdx) => {
      const x = PADDING + colIdx * (NODE_WIDTH + GAP_X);
      group.forEach((t, rowIdx) => {
        const y = PADDING + rowIdx * (NODE_HEIGHT + GAP_Y);
        positionedNodes.push({
          task: t,
          x,
          y,
          width: NODE_WIDTH,
          height: NODE_HEIGHT,
        });
        nodeCoords.set(t.task_id, {
          cx: x + NODE_WIDTH,
          cy: y + NODE_HEIGHT / 2,
          lx: x,
          ly: y + NODE_HEIGHT / 2,
        });
      });
    });

    // Edges
    const edges = [];
    tasks.forEach(t => {
      const toCoord = nodeCoords.get(t.task_id);
      if (toCoord && t.dependencies) {
        t.dependencies.forEach(pId => {
          const fromCoord = nodeCoords.get(pId);
          if (fromCoord) {
            edges.push({
              id: `${pId}->${t.task_id}`,
              fromX: fromCoord.cx,
              fromY: fromCoord.cy,
              toX: toCoord.lx,
              toY: toCoord.ly,
            });
          }
        });
      }
    });

    const maxCol = levelGroups.length;
    const maxRow = Math.max(...levelGroups.map(g => g ? g.length : 0), 1);
    const totalWidth = Math.max(850, PADDING * 2 + maxCol * (NODE_WIDTH + GAP_X));
    const totalHeight = Math.max(450, PADDING * 2 + maxRow * (NODE_HEIGHT + GAP_Y));

    return { nodes: positionedNodes, edges, width: totalWidth, height: totalHeight };
  }, [tasks]);

  if (tasks.length === 0) {
    return <div className="empty-state"><div className="empty-icon">🔗</div><p>No tasks currently scheduled</p></div>;
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '540px', background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'auto' }}>
      <div style={{ position: 'sticky', top: 12, right: 12, display: 'flex', gap: '6px', zIndex: 10, justifyContent: 'flex-end', padding: '0 12px' }}>
        <button className="btn btn-secondary btn-sm" onClick={() => setZoomLevel(z => Math.max(0.6, z - 0.1))}>−</button>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center' }}>{Math.round(zoomLevel * 100)}%</span>
        <button className="btn btn-secondary btn-sm" onClick={() => setZoomLevel(z => Math.min(1.5, z + 0.1))}>+</button>
        <button className="btn btn-secondary btn-sm" onClick={() => setZoomLevel(1)}>Reset</button>
      </div>

      <div style={{ transform: `scale(${zoomLevel})`, transformOrigin: '0 0', width: layout.width, height: layout.height, position: 'relative' }}>
        {/* SVG Dependency Edges */}
        <svg style={{ position: 'absolute', inset: 0, width: layout.width, height: layout.height, pointerEvents: 'none' }}>
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 1 L 10 5 L 0 9 z" fill="var(--accent-blue)" />
            </marker>
          </defs>
          {layout.edges.map(e => {
            const dx = Math.max(30, (e.toX - e.fromX) / 2);
            const pathData = `M ${e.fromX} ${e.fromY} C ${e.fromX + dx} ${e.fromY}, ${e.toX - dx} ${e.toY}, ${e.toX} ${e.toY}`;
            return (
              <path
                key={e.id}
                d={pathData}
                stroke="var(--accent-blue)"
                strokeWidth="2"
                fill="none"
                markerEnd="url(#arrow)"
                opacity="0.75"
              />
            );
          })}
        </svg>

        {/* Task Nodes */}
        {layout.nodes.map(n => {
          const t = n.task;
          const isSelected = selectedTaskId === t.task_id;
          return (
            <div
              key={t.task_id}
              onClick={() => onSelectTask(t)}
              style={{
                position: 'absolute',
                left: n.x,
                top: n.y,
                width: n.width,
                height: n.height,
                background: isSelected ? 'rgba(59,130,246,0.15)' : 'var(--bg-panel)',
                border: `1.5px solid ${isSelected ? 'var(--accent-blue)' : 'var(--border-bright)'}`,
                borderRadius: '8px',
                padding: '10px 12px',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                boxShadow: isSelected ? 'var(--shadow-glow)' : 'var(--shadow-card)',
                transition: 'all 0.15s ease',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-code)' }}>
                  <Mono>{t.task_id.slice(0, 10)}…</Mono>
                </span>
                <StatusBadge status={t.status} />
              </div>

              <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {t.objective || 'Analysis Task'}
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '11px', color: 'var(--text-muted)' }}>
                <span>🤖 {t.assigned_agent_id ? t.assigned_agent_id.replace('agent-', '') : 'unassigned'}</span>
                {t.tokens_consumed > 0 && (
                  <span style={{ color: 'var(--accent-cyan)' }}>{t.tokens_consumed.toLocaleString()} tok</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
