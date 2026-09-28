import React, { useState, useEffect } from 'react';
import { api } from '../../api';

export default function PoliciesPage() {
  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newRule, setNewRule] = useState('');
  const [actionMsg, setActionMsg] = useState('');

  const loadPolicies = async () => {
    try {
      setLoading(true);
      const res = await api.listPolicies();
      setPolicies(res.policies || []);
    } catch (err) {
      console.error('Failed to load policies:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPolicies();
  }, []);

  const handleReview = async (policyId, status) => {
    try {
      await api.reviewPolicy(policyId, { status });
      setActionMsg(`Policy ${policyId} status updated to ${status}.`);
      loadPolicies();
    } catch (err) {
      setActionMsg(`Failed to review policy: ${err.message}`);
    }
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    if (!newTitle || !newRule) return;
    try {
      await api.createPolicy({
        title: newTitle,
        policy_rule: newRule
      });
      setShowCreateModal(false);
      setNewTitle('');
      setNewRule('');
      setActionMsg('New candidate security policy created.');
      loadPolicies();
    } catch (err) {
      setActionMsg(`Failed to create policy: ${err.message}`);
    }
  };

  return (
    <div style={{ padding: '24px', color: '#e2e8f0', minHeight: '100%', background: '#0b0f17' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid #1e293b', paddingBottom: '16px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 'bold', margin: '0 0 6px 0', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span>📜</span> Security Policy Candidates (SoCureLLM-inspired)
          </h1>
          <p style={{ margin: 0, fontSize: '14px', color: '#94a3b8' }}>
            Machine-readable hardware security policies synthesized from threat models and validated evidence. Reviewable by analyst; never auto-enforced.
          </p>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          style={{ padding: '8px 16px', borderRadius: '6px', background: '#3b82f6', color: '#fff', border: 'none', fontWeight: 'bold', cursor: 'pointer' }}
        >
          + Propose Candidate Policy
        </button>
      </div>

      {actionMsg && (
        <div style={{ padding: '10px 16px', borderRadius: '6px', background: '#1e293b', borderLeft: '4px solid #3b82f6', marginBottom: '16px', fontSize: '13px' }}>
          {actionMsg}
        </div>
      )}

      {loading ? (
        <div style={{ color: '#64748b', textAlign: 'center', padding: '40px' }}>Loading policy candidates...</div>
      ) : policies.length === 0 ? (
        <div style={{ color: '#64748b', textAlign: 'center', padding: '40px' }}>No candidate policies generated yet. Click "Propose Candidate Policy" above.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {policies.map((p) => (
            <div key={p.policy_id} style={{ background: '#111827', borderRadius: '8px', border: '1px solid #1e293b', padding: '18px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                <div>
                  <h3 style={{ fontSize: '16px', fontWeight: 'bold', color: '#f8fafc', margin: '0 0 4px 0' }}>{p.title}</h3>
                  <div style={{ fontSize: '12px', color: '#94a3b8' }}>Role: {p.author_role} • Domain: {p.domain}</div>
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <span style={{
                    padding: '3px 8px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    fontWeight: 'bold',
                    background: p.status === 'APPROVED' ? '#10b98120' : (p.status === 'CANDIDATE' ? '#f59e0b20' : '#47556920'),
                    color: p.status === 'APPROVED' ? '#34d399' : (p.status === 'CANDIDATE' ? '#fbbf24' : '#94a3b8')
                  }}>
                    {p.status}
                  </span>
                  {p.status === 'CANDIDATE' && (
                    <>
                      <button
                        onClick={() => handleReview(p.policy_id, 'APPROVED')}
                        style={{ padding: '4px 10px', borderRadius: '4px', background: '#10b981', color: '#fff', border: 'none', fontSize: '12px', fontWeight: 'bold', cursor: 'pointer' }}
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => handleReview(p.policy_id, 'WAIVED')}
                        style={{ padding: '4px 10px', borderRadius: '4px', background: '#334155', color: '#cbd5e1', border: 'none', fontSize: '12px', cursor: 'pointer' }}
                      >
                        Waive
                      </button>
                    </>
                  )}
                </div>
              </div>

              <div style={{ background: '#0f172a', padding: '12px', borderRadius: '6px', border: '1px solid #1e293b', fontFamily: 'monospace', fontSize: '13px', color: '#38bdf8', marginBottom: '8px' }}>
                {p.policy_rule}
              </div>

              <div style={{ fontSize: '11px', color: '#64748b' }}>Provenance: {p.provenance}</div>
            </div>
          ))}
        </div>
      )}

      {showCreateModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#111827', padding: '24px', borderRadius: '8px', width: '480px', border: '1px solid #334155' }}>
            <h3 style={{ margin: '0 0 16px 0', color: '#f8fafc', fontSize: '16px' }}>Propose Candidate Security Policy</h3>
            <form onSubmit={handleCreateSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>Policy Title</label>
                <input
                  type="text"
                  placeholder="e.g. Debug Unlock Reset Invariant"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', background: '#1e293b', border: '1px solid #334155', color: '#f8fafc' }}
                  required
                />
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>Formal / SVA Policy Rule</label>
                <textarea
                  rows={3}
                  placeholder="e.g. assert property (@(posedge clk) rst_ni |-> !debug_unlocked);"
                  value={newRule}
                  onChange={(e) => setNewRule(e.target.value)}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', background: '#1e293b', border: '1px solid #334155', color: '#f8fafc', fontFamily: 'monospace' }}
                  required
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '6px' }}>
                <button type="button" onClick={() => setShowCreateModal(false)} style={{ padding: '8px 16px', borderRadius: '6px', background: '#334155', color: '#cbd5e1', border: 'none', cursor: 'pointer' }}>Cancel</button>
                <button type="submit" style={{ padding: '8px 16px', borderRadius: '6px', background: '#3b82f6', color: '#fff', border: 'none', fontWeight: 'bold', cursor: 'pointer' }}>Propose</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
