import React, { useState, useEffect } from 'react';
import { api } from '../../api';

export default function ContextFabricPage() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('components');

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const res = await api.getContextSummary();
        setSummary(res);
      } catch (err) {
        console.error('Failed to load context fabric summary:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div style={{ padding: '24px', color: '#e2e8f0', minHeight: '100%', background: '#0b0f17' }}>
      <div style={{ marginBottom: '20px', borderBottom: '1px solid #1e293b', paddingBottom: '16px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 'bold', margin: '0 0 6px 0', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span>🧩</span> SoC Context Fabric
        </h1>
        <p style={{ margin: 0, fontSize: '14px', color: '#94a3b8' }}>
          Typed architectural graph linking RM/TRM specifications, RTL components, interfaces, clock/reset domains, and security assets.
        </p>
      </div>

      {loading ? (
        <div style={{ color: '#64748b', padding: '40px', textAlign: 'center' }}>Loading Context Fabric graph...</div>
      ) : summary ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Top Graph Summary Metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '12px' }}>
            <div style={{ background: '#111827', padding: '14px', borderRadius: '8px', border: '1px solid #1e293b' }}>
              <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>SoC Components</div>
              <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#60a5fa' }}>{summary.components_count}</div>
            </div>
            <div style={{ background: '#111827', padding: '14px', borderRadius: '8px', border: '1px solid #1e293b' }}>
              <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Interface Contracts</div>
              <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#34d399' }}>{summary.interfaces_count}</div>
            </div>
            <div style={{ background: '#111827', padding: '14px', borderRadius: '8px', border: '1px solid #1e293b' }}>
              <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Security Assets</div>
              <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#f59e0b' }}>{summary.security_assets_count}</div>
            </div>
            <div style={{ background: '#111827', padding: '14px', borderRadius: '8px', border: '1px solid #1e293b' }}>
              <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Threat Models</div>
              <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#ef4444' }}>{summary.threat_models_count}</div>
            </div>
            <div style={{ background: '#111827', padding: '14px', borderRadius: '8px', border: '1px solid #1e293b' }}>
              <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Requirements Linked</div>
              <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#a855f7' }}>{summary.requirements_count}</div>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid #1e293b', paddingBottom: '8px' }}>
            {['components', 'interfaces', 'security_assets'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  background: activeTab === tab ? '#1e293b' : 'transparent',
                  color: activeTab === tab ? '#f8fafc' : '#94a3b8',
                  border: activeTab === tab ? '1px solid #334155' : 'none',
                  fontWeight: activeTab === tab ? 'bold' : 'normal',
                  cursor: 'pointer',
                  textTransform: 'capitalize'
                }}
              >
                {tab.replace('_', ' ')}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div style={{ background: '#111827', borderRadius: '8px', border: '1px solid #1e293b', padding: '20px' }}>
            {activeTab === 'components' && (
              <div>
                <h3 style={{ fontSize: '15px', fontWeight: 'bold', margin: '0 0 14px 0', color: '#f8fafc' }}>
                  Identified Hardware & Software Components ({summary.components?.length || 0})
                </h3>
                {summary.components && summary.components.length > 0 ? (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>
                    {summary.components.map((c) => (
                      <div key={c.component_id} style={{ background: '#0f172a', padding: '14px', borderRadius: '6px', border: '1px solid #1e293b' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                          <span style={{ fontWeight: 'bold', color: '#f8fafc' }}>{c.name}</span>
                          <span style={{ fontSize: '11px', padding: '2px 6px', borderRadius: '4px', background: '#3b82f620', color: '#60a5fa' }}>{c.component_type}</span>
                        </div>
                        <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>
                          Security Tier: <span style={{ color: '#cbd5e1' }}>{c.security_tier}</span>
                        </div>
                        {c.clock_domain && (
                          <div style={{ fontSize: '11px', color: '#64748b' }}>Clock: {c.clock_domain} | Reset: {c.reset_domain || 'default'}</div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ color: '#64748b', fontSize: '13px' }}>
                    No specialized SoC components indexed yet. Run verification plan synthesis or intake analysis.
                  </div>
                )}
              </div>
            )}

            {activeTab === 'interfaces' && (
              <div>
                <h3 style={{ fontSize: '15px', fontWeight: 'bold', margin: '0 0 14px 0', color: '#f8fafc' }}>
                  Interface Contracts & Domain Crossings
                </h3>
                {summary.interfaces && summary.interfaces.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {summary.interfaces.map((i) => (
                      <div key={i.contract_id} style={{ background: '#0f172a', padding: '12px', borderRadius: '6px', border: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between' }}>
                        <div>
                          <span style={{ fontWeight: 'bold', color: '#f8fafc' }}>{i.source_component_id} ➔ {i.target_component_id}</span>
                          <span style={{ marginLeft: '10px', fontSize: '11px', color: '#94a3b8' }}>Type: {i.interface_type}</span>
                        </div>
                        <div>
                          {i.clock_crossing && <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '3px', background: '#f59e0b20', color: '#fbbf24', marginRight: '6px' }}>CDC</span>}
                          {i.reset_crossing && <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '3px', background: '#ef444420', color: '#f87171', marginRight: '6px' }}>RDC</span>}
                          {i.security_boundary && <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '3px', background: '#a855f720', color: '#c084fc' }}>Security Boundary</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ color: '#64748b', fontSize: '13px' }}>No interface contracts recorded yet.</div>
                )}
              </div>
            )}

            {activeTab === 'security_assets' && (
              <div>
                <h3 style={{ fontSize: '15px', fontWeight: 'bold', margin: '0 0 14px 0', color: '#f8fafc' }}>
                  Critical Security Assets & Trust Boundaries
                </h3>
                {summary.security_assets && summary.security_assets.length > 0 ? (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>
                    {summary.security_assets.map((a) => (
                      <div key={a.asset_id} style={{ background: '#0f172a', padding: '14px', borderRadius: '6px', border: '1px solid #1e293b' }}>
                        <div style={{ fontWeight: 'bold', color: '#f8fafc', marginBottom: '4px' }}>{a.name}</div>
                        <div style={{ fontSize: '12px', color: '#f59e0b', marginBottom: '4px' }}>Type: {a.asset_type}</div>
                        <div style={{ fontSize: '11px', color: '#94a3b8' }}>{a.threat_description || 'Protected asset requiring invariant verification'}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ color: '#64748b', fontSize: '13px' }}>No security assets registered in current fabric.</div>
                )}
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
