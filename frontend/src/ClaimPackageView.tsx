import React from 'react';
import { Package, Download, FileText, FileArchive, CheckCircle2, Shield, ExternalLink } from 'lucide-react';
import type { Claim } from './api';

interface ClaimPackageViewProps {
  claims: Claim[];
  selectedClaimId?: string;
  onNavigate: (route: string) => void;
}

export const ClaimPackageView: React.FC<ClaimPackageViewProps> = ({
  claims,
  selectedClaimId,
  onNavigate
}) => {
  const claim = claims.find((c) => c.claim_id === selectedClaimId) || claims[0];

  if (!claim) {
    return (
      <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', background: '#ffffff' }}>
        <Package size={48} style={{ color: '#94a3b8', marginBottom: '1rem' }} />
        <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f172a' }}>No Claim Selected</h3>
        <p style={{ color: '#64748b', marginTop: '0.5rem', fontSize: '0.9rem' }}>
          Select an active claim from your portfolio to inspect and download compiled claim packages.
        </p>
        <button onClick={() => onNavigate('/claims')} className="btn-secondary" style={{ marginTop: '1.5rem' }}>
          View My Claims
        </button>
      </div>
    );
  }

  const backendUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* HEADER BAR */}
      <div className="glass-panel" style={{ padding: '2rem', background: '#ffffff' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1.25rem', marginBottom: '1.25rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
              <span className="badge badge-success">COMPILED PACKAGE READY</span>
              <span className="badge badge-info">{claim.status}</span>
            </div>
            <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0f172a' }}>
              Claim Bundle Package — #{claim.claim_id}
            </h2>
            <p style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '0.2rem' }}>
              Policy #: {claim.policy_number || 'N/A'} • Generated for Insurer Submission
            </p>
          </div>
          <button onClick={() => onNavigate(`/claims/${claim.claim_id}`)} className="btn-secondary" style={{ fontSize: '0.85rem' }}>
            View Claim Lifecycle
          </button>
        </div>

        <p style={{ fontSize: '0.9rem', color: '#475569', lineHeight: 1.5 }}>
          The compiled claim package bundles all validated evidence, computer vision assessment reports, workshop labor estimates, policy details, and supporting documents into standardized formats for insurer review.
        </p>
      </div>

      {/* PACKAGE CONTENTS BREAKDOWN */}
      <div className="glass-panel" style={{ padding: '1.75rem', background: '#ffffff' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#0f172a', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <CheckCircle2 style={{ color: '#10b981' }} size={20} /> Included Bundle Items
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem', marginBottom: '1.75rem' }}>
          <div style={{ padding: '1rem', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 'var(--radius-md)' }}>
            <FileText size={22} style={{ color: '#0284c7', marginBottom: '0.5rem' }} />
            <h4 style={{ fontWeight: 700, fontSize: '0.85rem', color: '#0f172a' }}>Official Claim Summary PDF</h4>
            <p style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>Formatted PDF report with damage bounding boxes & costs.</p>
          </div>

          <div style={{ padding: '1rem', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 'var(--radius-md)' }}>
            <FileArchive size={22} style={{ color: '#10b981', marginBottom: '0.5rem' }} />
            <h4 style={{ fontWeight: 700, fontSize: '0.85rem', color: '#0f172a' }}>Full Evidence Media ZIP Archive</h4>
            <p style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>High-resolution damage photos, videos & metadata.</p>
          </div>

          <div style={{ padding: '1rem', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 'var(--radius-md)' }}>
            <Shield size={22} style={{ color: '#f59e0b', marginBottom: '0.5rem' }} />
            <h4 style={{ fontWeight: 700, fontSize: '0.85rem', color: '#0f172a' }}>Technician & AI JSON Schema</h4>
            <p style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>Machine-readable structured claim payload for underwriting.</p>
          </div>
        </div>

        {/* DOWNLOAD ACTION BUTTONS */}
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', borderTop: '1px solid #f1f5f9', paddingTop: '1.25rem' }}>
          <button
            onClick={() => window.open(`${backendUrl}/claims/${claim.claim_id}/package/pdf`)}
            className="btn-primary"
          >
            <FileText size={18} /> View Summary PDF <ExternalLink size={14} />
          </button>
          <button
            onClick={() => window.open(`${backendUrl}/claims/${claim.claim_id}/package/zip`)}
            className="btn-secondary"
          >
            <Download size={18} /> Download Package ZIP Archive
          </button>
        </div>
      </div>
    </div>
  );
};
