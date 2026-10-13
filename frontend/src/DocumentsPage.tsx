import React, { useState } from 'react';
import { FileText, UploadCloud, Eye } from 'lucide-react';

export const DocumentsPage: React.FC = () => {
  const [docs] = useState([
    { id: 1, name: 'Motor_Policy_Comprehensive.pdf', claim: 'CLM-2026-0001', type: 'Insurance Policy', date: '2026-09-24', status: 'Verified' },
    { id: 2, name: 'Driving_License_Copy.jpg', claim: 'CLM-2026-0001', type: 'Driving License', date: '2026-09-24', status: 'Verified' },
    { id: 3, name: 'Vehicle_Registration_RC.pdf', claim: 'CLM-2026-0001', type: 'RC Document', date: '2026-09-24', status: 'Verified' }
  ]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0f172a' }}>Document Vault</h2>
          <p style={{ color: '#475569', fontSize: '0.9rem' }}>Manage policy documents, vehicle registration certificates, and claim attachments.</p>
        </div>
      </div>

      <div className="glass-panel" style={{ padding: '2rem', background: '#ffffff' }}>
        <div style={{ border: '2px dashed #cbd5e1', borderRadius: 'var(--radius-md)', padding: '2rem', textAlign: 'center', background: '#f8fafc', marginBottom: '2rem' }}>
          <UploadCloud size={36} style={{ color: '#0284c7', marginBottom: '0.5rem' }} />
          <h4 style={{ fontWeight: 700, color: '#0f172a', marginBottom: '0.25rem' }}>Upload Additional Supporting Document</h4>
          <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '1rem' }}>Upload Police FIR, Previous Claims, or Repair Receipts (PDF/JPG)</p>
          <button className="btn-primary" style={{ display: 'inline-flex' }}>Browse Files</button>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-color)', color: '#64748b' }}>
                <th style={{ padding: '0.75rem' }}>DOCUMENT NAME</th>
                <th style={{ padding: '0.75rem' }}>CLAIM REFERENCE</th>
                <th style={{ padding: '0.75rem' }}>TYPE</th>
                <th style={{ padding: '0.75rem' }}>UPLOAD DATE</th>
                <th style={{ padding: '0.75rem' }}>STATUS</th>
                <th style={{ padding: '0.75rem' }}>ACTION</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '0.85rem', fontWeight: 700, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <FileText size={18} style={{ color: '#0284c7' }} /> {d.name}
                  </td>
                  <td style={{ padding: '0.85rem', color: '#475569' }}>{d.claim}</td>
                  <td style={{ padding: '0.85rem', color: '#475569' }}>{d.type}</td>
                  <td style={{ padding: '0.85rem', color: '#64748b' }}>{d.date}</td>
                  <td style={{ padding: '0.85rem' }}><span className="badge badge-success">{d.status}</span></td>
                  <td style={{ padding: '0.85rem' }}>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button className="btn-secondary" style={{ padding: '0.35rem 0.65rem', fontSize: '0.75rem' }}><Eye size={14} /> View</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
