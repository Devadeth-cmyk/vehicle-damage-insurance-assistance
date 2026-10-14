import React, { useEffect, useState } from 'react';
import { api, type User } from './api';
import { ArrowRight, Building2, CarFront, LockKeyhole, Mail, Phone, UserRound } from 'lucide-react';

type Portal = 'customer' | 'service_center' | 'admin';

interface AuthModalProps {
  portal: Portal;
  onLoginSuccess: (user: User, token: string) => void;
}

const portalCopy = {
  customer: {
    description: 'Access your vehicles, claims, and claim updates.',
    eyebrow: 'POLICYHOLDER PORTAL',
    icon: CarFront,
  },
  service_center: {
    description: 'Review assigned claims and manage repair assessments.',
    eyebrow: 'TECHNICIAN WORKSPACE',
    icon: Building2,
  },
  admin: {
    description: 'Sign in to manage service-center organizations and platform access.',
    eyebrow: 'PLATFORM ADMINISTRATION',
    icon: LockKeyhole,
  },
} as const;

export const AuthModal: React.FC<AuthModalProps> = ({ portal, onLoginSuccess }) => {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [serviceCenters, setServiceCenters] = useState<Array<{ id: number; name: string; city?: string | null; state?: string | null }>>([]);
  const [serviceCenterId, setServiceCenterId] = useState('');
  const [serviceCenterCode, setServiceCenterCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const registrationDisabled = portal === 'admin';

  useEffect(() => {
    setIsRegister(false);
    setError('');
  }, [portal]);

  useEffect(() => {
    if (portal !== 'service_center' || !isRegister) return;
    api.get('/service-centers/options')
      .then((response) => setServiceCenters(response.data))
      .catch(() => setError('Could not load registered service centers. Please try again later.'));
  }, [portal, isRegister]);

  const formatErrorMsg = (detail: unknown): string => {
    if (!detail) return '';
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((item: any) => item.msg || JSON.stringify(item)).join(', ');
    return JSON.stringify(detail);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isRegister && !registrationDisabled) {
        const response = await api.post('/auth/register', {
          email: email.trim(),
          password,
          full_name: fullName.trim(),
          phone: phone.trim() || undefined,
          portal,
          ...(portal === 'service_center' ? { service_center_id: Number(serviceCenterId) } : {}),
          ...(portal === 'service_center' ? { service_center_code: serviceCenterCode.trim() } : {}),
        });
        const token = response.data?.access_token;
        if (!token) {
          setError('Your account was created, but sign-in could not be completed. Please sign in.');
          setIsRegister(false);
          return;
        }
        localStorage.setItem('token', token);
        const profile = await api.get('/users/me', { headers: { Authorization: `Bearer ${token}` } });
        onLoginSuccess(profile.data, token);
      } else {
        const response = await api.post('/auth/login', {
          email: email.trim(),
          password,
          portal: portal === 'admin' ? 'admin' : portal,
        });
        const token = response.data.access_token;
        localStorage.setItem('token', token);
        const profile = await api.get('/users/me', { headers: { Authorization: `Bearer ${token}` } });
        onLoginSuccess(profile.data, token);
      }
    } catch (requestError: any) {
      const detail = requestError.response?.data?.detail;
      setError(detail
        ? formatErrorMsg(detail)
        : isRegister
          ? 'Account creation failed. Check your connection and try again.'
          : 'We could not sign you in. Check your details and make sure you selected the correct portal.');
    } finally {
      setLoading(false);
    }
  };

  const copy = portalCopy[portal];
  const PortalIcon = copy.icon;
  return (
    <main className="auth-shell">
      <section className={`auth-card ${portal}`}>
        <div className="auth-card-heading">
          <span className={`auth-large-icon ${portal}`}><PortalIcon size={27} /></span>
          <span className="auth-eyebrow">{copy.eyebrow}</span>
          <h1>AutoInsight</h1>
          <p>{isRegister
            ? portal === 'customer'
              ? 'Create your customer policyholder account.'
              : 'Create an account for your service center team.'
            : copy.description}</p>
        </div>

        {error && <div className="auth-error" role="alert">{error}</div>}

        <form className="auth-form" onSubmit={handleSubmit}>
        {isRegister && !registrationDisabled && (
            <>
              <label className="auth-field">
                <span>Full name</span>
                <span className="auth-input-wrap"><UserRound size={17} /><input required autoComplete="name" value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="Your name" /></span>
              </label>
              <label className="auth-field">
                <span>Mobile number <small>Optional</small></span>
                <span className="auth-input-wrap"><Phone size={17} /><input autoComplete="tel" value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="Your phone number" /></span>
              </label>
            </>
          )}
        {isRegister && !registrationDisabled && portal === 'service_center' && (
            <label className="auth-field">
              <span>Service center organization</span>
              <span className="auth-input-wrap"><Building2 size={17} /><select required value={serviceCenterId} onChange={(event) => setServiceCenterId(event.target.value)}>
                <option value="">Choose your organization</option>
                {serviceCenters.map((center) => <option key={center.id} value={center.id}>{center.name}{center.city ? ` - ${center.city}` : ''}{center.state ? `, ${center.state}` : ''}</option>)}
              </select></span>
              {serviceCenters.length === 0 && <small>Organizations must be created by a platform administrator before staff can register.</small>}
            </label>
          )}
        {isRegister && !registrationDisabled && portal === 'service_center' && (
            <label className="auth-field">
              <span>Organization invitation code</span>
              <span className="auth-input-wrap"><LockKeyhole size={17} /><input required value={serviceCenterCode} onChange={(event) => setServiceCenterCode(event.target.value)} placeholder="Provided by your service-center administrator" /></span>
            </label>
          )}
          <label className="auth-field">
            <span>Email address</span>
            <span className="auth-input-wrap"><Mail size={17} /><input required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" /></span>
          </label>
          <label className="auth-field">
            <span>Password</span>
            <span className="auth-input-wrap"><LockKeyhole size={17} /><input required type="password" autoComplete={isRegister ? 'new-password' : 'current-password'} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" /></span>
          </label>
          <button type="submit" className="auth-submit" disabled={loading}>
            {loading ? 'Please wait...' : isRegister && !registrationDisabled ? (portal === 'customer' ? 'Create customer account' : 'Create service center account') : 'Sign in securely'}
            {!loading && <ArrowRight size={17} />}
          </button>
        </form>

        {!registrationDisabled && <div className="auth-card-footer">
          <button type="button" onClick={() => { setError(''); setIsRegister((current) => !current); }}>
            {isRegister
              ? 'Already registered? Sign in'
              : portal === 'customer'
                ? 'New to AutoInsight? Create a customer account'
                : 'New service center? Register your team'}
          </button>
        </div>}
        <p className="auth-privacy-note"><LockKeyhole size={13} /> Protected sign-in · Access is limited by account role</p>
      </section>
    </main>
  );
};
