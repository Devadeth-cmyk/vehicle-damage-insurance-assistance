import React, { useState } from 'react';
import { Car, Eye, Trash2, Pencil } from 'lucide-react';
import { api, type Vehicle } from './api';

interface MyVehiclesProps {
  vehicles: Vehicle[];
  onNavigate: (route: string) => void;
  onVehicleUpdated: () => void | Promise<void>;
}

export const MyVehicles: React.FC<MyVehiclesProps> = ({ vehicles, onNavigate, onVehicleUpdated }) => {
  const [deleteError, setDeleteError] = useState('');
  const [deletingVehicleId, setDeletingVehicleId] = useState<number | null>(null);

  const deleteVehicle = async (vehicle: Vehicle) => {
    const confirmed = window.confirm(
      `Delete ${vehicle.make} ${vehicle.model} (${vehicle.registration_number})? This cannot be undone.`
    );
    if (!confirmed) return;

    setDeletingVehicleId(vehicle.id);
    setDeleteError('');
    try {
      await api.delete(`/vehicles/${vehicle.id}`);
      await onVehicleUpdated();
    } catch (err: any) {
      setDeleteError(err.response?.data?.detail || 'Could not delete this vehicle. Please try again.');
    } finally {
      setDeletingVehicleId(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-primary)' }}>My Vehicles</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Manage your registered vehicles and their registration details.
          </p>
        </div>
        <button onClick={() => onNavigate('/vehicles/add')} className="btn-primary">
          + Add another vehicle
        </button>
      </div>

      {deleteError && (
        <div role="alert" style={{ padding: '0.85rem 1rem', background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', borderRadius: 'var(--radius-md)' }}>
          {deleteError}
        </div>
      )}

      {vehicles.length === 0 ? (
        <div className="glass-panel" style={{ padding: '4rem', textAlign: 'center' }}>
          <Car size={56} style={{ color: 'var(--text-muted)', marginBottom: '1rem' }} />
          <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>No Vehicles Registered</h3>
          <p style={{ color: 'var(--text-secondary)', maxWidth: '400px', margin: '0 auto 1.5rem auto', fontSize: '0.9rem' }}>
            Add your vehicle to start automated AI damage assessments and manage insurance claim filings.
          </p>
          <button onClick={() => onNavigate('/vehicles/add')} className="btn-primary">
            + Add Vehicle Now
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '1.5rem' }}>
          {vehicles.map((v) => (
            <div key={v.id} className="glass-panel glass-panel-hover" style={{ padding: '1.75rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem' }}>
                  <div style={{ display: 'flex', gap: '0.85rem', alignItems: 'center' }}>
                    <div
                      style={{
                        padding: '0.75rem',
                        background: 'rgba(99, 102, 241, 0.15)',
                        color: '#818cf8',
                        borderRadius: '12px'
                      }}
                    >
                      <Car size={24} />
                    </div>
                    <div>
                      <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                        {v.make} {v.model}
                      </h3>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600 }}>
                        {v.registration_number}
                      </span>
                    </div>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.5rem', background: '#f8fafc', border: '1px solid var(--border-color)', padding: '1rem', borderRadius: 'var(--radius-md)' }}>
                  <div>
                    <span style={{ display: 'block', fontSize: '0.7rem', color: '#64748b' }}>YEAR</span>
                    <strong>{v.year}</strong>
                  </div>
                  <div>
                    <span style={{ display: 'block', fontSize: '0.7rem', color: '#64748b' }}>FUEL TYPE</span>
                    <strong>{v.fuel_type || 'Petrol'}</strong>
                  </div>
                  <div>
                    <span style={{ display: 'block', fontSize: '0.7rem', color: '#64748b' }}>VEHICLE TYPE</span>
                    <strong>{v.vehicle_type || 'Not provided'}</strong>
                  </div>
                  <div><span style={{ display: 'block', fontSize: '0.7rem', color: '#64748b' }}>STATE</span><strong>{v.registration_state || 'Not provided'}</strong></div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '0.5rem', borderTop: '1px solid var(--border-color)', paddingTop: '1rem', flexWrap: 'wrap' }}>
                <button
                  onClick={() => onNavigate(`/vehicles/${v.id}`)}
                  className="btn-secondary"
                  style={{ flex: 1, padding: '0.5rem', fontSize: '0.8rem', justifyContent: 'center' }}
                >
                  <Eye size={15} /> View details
                </button>
                <button
                  type="button"
                  onClick={() => {
                    onNavigate(`/vehicles/${v.id}/edit`);
                  }}
                  className="btn-primary"
                  style={{ flex: 1, padding: '0.5rem', fontSize: '0.8rem', justifyContent: 'center' }}
                >
                  <Pencil size={15} /> Edit details
                </button>
                <button
                  type="button"
                  onClick={() => deleteVehicle(v)}
                  disabled={deletingVehicleId === v.id}
                  aria-label={`Delete ${v.make} ${v.model}`}
                  title="Delete vehicle"
                  style={{ padding: '0.5rem 0.7rem', display: 'inline-flex', justifyContent: 'center', alignItems: 'center', gap: '0.35rem', color: '#b91c1c', background: '#fff', border: '1px solid #fecaca', borderRadius: 'var(--radius-md)', cursor: deletingVehicleId === v.id ? 'wait' : 'pointer', opacity: deletingVehicleId === v.id ? 0.65 : 1 }}
                >
                  <Trash2 size={15} /> {deletingVehicleId === v.id ? 'Deleting…' : 'Delete'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
