import React from 'react';
import { Clock, CheckCircle2, Calendar, Bell, User as UserIcon, Shield, Save } from 'lucide-react';
import { api, type User } from './api';

export const ServiceRequestsTracker: React.FC = () => {
  const steps = [
    { title: 'Submitted', desc: 'Request logged with workshop', status: 'completed' },
    { title: 'Under Review', desc: 'Estimator reviewing damage report', status: 'completed' },
    { title: 'Accepted', desc: 'Workshop slot confirmed', status: 'completed' },
    { title: 'Appointment Confirmed', desc: 'Scheduled for Sep 28 @ 10:00 AM', status: 'active' },
    { title: 'Vehicle Received', desc: 'Pending drop-off', status: 'pending' },
    { title: 'Repair In Progress', desc: 'Bodywork & paint refinishing', status: 'pending' },
    { title: 'Completed', desc: 'Ready for customer pickup', status: 'pending' }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div>
        <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'white' }}>Track Service Requests</h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Real-time workshop progress & repair milestone tracking.</p>
      </div>

      <div className="glass-panel" style={{ padding: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem', marginBottom: '2rem' }}>
          <div>
            <span className="badge badge-info" style={{ marginBottom: '0.35rem' }}>REQ-88192</span>
            <h3 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'white' }}>Metro Repairs & AutoCare</h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Vehicle: Toyota Camry (ABC-1234) • Claim #CLM-99812</p>
          </div>
          <span className="badge badge-warning">IN PROGRESS</span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', position: 'relative', paddingLeft: '1rem' }}>
          {steps.map((stg, i) => (
            <div key={i} style={{ display: 'flex', gap: '1.25rem', alignItems: 'flex-start' }}>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  background: stg.status === 'completed' ? '#10b981' : stg.status === 'active' ? '#6366f1' : 'rgba(255,255,255,0.1)',
                  color: 'white',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0
                }}
              >
                {stg.status === 'completed' ? <CheckCircle2 size={18} /> : <Clock size={16} />}
              </div>
              <div>
                <h4 style={{ fontSize: '1rem', fontWeight: 700, color: stg.status === 'pending' ? 'var(--text-muted)' : 'white' }}>{stg.title}</h4>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{stg.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export const AppointmentsView: React.FC = () => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
    <div>
      <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'white' }}>My Appointments</h2>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Scheduled workshop repair appointments.</p>
    </div>

    <div className="glass-panel" style={{ padding: '1.75rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <div style={{ padding: '0.75rem', background: 'rgba(99,102,241,0.15)', color: '#818cf8', borderRadius: '12px' }}>
            <Calendar size={24} />
          </div>
          <div>
            <h4 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'white' }}>Metro Repairs Workshop</h4>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Sep 28, 2026 @ 10:00 AM • Toyota Camry (ABC-1234)</p>
          </div>
        </div>
        <span className="badge badge-success">CONFIRMED</span>
      </div>
    </div>
  </div>
);

export const NotificationsView: React.FC = () => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
    <div>
      <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'white' }}>Notifications Center</h2>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Recent policy activity and claim status updates.</p>
    </div>

    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="glass-panel" style={{ padding: '1.25rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
        <Bell size={20} style={{ color: '#818cf8' }} />
        <div>
          <h4 style={{ fontWeight: 700, color: 'white', fontSize: '0.95rem' }}>AI Assessment Completed</h4>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Damage report generated with 94.2% confidence score for claim #CLM-99812.</p>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>2 hours ago</span>
        </div>
      </div>

      <div className="glass-panel" style={{ padding: '1.25rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
        <CheckCircle2 size={20} style={{ color: '#34d399' }} />
        <div>
          <h4 style={{ fontWeight: 700, color: 'white', fontSize: '0.95rem' }}>Workshop Appointment Confirmed</h4>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Metro Repairs confirmed repair slot for Sep 28, 10:00 AM.</p>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Yesterday</span>
        </div>
      </div>
    </div>
  </div>
);

export const UserProfileView: React.FC<{ user: User }> = ({ user }) => {
  const [firstName, setFirstName] = React.useState(user.full_name.split(' ')[0] || '');
  const [lastName, setLastName] = React.useState(user.full_name.split(' ')[1] || '');
  const [email] = React.useState(user.email);
  const [phone, setPhone] = React.useState(user.phone || '');
  const [dob, setDob] = React.useState('1992-04-15');
  const [gender, setGender] = React.useState('Male');
  const [addr, setAddr] = React.useState(user.address_line || '');
  const [city, setCity] = React.useState(user.city || '');
  const [state, setState] = React.useState(user.state || '');
  const [pincode, setPincode] = React.useState(user.pincode || '');
  const [country, setCountry] = React.useState(user.country || '');

  const [saved, setSaved] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [saveError, setSaveError] = React.useState('');

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveError('');
    try {
      await api.patch('/users/me', {
        full_name: `${firstName} ${lastName}`.trim(),
        phone,
        address_line: addr,
        city,
        state,
        pincode,
        country,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (error: any) {
      setSaveError(error.response?.data?.detail || 'Could not save profile details. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div>
        <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'white' }}>Profile Settings</h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Manage your personal details and policyholder address.</p>
      </div>

      {saved && (
        <div style={{ padding: '1rem', background: 'rgba(16,185,129,0.15)', color: '#34d399', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <CheckCircle2 size={18} /> Profile details saved successfully!
        </div>
      )}
      {saveError && (
        <div role="alert" style={{ padding: '1rem', background: 'rgba(239,68,68,0.15)', color: '#f87171', borderRadius: 'var(--radius-md)' }}>
          {saveError}
        </div>
      )}

      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <div className="glass-panel" style={{ padding: '2rem' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'white', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <UserIcon size={18} style={{ color: 'var(--accent-primary)' }} /> Personal Information
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>First Name</label>
              <input value={firstName} onChange={e => setFirstName(e.target.value)} style={{ width: '100%', padding: '0.75rem', background: 'rgba(0,0,0,0.25)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', color: 'white' }} />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Last Name</label>
              <input value={lastName} onChange={e => setLastName(e.target.value)} style={{ width: '100%', padding: '0.75rem', background: 'rgba(0,0,0,0.25)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', color: 'white' }} />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Email Address</label>
              <input disabled value={email} style={{ width: '100%', padding: '0.75rem', background: 'rgba(0,0,0,0.4)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', color: 'var(--text-muted)' }} />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Phone Number</label>
              <input value={phone} onChange={e => setPhone(e.target.value)} style={{ width: '100%', padding: '0.75rem', background: 'rgba(0,0,0,0.25)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', color: 'white' }} />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Date of Birth</label>
              <input type="date" value={dob} onChange={e => setDob(e.target.value)} style={{ width: '100%', padding: '0.75rem', background: 'rgba(0,0,0,0.25)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', color: 'white' }} />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Gender</label>
              <select value={gender} onChange={e => setGender(e.target.value)} style={{ width: '100%', padding: '0.75rem', background: 'rgba(0,0,0,0.25)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', color: 'white' }}>
                <option value="Male" style={{ background: '#111827' }}>Male</option>
                <option value="Female" style={{ background: '#111827' }}>Female</option>
                <option value="Other" style={{ background: '#111827' }}>Other</option>
              </select>
            </div>
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '2rem' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'white', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Shield size={18} style={{ color: '#34d399' }} /> Policyholder Address
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Address Line</label>
              <input value={addr} onChange={e => setAddr(e.target.value)} style={{ width: '100%', padding: '0.75rem', background: 'rgba(0,0,0,0.25)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', color: 'white' }} />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>City</label>
              <input value={city} onChange={e => setCity(e.target.value)} style={{ width: '100%', padding: '0.75rem', background: 'rgba(0,0,0,0.25)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', color: 'white' }} />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>State</label>
              <input value={state} onChange={e => setState(e.target.value)} style={{ width: '100%', padding: '0.75rem', background: 'rgba(0,0,0,0.25)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', color: 'white' }} />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Pincode / Zip</label>
              <input value={pincode} onChange={e => setPincode(e.target.value)} style={{ width: '100%', padding: '0.75rem', background: 'rgba(0,0,0,0.25)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', color: 'white' }} />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Country</label>
              <input value={country} onChange={e => setCountry(e.target.value)} style={{ width: '100%', padding: '0.75rem', background: 'rgba(0,0,0,0.25)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', color: 'white' }} />
            </div>
          </div>
        </div>

        <button type="submit" className="btn-primary" style={{ justifyContent: 'center', padding: '0.85rem' }}>
          <Save size={18} /> {saving ? 'Saving…' : 'Save Profile Changes'}
        </button>
      </form>
    </div>
  );
};
