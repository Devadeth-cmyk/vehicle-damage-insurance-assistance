import React from 'react';
import { ArrowLeft, Car } from 'lucide-react';
import type { Vehicle } from './api';

interface VehicleDetailsViewProps {
  vehicle?: Vehicle;
  onNavigate: (route: string) => void;
}

const Detail: React.FC<{ label: string; value?: string | number | null }> = ({ label, value }) => (
  <div style={{ padding: '0.9rem', background: '#f8fafc', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)' }}>
    <div style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginBottom: '0.25rem' }}>{label}</div>
    <strong style={{ color: 'var(--text-primary)', overflowWrap: 'anywhere' }}>{value || 'Not provided'}</strong>
  </div>
);

export const VehicleDetailsView: React.FC<VehicleDetailsViewProps> = ({ vehicle, onNavigate }) => {
  if (!vehicle) {
    return <div className="glass-panel" style={{ padding: '2rem' }}><p>Vehicle not found.</p><button className="btn-secondary" onClick={() => onNavigate('/vehicles')}>Back to vehicles</button></div>;
  }

  const details: [string, string | number | undefined][] = [
    ['Registration number', vehicle.registration_number], ['Make', vehicle.make], ['Model', vehicle.model],
    ['Year', vehicle.year], ['Vehicle type', vehicle.vehicle_type], ['Variant', vehicle.variant],
    ['Fuel type', vehicle.fuel_type], ['Transmission', vehicle.transmission], ['Color', vehicle.color],
    ['VIN / chassis number', vehicle.vin], ['Engine number', vehicle.engine_number],
    ['Registration date', vehicle.registration_date], ['Registration state', vehicle.registration_state], ['RTO office', vehicle.rto],
  ];

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', display: 'grid', gap: '1.25rem' }}>
      <button className="btn-secondary" onClick={() => onNavigate('/vehicles')} style={{ justifySelf: 'start' }}><ArrowLeft size={16} /> Back to vehicles</button>
      <section className="glass-panel" style={{ padding: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', marginBottom: '1.25rem' }}>
          <Car size={26} color="#0284c7" />
          <div><h2 style={{ color: 'var(--text-primary)' }}>{vehicle.make} {vehicle.model}</h2><p style={{ color: 'var(--text-secondary)' }}>Vehicle details</p></div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '0.75rem' }}>
          {details.map(([label, value]) => <Detail key={label} label={label} value={value} />)}
        </div>
      </section>
    </div>
  );
};
