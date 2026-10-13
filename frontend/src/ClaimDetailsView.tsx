import { Clock, CheckCircle2, ShieldCheck, Download, FileText, Package } from 'lucide-react';
import { getEvidenceDisplay, type Claim, type User } from './api';
import { CLAIM_PROGRESS_STAGES, formatClaimStatus, getClaimProgress } from './claimProgress';

interface ClaimDetailsViewProps {
  claimId: string;
  claims: Claim[];
  user: User;
  onNavigate: (route: string) => void;
}

export const ClaimDetailsView: React.FC<ClaimDetailsViewProps> = ({ claimId, claims, user, onNavigate }) => {
  const claim = claims.find((c) => c.claim_id === claimId);

  if (!claim) {
    return (
      <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', background: '#ffffff' }}>
        <p style={{ color: '#64748b' }}>Claim details not found.</p>
        <button onClick={() => onNavigate('/claims')} className="btn-secondary" style={{ marginTop: '1rem' }}>
          Back to Claims List
        </button>
      </div>
    );
  }

  const claimStatus = claim.status?.toLowerCase() || 'submitted';
  const assessmentStatus = claim.assessment?.status?.toLowerCase();
  const progress = getClaimProgress(claimStatus);
  const timelineSteps = CLAIM_PROGRESS_STAGES.map((title, index) => ({
    title,
    status: progress.stageStatus(index),
  }));
  const damageImages = claim.assessment?.damage_results?.images;
  const detectedCount = Array.isArray(damageImages)
    ? damageImages.reduce((count, image) => {
        if (!image || typeof image !== 'object') return count;
        const detections = (image as { detections?: unknown }).detections;
        return count + (Array.isArray(detections) ? detections.length : 0);
      }, 0)
    : 0;
  const aiEstimate = claim.assessment?.repair_results?.ai_estimate;
  const estimate = aiEstimate && typeof aiEstimate === 'object'
    ? aiEstimate as { total_min_cost?: number; total_max_cost?: number; currency?: string }
    : null;
  const accidentDate = claim.accident_date || claim.incident_date;
  const formattedAccidentDate = accidentDate && !Number.isNaN(Date.parse(accidentDate))
    ? new Date(accidentDate).toLocaleDateString()
    : 'Not provided';
  const submittedDocuments = claim.evidence || [];

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* HEADER BAR */}
      <div className="glass-panel" style={{ padding: '2rem', background: '#ffffff' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem', marginBottom: '1.5rem' }}>
          <div>
            <span className="badge badge-info" style={{ marginBottom: '0.4rem' }}>CLAIM RECORD</span>
            <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0f172a' }}>Claim #{claim.claim_id}</h2>
            <p style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '0.2rem' }}>
              Policy #: {claim.policy_number || 'Not provided'} · Accident date: {formattedAccidentDate}
            </p>
          </div>
          <span className="badge badge-warning">{formatClaimStatus(claim.status)}</span>
        </div>

        {/* CUSTOMER-FRIENDLY TIMELINE */}
        <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0f172a', marginBottom: '1rem' }}>Claim Progress Timeline</h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.75rem', marginBottom: '1.5rem' }}>
          {timelineSteps.map((stg, i) => (
            <div key={i} style={{ background: stg.status === 'completed' ? '#f0fdf4' : stg.status === 'active' ? '#e0f2fe' : '#f8fafc', border: `1px solid ${stg.status === 'completed' ? '#bbf7d0' : stg.status === 'active' ? '#bae6fd' : '#e2e8f0'}`, padding: '0.75rem', borderRadius: 'var(--radius-md)', textAlign: 'center' }}>
              <div style={{ color: stg.status === 'completed' ? '#16a34a' : stg.status === 'active' ? '#0284c7' : '#94a3b8', marginBottom: '0.25rem' }}>
                {stg.status === 'completed' ? <CheckCircle2 size={18} /> : <Clock size={18} />}
              </div>
              <p style={{ fontSize: '0.75rem', fontWeight: 700, color: stg.status === 'pending' ? '#94a3b8' : '#0f172a' }}>{stg.title}</p>
            </div>
          ))}
        </div>
      </div>

      <section className="glass-panel" style={{ padding: '2rem', background: '#ffffff' }}>
        <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#0f172a', marginBottom: '1.25rem' }}>
          Claim Information Sent to Service Center
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem' }}>
          <div style={{ background: '#f8fafc', padding: '1.1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <h4 style={{ fontWeight: 700, marginBottom: '0.75rem', color: '#0369a1' }}>Vehicle</h4>
            <p><strong>Make & model:</strong> {claim.vehicle ? `${claim.vehicle.make} ${claim.vehicle.model}` : 'Not provided'}</p>
            <p><strong>Year:</strong> {claim.vehicle?.year || 'Not provided'}</p>
            <p><strong>Registration:</strong> {claim.vehicle?.registration_number || 'Not provided'}</p>
            <p><strong>VIN / chassis:</strong> {claim.vehicle?.vin || 'Not provided'}</p>
            <p><strong>Engine number:</strong> {claim.vehicle?.engine_number || 'Not provided'}</p>
          </div>
          <div style={{ background: '#f8fafc', padding: '1.1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <h4 style={{ fontWeight: 700, marginBottom: '0.75rem', color: '#0369a1' }}>Customer Contact</h4>
            <p><strong>Name:</strong> {user.full_name}</p>
            <p><strong>Email:</strong> {user.email}</p>
            <p><strong>Phone:</strong> {user.phone || 'Not provided'}</p>
            <p><strong>Address:</strong> {claim.customer_address || [user.address_line, user.city, user.state, user.pincode, user.country].filter(Boolean).join(', ') || 'Not provided'}</p>
          </div>
          <div style={{ background: '#f8fafc', padding: '1.1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <h4 style={{ fontWeight: 700, marginBottom: '0.75rem', color: '#0369a1' }}>Insurance Policy</h4>
            <p><strong>Insurer:</strong> {claim.insurance_company || 'Not provided'}</p>
            <p><strong>Policy number:</strong> {claim.policy_number || 'Not provided'}</p>
            <p><strong>Policy type:</strong> {claim.policy_type || 'Not provided'}</p>
            <p><strong>Expiry:</strong> {claim.policy_expiry || 'Not provided'}</p>
          </div>
          <div style={{ background: '#f8fafc', padding: '1.1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <h4 style={{ fontWeight: 700, marginBottom: '0.75rem', color: '#0369a1' }}>Accident Details</h4>
            <p><strong>Date:</strong> {formattedAccidentDate}</p>
            <p><strong>Time:</strong> {claim.accident_time || 'Not provided'}</p>
            <p><strong>Type:</strong> {claim.accident_type || 'Not provided'}</p>
            <p><strong>Location:</strong> {claim.accident_location || 'Not provided'}</p>
            <p style={{ marginTop: '0.5rem' }}><strong>Description:</strong> {claim.accident_description || claim.incident_description || 'No description provided.'}</p>
          </div>
          <div style={{ background: '#f8fafc', padding: '1.1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <h4 style={{ fontWeight: 700, marginBottom: '0.75rem', color: '#0369a1' }}>Submitted Files</h4>
            {submittedDocuments.length ? (
              <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
                {submittedDocuments.map((document, index) => {
                  const display = getEvidenceDisplay(document.file_name);
                  return (
                    <li key={`${document.file_name}-${index}`}>
                      <strong>{display.label}:</strong> {display.fileName}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p style={{ color: '#64748b' }}>No uploaded files are recorded for this claim.</p>
            )}          </div>
        </div>
      </section>

      {/* RELEASED PRELIMINARY ASSESSMENT & REPAIR ESTIMATE */}
      <div className="glass-panel" style={{ padding: '2rem', background: '#ffffff' }}>
        <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f172a', marginBottom: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <ShieldCheck style={{ color: '#0284c7' }} /> AI-Assisted Preliminary Assessment
        </h3>
        <p style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '1.25rem' }}>
          {assessmentStatus === 'completed'
            ? 'Preliminary results from the submitted evidence. Final repair costs require service center verification.'
            : 'Assessment results will appear here after the service center processes the submitted evidence.'}
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem', marginBottom: '1.5rem' }}>
          <div style={{ background: '#f8fafc', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#0f172a', marginBottom: '0.75rem' }}>Detected Vehicle Damage</h4>
            {assessmentStatus === 'completed' ? (
              <p style={{ fontSize: '0.85rem', color: '#334155' }}>
                {detectedCount} damage finding{detectedCount === 1 ? '' : 's'} detected across the submitted images.
              </p>
            ) : (
              <p style={{ fontSize: '0.85rem', color: '#64748b' }}>
                {assessmentStatus === 'failed' ? `Assessment failed: ${claim.assessment?.error_message || 'please contact the service center.'}` : 'No assessment results yet.'}
              </p>
            )}
          </div>

          <div style={{ background: '#f8fafc', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#0f172a', marginBottom: '0.75rem' }}>Indicative Repair Estimate</h4>
            {estimate && typeof estimate.total_min_cost === 'number' && typeof estimate.total_max_cost === 'number' ? (
              <p style={{ fontSize: '0.9rem', color: '#334155' }}>
                {estimate.currency || 'INR'} {estimate.total_min_cost.toLocaleString()}–{estimate.total_max_cost.toLocaleString()}
                <span style={{ display: 'block', color: '#64748b', fontSize: '0.78rem', marginTop: '0.35rem' }}>AI estimate; workshop verification pending.</span>
              </p>
            ) : (
              <p style={{ fontSize: '0.85rem', color: '#64748b' }}>No repair estimate available yet.</p>
            )}
          </div>
        </div>
      </div>

      {/* CLAIM PACKAGE DOWNLOAD SECTION */}
      <div className="glass-panel" style={{ padding: '2rem', background: '#ffffff' }}>
        <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f172a', marginBottom: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Package style={{ color: '#16a34a' }} /> Claim Package Exports
        </h3>
        <p style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '1.25rem' }}>
          Download compiled claim documentation and PDF assessment reports.
        </p>

        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <button onClick={() => window.open(`http://127.0.0.1:8000/api/v1/claims/${claim.claim_id}/package/pdf`)} className="btn-primary">
            <FileText size={18} /> View Claim Report PDF
          </button>
          <button onClick={() => window.open(`http://127.0.0.1:8000/api/v1/claims/${claim.claim_id}/package/zip`)} className="btn-secondary">
            <Download size={18} /> Download Claim Package ZIP
          </button>
        </div>
      </div>
    </div>
  );
};
