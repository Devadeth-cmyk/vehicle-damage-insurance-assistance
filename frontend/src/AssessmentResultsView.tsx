import React from 'react';
import { ShieldCheck, AlertTriangle, ChevronRight, Wrench } from 'lucide-react';
import { formatClaimDate, type Claim } from './api';

interface AssessmentResultsViewProps {
  claims: Claim[];
  selectedClaimId?: string;
  onNavigate: (route: string) => void;
}

export const AssessmentResultsView: React.FC<AssessmentResultsViewProps> = ({
  claims,
  selectedClaimId,
  onNavigate
}) => {
  const claim = claims.find((c) => c.claim_id === selectedClaimId) || claims[0];

  if (!claim) {
    return (
      <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', background: '#ffffff' }}>
        <ShieldCheck size={48} style={{ color: '#94a3b8', marginBottom: '1rem' }} />
        <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f172a' }}>No Assessment Data Available</h3>
        <p style={{ color: '#64748b', marginTop: '0.5rem', fontSize: '0.9rem' }}>
          Please select a claim or file a new claim to view computer vision AI damage results.
        </p>
        <button onClick={() => onNavigate('/claims')} className="btn-secondary" style={{ marginTop: '1.5rem' }}>
          View My Claims
        </button>
      </div>
    );
  }

  // Check if released by Service Center
  const isReleased = claim.status !== 'SUBMITTED' && claim.status !== 'SERVICE_CENTER_RECEIVED';

  return (
    <div style={{ maxWidth: '960px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* HEADER BAR */}
      <div className="glass-panel" style={{ padding: '2rem', background: '#ffffff' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1.25rem', marginBottom: '1.25rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
              <span className="badge badge-info">AI ASSESSMENT RESULTS</span>
              <span className="badge badge-warning">{claim.status}</span>
            </div>
            <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0f172a' }}>
              Damage Assessment — Claim #{claim.claim_id}
            </h2>
            <p style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '0.2rem' }}>
              Policy #: {claim.policy_number || 'N/A'} • Submitted on {formatClaimDate(claim)}
            </p>
          </div>
          <button onClick={() => onNavigate(`/claims/${claim.claim_id}`)} className="btn-secondary" style={{ fontSize: '0.85rem' }}>
            Track Claim Lifecycle <ChevronRight size={16} />
          </button>
        </div>

        {/* INDICATIVE DISCLAIMER */}
        <div style={{
          padding: '1rem 1.25rem',
          background: '#fffbebfb',
          border: '1px solid #fde68a',
          borderRadius: 'var(--radius-md)',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '0.75rem',
          color: '#b45309'
        }}>
          <AlertTriangle size={20} style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <h4 style={{ fontSize: '0.85rem', fontWeight: 700 }}>Indicative Estimate Notice</h4>
            <p style={{ fontSize: '0.8rem', lineHeight: 1.4, marginTop: '0.1rem' }}>
              AI damage detection and repair cost estimates presented below are <strong>INDICATIVE ONLY</strong>. Final insurance settlement amounts are subject to physical technician verification and formal insurer review.
            </p>
          </div>
        </div>
      </div>

      {!isReleased ? (
        /* LOCKED / PENDING RELEASE STATE */
        <div className="glass-panel" style={{ padding: '3.5rem 2rem', textAlign: 'center', background: '#ffffff' }}>
          <div style={{ width: '64px', height: '64px', background: '#e0f2fe', color: '#0284c7', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem auto' }}>
            <Wrench size={32} />
          </div>
          <h3 style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f172a', marginBottom: '0.5rem' }}>
            Assessment Pending Release by Service Center
          </h3>
          <p style={{ color: '#64748b', maxWidth: '540px', margin: '0 auto 1.75rem auto', fontSize: '0.9rem' }}>
            Your claim is currently queued at the authorized Service Center. Computer vision damage scans and repair estimations will automatically unlock here once verified by workshop technicians.
          </p>
          <button onClick={() => onNavigate(`/claims/${claim.claim_id}`)} className="btn-primary">
            View Current Claim Progress Status
          </button>
        </div>
      ) : (
        /* RELEASED ASSESSMENT DETAILS */
        <>
          <div className="glass-panel" style={{ padding: '2rem', background: '#ffffff' }}>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f172a', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <ShieldCheck style={{ color: '#0284c7' }} size={24} /> AI Computer Vision Scans & Inspection Results
            </h3>
            <p style={{ fontSize: '0.875rem', color: '#64748b', marginBottom: '1.5rem' }}>
              Claim #{claim.claim_id} assessment details processed for {claim.incident_type || 'Vehicle Accident'}.
            </p>

            <div style={{ padding: '1.5rem', background: '#f8fafc', borderRadius: 'var(--radius-md)', border: '1px solid #e2e8f0', marginBottom: '1.5rem' }}>
              <h4 style={{ fontWeight: 700, color: '#0f172a', fontSize: '1rem', marginBottom: '0.5rem' }}>Incident Details</h4>
              <p style={{ fontSize: '0.875rem', color: '#475569' }}><strong>Location:</strong> {claim.incident_location || 'Not Specified'}</p>
              <p style={{ fontSize: '0.875rem', color: '#475569', marginTop: '0.25rem' }}><strong>Description:</strong> {claim.incident_description || 'No description provided.'}</p>
              <p style={{ fontSize: '0.875rem', color: '#475569', marginTop: '0.25rem' }}><strong>Policy Number:</strong> {claim.policy_number || 'N/A'}</p>
            </div>

            <div style={{ padding: '1.5rem', background: '#e0f2fe', borderRadius: 'var(--radius-md)', border: '1px solid #bae6fd', color: '#0369a1' }}>
              <h4 style={{ fontWeight: 700, fontSize: '0.95rem', marginBottom: '0.35rem' }}>Service Center Verification Status</h4>
              <p style={{ fontSize: '0.85rem', lineHeight: 1.4 }}>
                The physical inspection report and line-by-line itemized labor/parts evaluation for Claim #{claim.claim_id} are directly managed within the Service Center Module queue.
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
