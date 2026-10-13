import React, { useState } from 'react';
import { api, type User } from './api';
import { Shield, Lock, Mail, User as UserIcon, Phone } from 'lucide-react';

interface AuthModalProps {
  onLoginSuccess: (user: User, token: string) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ onLoginSuccess }) => {
  const [isRegister, setIsRegister] = useState(false);
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [role, setRole] = useState('user');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const formatErrorMsg = (detail: any): string => {
    if (!detail) return '';
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map((item: any) => item.msg || JSON.stringify(item)).join(', ');
    }
    return JSON.stringify(detail);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isRegister) {
        const regRes = await api.post('/auth/register', {
          email: email.trim(),
          password,
          full_name: fullName.trim(),
          phone: phone.trim() || undefined,
          role,
        });

        const token = regRes.data?.access_token;
        if (token) {
          localStorage.setItem('token', token);
          try {
            const profileRes = await api.get('/users/me', {
              headers: { Authorization: `Bearer ${token}` }
            });
            onLoginSuccess(profileRes.data, token);
          } catch {
            onLoginSuccess({
              id: Date.now(),
              full_name: fullName,
              email,
              phone,
              role: 'user'
            }, token);
          }
        } else {
          setError('Registration successful, but no token returned. Please log in.');
          setIsRegister(false);
        }
      } else {
        const loginRes = await api.post('/auth/login', {
          email: email.trim(),
          password,
        });

        const token = loginRes.data.access_token;
        localStorage.setItem('token', token);

        const profileRes = await api.get('/users/me', {
          headers: { Authorization: `Bearer ${token}` }
        });
        onLoginSuccess(profileRes.data, token);
      }
    } catch (err: any) {
      const backendDetail = err.response?.data?.detail;
      if (backendDetail) {
        setError(formatErrorMsg(backendDetail));
      } else if (isRegister) {
        setError('Account registration failed. Please check network connection or try again.');
      } else {
        setError('Invalid credentials or backend server unreachable.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '2rem',
      background: 'var(--bg-primary)'
    }}>
      <div className="glass-panel" style={{ width: '100%', maxWidth: '460px', padding: '2.5rem', background: '#ffffff' }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{
            display: 'inline-flex',
            padding: '1rem',
            borderRadius: '16px',
            background: '#e0f2fe',
            color: '#0284c7',
            marginBottom: '1rem',
            boxShadow: '0 4px 12px rgba(2, 132, 199, 0.2)'
          }}>
            <Shield size={36} />
          </div>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0f172a', marginBottom: '0.35rem' }}>
            AutoInsight
          </h2>
          <p style={{ color: '#64748b', fontSize: '0.9rem' }}>
            {isRegister ? 'Create your customer policyholder account' : 'Sign in to access your claims & vehicles'}
          </p>
        </div>

        {error && (
          <div style={{
            padding: '0.75rem 1rem',
            borderRadius: 'var(--radius-sm)',
            background: '#fee2e2',
            border: '1px solid #fca5a5',
            color: '#b91c1c',
            fontSize: '0.85rem',
            marginBottom: '1.5rem'
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {isRegister && (
            <>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#475569', marginBottom: '0.4rem', fontWeight: 600 }}>
                  Full Name *
                </label>
                <div style={{ position: 'relative' }}>
                  <UserIcon size={18} style={{ position: 'absolute', left: '12px', top: '12px', color: '#94a3b8' }} />
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="John Doe"
                    style={{
                      width: '100%',
                      padding: '0.75rem 0.75rem 0.75rem 2.5rem',
                      background: '#f8fafc',
                      border: '1px solid var(--border-color)',
                      borderRadius: 'var(--radius-md)',
                      fontSize: '0.9rem',
                      outline: 'none'
                    }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#475569', marginBottom: '0.4rem', fontWeight: 600 }}>
                  Mobile Number
                </label>
                <div style={{ position: 'relative' }}>
                  <Phone size={18} style={{ position: 'absolute', left: '12px', top: '12px', color: '#94a3b8' }} />
                  <input
                    type="text"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+1 555-0192"
                    style={{
                      width: '100%',
                      padding: '0.75rem 0.75rem 0.75rem 2.5rem',
                      background: '#f8fafc',
                      border: '1px solid var(--border-color)',
                      borderRadius: 'var(--radius-md)',
                      fontSize: '0.9rem',
                      outline: 'none'
                    }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#475569', marginBottom: '0.4rem', fontWeight: 600 }}>
                  Account Type
                </label>
                <div style={{ display: 'flex', gap: '1rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem' }}>
                    <input type="radio" name="role" value="user" checked={role === 'user'} onChange={(e) => setRole(e.target.value)} />
                    Customer
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem' }}>
                    <input type="radio" name="role" value="service_center" checked={role === 'service_center'} onChange={(e) => setRole(e.target.value)} />
                    Service Center Technician
                  </label>
                </div>
              </div>
            </>
          )}

          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', color: '#475569', marginBottom: '0.4rem', fontWeight: 600 }}>
              Email Address *
            </label>
            <div style={{ position: 'relative' }}>
              <Mail size={18} style={{ position: 'absolute', left: '12px', top: '12px', color: '#94a3b8' }} />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                style={{
                  width: '100%',
                  padding: '0.75rem 0.75rem 0.75rem 2.5rem',
                  background: '#f8fafc',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.9rem',
                  outline: 'none'
                }}
              />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', color: '#475569', marginBottom: '0.4rem', fontWeight: 600 }}>
              Password *
            </label>
            <div style={{ position: 'relative' }}>
              <Lock size={18} style={{ position: 'absolute', left: '12px', top: '12px', color: '#94a3b8' }} />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                style={{
                  width: '100%',
                  padding: '0.75rem 0.75rem 0.75rem 2.5rem',
                  background: '#f8fafc',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.9rem',
                  outline: 'none'
                }}
              />
            </div>
          </div>

          <button type="submit" className="btn-primary" disabled={loading} style={{ justifyContent: 'center', width: '100%', marginTop: '0.5rem' }}>
            {loading ? 'Processing...' : isRegister ? 'Create Account' : 'Sign In'}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
          <button
            onClick={() => {
              setError('');
              setIsRegister(!isRegister);
            }}
            style={{
              background: 'none',
              border: 'none',
              color: '#0284c7',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            {isRegister ? 'Already have an account? Sign in' : "Don't have an account? Create one"}
          </button>
        </div>
      </div>
    </div>
  );
};
