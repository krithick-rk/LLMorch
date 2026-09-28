import React, { useState, useEffect } from 'react';
import { api } from '../../api';

export default function SpecificationsPage() {
  const [specs, setSpecs] = useState([]);
  const [selectedSpecId, setSelectedSpecId] = useState(null);
  const [requirements, setRequirements] = useState([]);
  const [filePathInput, setFilePathInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [ingesting, setIngesting] = useState(false);
  const [actionMsg, setActionMsg] = useState('');

  const loadSpecs = async () => {
    try {
      setLoading(true);
      const res = await api.listSpecifications();
      const list = res.specifications || [];
      setSpecs(list);
      if (list.length > 0 && !selectedSpecId) {
        setSelectedSpecId(list[0].spec_id);
        loadReqs(list[0].spec_id);
      }
    } catch (err) {
      console.error('Failed to load specs:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadReqs = async (sId) => {
    try {
      const res = await api.listSpecRequirements(sId);
      setRequirements(res.requirements || []);
    } catch (err) {
      console.error('Failed to load requirements:', err);
    }
  };

  useEffect(() => {
    loadSpecs();
  }, []);

  const handleIngest = async (e) => {
    e.preventDefault();
    if (!filePathInput) return;
    try {
      setIngesting(true);
      setActionMsg('Ingesting specification and extracting claims...');
      const res = await api.ingestSpecification({ file_path: filePathInput });
      setActionMsg(`Successfully ingested ${res.specification.title}! Extracted ${res.requirements_count} requirements.`);
      setFilePathInput('');
      await loadSpecs();
      if (res.specification) {
        setSelectedSpecId(res.specification.spec_id);
        loadReqs(res.specification.spec_id);
      }
    } catch (err) {
      setActionMsg(`Ingestion failed: ${err.message}`);
    } finally {
      setIngesting(false);
    }
  };

  return (
    <div style={{ padding: '24px', color: '#e2e8f0', minHeight: '100%', background: '#0b0f17' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid #1e293b', paddingBottom: '16px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 'bold', margin: '0 0 6px 0', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span>📖</span> RM/TRM Specification Intelligence
          </h1>
          <p style={{ margin: 0, fontSize: '14px', color: '#94a3b8' }}>
            Deterministic ingestion of Technical Reference Manuals, register definitions, Markdown, and SVD files.
          </p>
        </div>

        <form onSubmit={handleIngest} style={{ display: 'flex', gap: '10px' }}>
          <input
            type="text"
            placeholder="Spec file path (e.g. /path/to/trm.md or spec.txt)"
            value={filePathInput}
            onChange={(e) => setFilePathInput(e.target.value)}
            style={{ padding: '8px 12px', borderRadius: '6px', background: '#1e293b', border: '1px solid #334155', color: '#f8fafc', fontSize: '13px', width: '320px' }}
          />
          <button
            type="submit"
            disabled={ingesting}
            style={{ padding: '8px 16px', borderRadius: '6px', background: ingesting ? '#475569' : '#3b82f6', color: '#fff', border: 'none', fontWeight: 'bold', cursor: ingesting ? 'not-allowed' : 'pointer' }}
          >
            {ingesting ? 'Ingesting...' : 'Ingest Spec'}
          </button>
        </form>
      </div>

      {actionMsg && (
        <div style={{ padding: '10px 16px', borderRadius: '6px', background: '#1e293b', borderLeft: '4px solid #3b82f6', marginBottom: '16px', fontSize: '13px' }}>
          {actionMsg}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '20px' }}>
        {/* Specs List */}
        <div style={{ background: '#111827', borderRadius: '8px', border: '1px solid #1e293b', padding: '16px' }}>
          <h3 style={{ fontSize: '13px', fontWeight: 'bold', margin: '0 0 12px 0', color: '#94a3b8', textTransform: 'uppercase' }}>Ingested Documents</h3>
          {loading ? (
            <div style={{ color: '#64748b', fontSize: '13px' }}>Loading specifications...</div>
          ) : specs.length === 0 ? (
            <div style={{ color: '#64748b', fontSize: '13px' }}>No specifications ingested yet. Ingest a document above.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {specs.map((s) => (
                <div
                  key={s.spec_id}
                  onClick={() => { setSelectedSpecId(s.spec_id); loadReqs(s.spec_id); }}
                  style={{
                    padding: '12px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    background: selectedSpecId === s.spec_id ? '#1e293b' : '#0f172a',
                    border: selectedSpecId === s.spec_id ? '1px solid #3b82f6' : '1px solid #1e293b'
                  }}
                >
                  <div style={{ fontWeight: 'bold', color: '#f8fafc', fontSize: '13px', marginBottom: '2px' }}>{s.title}</div>
                  <div style={{ fontSize: '11px', color: '#94a3b8' }}>Type: {s.document_type} • {s.requirements_extracted} requirements</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Requirements Table */}
        <div style={{ background: '#111827', borderRadius: '8px', border: '1px solid #1e293b', padding: '20px' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 'bold', margin: '0 0 14px 0', color: '#f8fafc' }}>
            Extracted Verification Requirements ({requirements.length})
          </h3>
          {requirements.length === 0 ? (
            <div style={{ color: '#64748b', fontSize: '13px' }}>No requirements extracted for this specification.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {requirements.map((r) => (
                <div key={r.requirement_id} style={{ background: '#0f172a', padding: '14px', borderRadius: '6px', border: '1px solid #1e293b' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <span style={{ fontWeight: 'bold', color: '#f8fafc', fontSize: '13px' }}>{r.title}</span>
                    <span style={{ fontSize: '11px', padding: '2px 6px', borderRadius: '4px', background: '#3b82f620', color: '#60a5fa' }}>
                      {r.primary_bucket}
                    </span>
                  </div>
                  <div style={{ fontSize: '13px', color: '#cbd5e1', marginBottom: '6px' }}>{r.description}</div>
                  <div style={{ fontSize: '11px', color: '#64748b' }}>
                    Section: {r.section} | Provenance: {r.provenance}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
