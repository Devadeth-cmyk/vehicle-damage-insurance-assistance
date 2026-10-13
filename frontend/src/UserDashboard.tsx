import React from 'react';
import { Sparkles, Car, FileCheck2, ShieldCheck } from 'lucide-react';
import { formatClaimDate, type Vehicle, type Claim } from './api';

interface UserDashboardProps {
  user: any;
  vehicles: Vehicle[];
  claims: Claim[];
  onNavigate: (route: string) => void;
}

export const UserDashboard: React.FC<UserDashboardProps> = ({ user, vehicles, claims, onNavigate }) => {
  const activeClaims = claims.filter(
    (c) => !c.status.toLowerCase().includes('completed') && !c.status.toLowerCase().includes('rejected')
  );
  const completedClaims = claims.filter((c) => c.status.toLowerCase().includes('completed'));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* HEADER & HERO */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#0f172a' }}>
            Welcome, {user.full_name || 'Customer'}
          </h2>
          <p style={{ color: '#475569', fontSize: '0.95rem' }}>
            Assess vehicle damage, manage insurance claims, and track service status from your portal.
          </p>
        </div>
        <button onClick={() => onNavigate('/claims/new')} className="btn-primary" style={{ padding: '0.85rem 1.5rem' }}>
          <FileCheck2 size={18} /> + New Claim
        </button>
      </div>

      {/* SUMMARY STAT CARDS */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.25rem' }}>
        <div className="glass-panel glass-panel-hover" style={{ padding: '1.5rem', background: '#ffffff' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
            <span style={{ fontSize: '0.85rem', color: '#64748b', fontWeight: 600 }}>Active Claims</span>
            <div style={{ padding: '0.5rem', background: '#e0f2fe', color: '#0284c7', borderRadius: '10px' }}>
              <FileCheck2 size={20} />
            </div>
          </div>
          <h3 style={{ fontSize: '2rem', fontWeight: 800, color: '#0f172a', marginBottom: '0.25rem' }}>{activeClaims.length}</h3>
          <p style={{ fontSize: '0.75rem', color: '#64748b' }}>In progress or under review</p>
        </div>

        <div className="glass-panel glass-panel-hover" style={{ padding: '1.5rem', background: '#ffffff' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
            <span style={{ fontSize: '0.85rem', color: '#64748b', fontWeight: 600 }}>My Vehicles</span>
            <div style={{ padding: '0.5rem', background: '#fef3c7', color: '#b45309', borderRadius: '10px' }}>
              <Car size={20} />
            </div>
          </div>
          <h3 style={{ fontSize: '2rem', fontWeight: 800, color: '#0f172a', marginBottom: '0.25rem' }}>{vehicles.length}</h3>
          <p style={{ fontSize: '0.75rem', color: '#64748b' }}>Registered policy vehicles</p>
        </div>

        <div className="glass-panel glass-panel-hover" style={{ padding: '1.5rem', background: '#ffffff' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
            <span style={{ fontSize: '0.85rem', color: '#64748b', fontWeight: 600 }}>Completed Claims</span>
            <div style={{ padding: '0.5rem', background: '#dcfce7', color: '#15803d', borderRadius: '10px' }}>
              <ShieldCheck size={20} />
            </div>
          </div>
          <h3 style={{ fontSize: '2rem', fontWeight: 800, color: '#0f172a', marginBottom: '0.25rem' }}>{completedClaims.length}</h3>
          <p style={{ fontSize: '0.75rem', color: '#64748b' }}>Finalized & package generated</p>
        </div>
      </div>

      {/* RECENT CLAIMS TABLE & QUICK ACTIONS */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1.5rem' }}>
        {/* RECENT CLAIMS */}
        <div className="glass-panel" style={{ padding: '1.75rem', background: '#ffffff' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#0f172a' }}>Recent Claims</h3>
            <button onClick={() => onNavigate('/claims')} style={{ background: 'none', border: 'none', color: '#0284c7', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer' }}>
              View All →
            </button>
          </div>

          {claims.length === 0 ? (
            <div style={{ padding: '3rem 1rem', textAlign: 'center', color: '#64748b' }}>
              <FileCheck2 size={48} style={{ color: '#cbd5e1', marginBottom: '0.75rem' }} />
              <p>No insurance claims filed yet.</p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)', color: '#64748b' }}>
                    <th style={{ padding: '0.75rem 0.5rem' }}>CLAIM ID</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>SUBMISSION DATE</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>STATUS</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>ACTION</th>
                  </tr>
                </thead>
                <tbody>
                  {claims.slice(0, 5).map((claim) => (
                    <tr key={claim.claim_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '0.85rem 0.5rem', fontWeight: 700, color: '#0f172a' }}>{claim.claim_id}</td>
                      <td style={{ padding: '0.85rem 0.5rem', color: '#475569' }}>{formatClaimDate(claim)}</td>
                      <td style={{ padding: '0.85rem 0.5rem' }}>
                        <span className={`badge ${claim.status.toLowerCase().includes('completed') ? 'badge-success' : 'badge-info'}`}>
                          {claim.status}
                        </span>
                      </td>
                      <td style={{ padding: '0.85rem 0.5rem' }}>
                        <button
                          onClick={() => onNavigate(`/claims/${claim.claim_id}`)}
                          className="btn-secondary"
                          style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem' }}
                        >
                          View Claim
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* QUICK SHORTCUTS */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="glass-panel glass-panel-hover" onClick={() => onNavigate('/claims/new')} style={{ padding: '1.5rem', cursor: 'pointer', background: '#ffffff' }}>
            <div style={{ padding: '0.6rem', background: '#e0f2fe', color: '#0284c7', borderRadius: '10px', width: 'fit-content', marginBottom: '0.75rem' }}>
              <Sparkles size={20} />
            </div>
            <h4 style={{ fontWeight: 700, color: '#0f172a', marginBottom: '0.25rem' }}>File New Damage Claim</h4>
            <p style={{ fontSize: '0.8rem', color: '#64748b' }}>Start streamlined claim wizard for instant damage claim submission.</p>
          </div>

          <div className="glass-panel glass-panel-hover" onClick={() => onNavigate('/vehicles')} style={{ padding: '1.5rem', cursor: 'pointer', background: '#ffffff' }}>
            <div style={{ padding: '0.6rem', background: '#fef3c7', color: '#b45309', borderRadius: '10px', width: 'fit-content', marginBottom: '0.75rem' }}>
              <Car size={20} />
            </div>
            <h4 style={{ fontWeight: 700, color: '#0f172a', marginBottom: '0.25rem' }}>Manage Vehicles</h4>
            <p style={{ fontSize: '0.8rem', color: '#64748b' }}>Add or edit your registered policy vehicles & VIN info.</p>
          </div>

          </div>
        </div>
      </div>
  );
};
