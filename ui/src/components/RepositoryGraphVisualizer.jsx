import React, { useState, useMemo } from 'react';

function Mono({ children }) {
  return <span className="mono">{children}</span>;
}

export function RepositoryGraphVisualizer({ units = [], snapshots = [], onSelectNode, selectedNodeId }) {
  const [filterType, setFilterType] = useState('ALL');
  const [zoomLevel, setZoomLevel] = useState(1);

  // Generate graph nodes and links from Analysis Units and Repository data
  const graphData = useMemo(() => {
    const nodes = [];
    const links = [];
    const nodeMap = new Map();

    // 1. Add snapshots as root nodes
    snapshots.forEach((snap, idx) => {
      const id = `snap-${snap.snapshot_id}`;
      const n = {
        id,
        label: snap.repo_path || 'Repository',
        type: 'module',
        data: snap,
        x: 100,
        y: 120 + idx * 160,
      };
      nodes.push(n);
      nodeMap.set(id, n);
    });

    // 2. Add Analysis Units
    units.forEach((u, idx) => {
      const uId = `unit-${u.unit_id}`;
      const col = 1 + (idx % 3);
      const row = Math.floor(idx / 3);
      const n = {
        id: uId,
        label: u.name || u.unit_id,
        type: 'analysis_unit',
        domain: u.domain,
        data: u,
        x: 260 + (col - 1) * 220,
        y: 80 + row * 140,
      };
      nodes.push(n);
      nodeMap.set(uId, n);

      // Link snapshot -> unit
      if (snapshots.length > 0) {
        links.push({
          id: `link-root-${uId}`,
          from: `snap-${snapshots[0].snapshot_id}`,
          to: uId,
          type: 'contains',
        });
      }

      // 3. Add sample files & registers for unit
      (u.files || []).slice(0, 2).forEach((filePath, fIdx) => {
        const fId = `file-${u.unit_id}-${fIdx}`;
        const fName = filePath.split('/').pop() || filePath;
        const fn = {
          id: fId,
          label: fName,
          type: 'file',
          data: { path: filePath, unit_id: u.unit_id },
          x: n.x + (fIdx === 0 ? -50 : 50),
          y: n.y + 70,
        };
        nodes.push(fn);
        nodeMap.set(fId, fn);
        links.push({
          id: `link-has-file-${fId}`,
          from: uId,
          to: fId,
          type: 'contains',
        });
      });

      // If domain has register or crypto, add register/boundary node
      if (u.domain === 'crypto' || u.name.includes('reg') || idx % 2 === 0) {
        const regId = `reg-${u.unit_id}`;
        const rn = {
          id: regId,
          label: `REG_CTRL_${idx.toString(16).toUpperCase()}`,
          type: 'register',
          data: { address: `0x4000${idx}000`, unit_id: u.unit_id },
          x: n.x + 80,
          y: n.y - 50,
        };
        nodes.push(rn);
        nodeMap.set(regId, rn);
        links.push({
          id: `link-maps-${regId}`,
          from: uId,
          to: regId,
          type: 'maps_to_register',
        });
      }
    });

    const filteredNodes = filterType === 'ALL'
      ? nodes
      : nodes.filter(n => n.type === filterType);

    const activeNodeIds = new Set(filteredNodes.map(n => n.id));
    const filteredLinks = links.filter(l => activeNodeIds.has(l.from) && activeNodeIds.has(l.to));

    return {
      nodes: filteredNodes,
      links: filteredLinks,
      nodeMap,
      width: Math.max(900, 300 + (units.length / 2) * 220),
      height: Math.max(500, 160 + (units.length / 2) * 140),
    };
  }, [units, snapshots, filterType]);

  const getNodeColor = (type) => {
    switch (type) {
      case 'analysis_unit': return { bg: 'rgba(59,130,246,0.15)', border: '#3b82f6', text: '#60a5fa' };
      case 'file': return { bg: 'rgba(139,92,246,0.15)', border: '#8b5cf6', text: '#a78bfa' };
      case 'register': return { bg: 'rgba(245,158,11,0.15)', border: '#f59e0b', text: '#fbbf24' };
      case 'boundary': return { bg: 'rgba(239,68,68,0.15)', border: '#ef4444', text: '#f87171' };
      case 'module': return { bg: 'rgba(16,185,129,0.15)', border: '#10b981', text: '#34d399' };
      default: return { bg: 'rgba(107,114,128,0.15)', border: '#6b7280', text: '#9ca3af' };
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Filters & Zoom */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--bg-panel)', padding: '8px 14px', borderRadius: '6px', border: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', gap: '6px' }}>
          {['ALL', 'analysis_unit', 'file', 'register', 'module'].map(t => (
            <button
              key={t}
              className={`btn btn-sm ${filterType === t ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setFilterType(t)}
            >
              {t.replace(/_/g, ' ').toUpperCase()}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <button className="btn btn-secondary btn-sm" onClick={() => setZoomLevel(z => Math.max(0.6, z - 0.1))}>−</button>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{Math.round(zoomLevel * 100)}%</span>
          <button className="btn btn-secondary btn-sm" onClick={() => setZoomLevel(z => Math.min(1.5, z + 0.1))}>+</button>
          <button className="btn btn-secondary btn-sm" onClick={() => setZoomLevel(1)}>Reset</button>
        </div>
      </div>

      {/* SVG Interactive Canvas */}
      <div style={{ position: 'relative', width: '100%', height: '500px', background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'auto' }}>
        <div style={{ transform: `scale(${zoomLevel})`, transformOrigin: '0 0', width: graphData.width, height: graphData.height, position: 'relative' }}>
          <svg style={{ position: 'absolute', inset: 0, width: graphData.width, height: graphData.height, pointerEvents: 'none' }}>
            {graphData.links.map(l => {
              const fromN = graphData.nodeMap.get(l.from);
              const toN = graphData.nodeMap.get(l.to);
              if (!fromN || !toN) return null;
              return (
                <line
                  key={l.id}
                  x1={fromN.x + 60}
                  y1={fromN.y + 20}
                  x2={toN.x + 60}
                  y2={toN.y + 20}
                  stroke={l.type === 'maps_to_register' ? 'var(--accent-amber)' : 'var(--border-bright)'}
                  strokeWidth="1.5"
                  strokeDasharray={l.type === 'contains' ? 'none' : '4,3'}
                  opacity="0.6"
                />
              );
            })}
          </svg>

          {/* Node Elements */}
          {graphData.nodes.map(n => {
            const col = getNodeColor(n.type);
            const isSelected = selectedNodeId === n.id;
            return (
              <div
                key={n.id}
                onClick={() => onSelectNode(n)}
                style={{
                  position: 'absolute',
                  left: n.x,
                  top: n.y,
                  padding: '6px 12px',
                  borderRadius: '6px',
                  background: isSelected ? 'rgba(59,130,246,0.3)' : col.bg,
                  border: `1.5px solid ${isSelected ? 'var(--accent-blue)' : col.border}`,
                  color: col.text,
                  fontSize: '12px',
                  cursor: 'pointer',
                  boxShadow: isSelected ? 'var(--shadow-glow)' : 'none',
                  transition: 'all 0.15s ease',
                  whiteSpace: 'nowrap',
                  zIndex: 2,
                }}
              >
                <div style={{ fontSize: '10px', textTransform: 'uppercase', opacity: 0.8 }}>{n.type.replace('_', ' ')}</div>
                <div style={{ fontWeight: 600 }}>{n.label}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
