import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity, ArrowRight, Building2, Check, CircleCheck, CircleX, Copy, LayoutDashboard,
  LogOut, MapPin, Plus, RefreshCw, Search, ShieldCheck, UsersRound, X
} from 'lucide-react';
import { serviceCenterApi } from './services/serviceCenterService';

type AdminPortalProps = {
  user: { full_name?: string; email?: string };
  currentRoute: string;
  onNavigate: (route: string) => void;
  onLogout: () => void;
};

type Center = {
  id: number;
  name: string;
  supported_makes: string[];
  city?: string | null;
  state?: string | null;
  address?: string | null;
  is_active: boolean;
};

const panel: React.CSSProperties = { background: '#fff', border: '1px solid #e2e8f0', borderRadius: 16, padding: 22, boxShadow: '0 1px 2px rgba(15, 23, 42, 0.03)' };
const input: React.CSSProperties = { boxSizing: 'border-box', width: '100%', minHeight: 44, padding: '10px 12px', border: '1px solid #cbd5e1', borderRadius: 9, color: '#0f172a', background: '#fff', font: 'inherit' };

export const AdminPortal: React.FC<AdminPortalProps> = ({ user, currentRoute, onNavigate, onLogout }) => {
  const [centers, setCenters] = useState<Center[]>([]);
  const [name, setName] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [address, setAddress] = useState('');
  const [memberEmails, setMemberEmails] = useState<Record<number, string>>({});
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [inviteCode, setInviteCode] = useState('');
  const [inviteCodeCopied, setInviteCodeCopied] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const loadCenters = async () => {
    setLoading(true);
    try {
      setCenters(await serviceCenterApi.getManagedCenters());
      setError('');
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Could not load service centers. Check the API connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void loadCenters(); }, []);

  const runAction = async (action: () => Promise<void>) => {
    setBusy(true);
    setMessage('');
    setError('');
    try { await action(); }
    catch (e: any) { setError(e.response?.data?.detail || 'The action could not be completed.'); }
    finally { setBusy(false); }
  };

  const createCenter = (event: React.FormEvent) => {
    event.preventDefault();
    void runAction(async () => {
      const result = await serviceCenterApi.createCenter({ name, city, state, address });
      setInviteCode(result.join_code || '');
      setInviteCodeCopied(false);
      setMessage(`Service center created. Existing claims routed: ${result.routed_existing_claims || 0}.`);
      setName(''); setCity(''); setState(''); setAddress('');
      setShowCreateForm(false);
      await loadCenters();
    });
  };

  const assignStaff = (center: Center) => void runAction(async () => {
    await serviceCenterApi.assignCenterMember(center.id, memberEmails[center.id] || '');
    setMessage(`Staff account linked to ${center.name}. Staff who register with this center's invite code are linked automatically.`);
    setMemberEmails(current => ({ ...current, [center.id]: '' }));
  });

  const rotateCode = (center: Center) => void runAction(async () => {
    const result = await serviceCenterApi.rotateCenterInviteCode(center.id);
    setInviteCode(result.join_code);
    setInviteCodeCopied(false);
    setMessage(`A new invitation code was created for ${center.name}; the previous code is invalid.`);
  });

  const copyInviteCode = async () => {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard is unavailable');
      await navigator.clipboard.writeText(inviteCode);
      setInviteCodeCopied(true);
      setError('');
      setMessage('Invitation code copied to clipboard.');
    } catch {
      setError('Clipboard access was blocked. Select the invitation code and copy it manually.');
    }
  };

  const toggleCenter = (center: Center) => void runAction(async () => {
    await serviceCenterApi.updateCenter(center.id, { is_active: !center.is_active });
    setMessage(`${center.name} ${center.is_active ? 'deactivated' : 'activated'}.`);
    await loadCenters();
  });

  const activeCount = centers.filter(center => center.is_active).length;
  const inactiveCount = centers.length - activeCount;
  const makeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    centers.forEach(center => center.supported_makes.forEach(make => counts.set(make, (counts.get(make) || 0) + 1)));
    return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [centers]);
  const filteredCenters = useMemo(() => {
    const query = search.trim().toLowerCase();
    return centers.filter(center => {
      const matchesStatus = statusFilter === 'all' || (statusFilter === 'active' ? center.is_active : !center.is_active);
      const text = [center.name, center.city, center.state, center.address, ...center.supported_makes].filter(Boolean).join(' ').toLowerCase();
      return matchesStatus && (!query || text.includes(query));
    });
  }, [centers, search, statusFilter]);

  const isCentersPage = currentRoute.endsWith('/service-centers');
  const navItem = (route: string, label: string, Icon: typeof LayoutDashboard) => (
    <button key={route} onClick={() => onNavigate(route)} style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%', padding: '12px 14px', border: 0, borderRadius: 9, cursor: 'pointer', textAlign: 'left', color: currentRoute === route ? '#fff' : '#cbd5e1', background: currentRoute === route ? '#0284c7' : 'transparent', fontWeight: 650 }}>
      <Icon size={18} />{label}
    </button>
  );

  const stat = (label: string, value: number, detail: string, Icon: typeof Building2, color: string) => (
    <article style={{ ...panel, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
      <div><div style={{ color: '#64748b', fontSize: 13, fontWeight: 600 }}>{label}</div><strong style={{ display: 'block', marginTop: 8, fontSize: 30, lineHeight: 1.1 }}>{value}</strong><div style={{ marginTop: 7, color: '#94a3b8', fontSize: 12 }}>{detail}</div></div>
      <span style={{ display: 'grid', placeItems: 'center', width: 42, height: 42, flexShrink: 0, borderRadius: 12, background: `${color}14`, color }}><Icon size={20} /></span>
    </article>
  );

  return <div style={{ minHeight: '100vh', background: '#f5f8fc', color: '#0f172a' }}>
    <aside style={{ position: 'fixed', inset: '0 auto 0 0', width: 250, padding: 18, background: '#101a2e', color: '#fff', display: 'flex', flexDirection: 'column', zIndex: 20, boxSizing: 'border-box' }}>
      <div style={{ display: 'flex', gap: 11, alignItems: 'center', padding: '10px 6px 28px' }}><span style={{ display: 'grid', placeItems: 'center', background: '#0284c7', width: 42, height: 42, borderRadius: 12 }}><ShieldCheck /></span><div><strong style={{ fontSize: 17 }}>AutoInsight</strong><div style={{ fontSize: 11, color: '#94a3b8', letterSpacing: 1 }}>PLATFORM ADMIN</div></div></div>
      <div style={{ color: '#64748b', fontSize: 10, fontWeight: 700, letterSpacing: 1.3, padding: '0 14px 8px' }}>WORKSPACE</div>
      <nav style={{ display: 'grid', gap: 6 }}>{navItem('/dashboard', 'Overview', LayoutDashboard)}{navItem('/service-centers', 'Service Centers', Building2)}</nav>
      <div style={{ marginTop: 'auto', borderTop: '1px solid #334155', paddingTop: 12 }}><button onClick={onLogout} style={{ ...navButtonStyle, color: '#fca5a5' }}><LogOut size={18} />Sign out</button></div>
    </aside>

    <div style={{ marginLeft: 250, minHeight: '100vh' }}>
      <header style={{ minHeight: 72, boxSizing: 'border-box', position: 'sticky', top: 0, zIndex: 10, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, padding: '12px 30px', background: 'rgba(255,255,255,0.96)', borderBottom: '1px solid #e2e8f0', backdropFilter: 'blur(10px)' }}>
        <div><div style={{ color: '#0284c7', fontSize: 11, fontWeight: 800, letterSpacing: 1.1 }}>AUTOINSiGHT / ADMIN</div><strong style={{ fontSize: 16 }}>Platform administration</strong></div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}><span style={{ display: 'grid', placeItems: 'center', width: 38, height: 38, borderRadius: '50%', background: '#e0f2fe', color: '#0369a1', fontWeight: 800 }}>{(user.full_name || 'A').slice(0, 1).toUpperCase()}</span><div><strong style={{ display: 'block', fontSize: 13 }}>{user.full_name || 'Administrator'}</strong><span style={{ color: '#64748b', fontSize: 12 }}>{user.email}</span></div></div>
      </header>

      <main style={{ maxWidth: 1380, margin: '0 auto', padding: '30px clamp(18px, 3vw, 42px)', display: 'grid', gap: 22 }}>
        {(error || message) && <div role={error ? 'alert' : 'status'} style={{ ...panel, padding: '13px 16px', color: error ? '#991b1b' : '#075985', background: error ? '#fef2f2' : '#eff6ff', borderColor: error ? '#fecaca' : '#bae6fd' }}>{error || message}</div>}

        {!isCentersPage ? <>
          <section style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 20, flexWrap: 'wrap' }}>
            <div><div style={{ color: '#0284c7', fontSize: 12, fontWeight: 800, letterSpacing: 1 }}>NETWORK OPERATIONS</div><h1 style={{ margin: '7px 0', fontSize: 30, letterSpacing: '-0.6px' }}>Administration overview</h1><p style={{ margin: 0, color: '#64748b' }}>Monitor your service-center network and manage access from one workspace.</p></div>
            <div style={{ display: 'flex', gap: 9 }}><button className="btn-secondary" disabled={loading} onClick={() => void loadCenters()}><RefreshCw size={15} /> Refresh data</button><button className="btn-primary" onClick={() => { setShowCreateForm(true); onNavigate('/service-centers'); }}><Plus size={16} /> Add service center</button></div>
          </section>

          <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(210px,1fr))', gap: 14 }}>
            {stat('Total service centers', centers.length, 'Organizations in the network', Building2, '#0284c7')}
            {stat('Active centers', activeCount, 'Currently accepting routed claims', CircleCheck, '#059669')}
            {stat('Inactive centers', inactiveCount, 'Temporarily unavailable', CircleX, '#d97706')}
            {stat('Manufacturers covered', makeCounts.length, 'Unique vehicle makes mapped', Activity, '#7c3aed')}
          </section>

          <section style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1.6fr) minmax(260px,0.9fr)', gap: 18 }}>
            <div style={panel}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}><div><h2 style={{ margin: 0, fontSize: 18 }}>Service-center network</h2><p style={{ margin: '5px 0 0', color: '#64748b', fontSize: 13 }}>Current status by registered location</p></div><button className="btn-secondary" onClick={() => onNavigate('/service-centers')}>View all <ArrowRight size={15} /></button></div>
              {loading ? <p style={{ color: '#64748b', padding: '18px 0 0' }}>Loading network…</p> : centers.length === 0 ? <div style={{ marginTop: 18, padding: 20, borderRadius: 12, background: '#f8fafc', color: '#64748b' }}>No service centers yet. Add the first center to begin routing claims.</div> : <div style={{ marginTop: 12 }}>{centers.slice(0, 5).map(center => <div key={center.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, padding: '13px 0', borderTop: '1px solid #edf2f7' }}><div><strong style={{ fontSize: 14 }}>{center.name}</strong><div style={{ marginTop: 4, color: '#64748b', fontSize: 12 }}>{[center.city, center.state].filter(Boolean).join(', ') || 'Location not specified'} · {center.supported_makes.join(', ')}</div></div><StatusBadge active={center.is_active} /></div>)}</div>}
            </div>
            <div style={{ ...panel, background: 'linear-gradient(145deg,#0b4f7b,#0f766e)', color: '#fff', border: 0 }}><span style={{ display: 'grid', placeItems: 'center', width: 42, height: 42, borderRadius: 12, background: 'rgba(255,255,255,0.15)' }}><UsersRound size={21} /></span><h2 style={{ margin: '18px 0 8px', fontSize: 19 }}>Staff access</h2><p style={{ margin: 0, color: '#dbeafe', fontSize: 13, lineHeight: 1.6 }}>Issue a one-time invitation for each center. Staff who register with it are linked to that organization automatically.</p><button onClick={() => onNavigate('/service-centers')} style={{ marginTop: 18, border: '1px solid rgba(255,255,255,0.45)', borderRadius: 9, background: 'rgba(255,255,255,0.1)', color: '#fff', padding: '9px 12px', display: 'inline-flex', alignItems: 'center', gap: 7, cursor: 'pointer', fontWeight: 700 }}>Manage invitations <ArrowRight size={15} /></button></div>
          </section>

          <section style={panel}>
            <div><h2 style={{ margin: 0, fontSize: 18 }}>Manufacturer coverage</h2><p style={{ margin: '5px 0 15px', color: '#64748b', fontSize: 13 }}>Each center’s manufacturer is inferred from its name for claim routing.</p></div>
            {makeCounts.length === 0 ? <p style={{ margin: 0, color: '#64748b' }}>Coverage appears here after centers are registered.</p> : <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>{makeCounts.map(([make, count]) => <div key={make} style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '9px 12px', border: '1px solid #e2e8f0', borderRadius: 10, background: '#f8fafc' }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#0284c7' }} /><strong style={{ fontSize: 13 }}>{make}</strong><span style={{ color: '#64748b', fontSize: 12 }}>{count} {count === 1 ? 'center' : 'centers'}</span></div>)}</div>}
          </section>
        </> : <>
          <section style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 18, flexWrap: 'wrap' }}>
            <div><div style={{ color: '#0284c7', fontSize: 12, fontWeight: 800, letterSpacing: 1 }}>ORGANIZATION DIRECTORY</div><h1 style={{ margin: '7px 0', fontSize: 30, letterSpacing: '-0.6px' }}>Service centers</h1><p style={{ margin: 0, color: '#64748b' }}>Create locations, manage status, and control staff invitations.</p></div>
            <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}><button className="btn-secondary" disabled={loading} onClick={() => void loadCenters()}><RefreshCw size={15} /> Refresh</button><button className="btn-primary" onClick={() => setShowCreateForm(value => !value)}>{showCreateForm ? <X size={16} /> : <Plus size={16} />}{showCreateForm ? 'Close form' : 'New service center'}</button></div>
          </section>

          {showCreateForm && <form onSubmit={createCenter} style={{ ...panel, display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(210px,1fr))', gap: 16 }}>
            <div style={{ gridColumn: '1/-1' }}><h2 style={{ margin: 0, fontSize: 18 }}>Register a service center</h2><p style={{ color: '#64748b', fontSize: 13, margin: '5px 0 0' }}>Include a supported vehicle make in the center name to enable automatic claim routing.</p></div>
            <label style={labelStyle}>Center name<input required value={name} onChange={e => setName(e.target.value)} style={input} placeholder="e.g. Maruti Suzuki Kochi Service" /></label>
            <label style={labelStyle}>City<input value={city} onChange={e => setCity(e.target.value)} style={input} placeholder="e.g. Kochi" /></label>
            <label style={labelStyle}>Coverage state<input required value={state} onChange={e => setState(e.target.value)} style={input} placeholder="e.g. Kerala" /></label>
            <label style={{ ...labelStyle, gridColumn: '1/-1' }}>Street address<input value={address} onChange={e => setAddress(e.target.value)} style={input} placeholder="Service center address" /></label>
            <div><button className="btn-primary" type="submit" disabled={busy}>{busy ? 'Creating…' : 'Create service center'}</button></div>
          </form>}

          {inviteCode && <section style={{ ...panel, background: '#fffbeb', borderColor: '#fcd34d' }}><strong>Staff invitation code — share securely</strong><div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', margin: '10px 0' }}><code style={{ fontFamily: 'monospace', userSelect: 'all', fontSize: 16 }}>{inviteCode}</code><button type="button" className="btn-secondary" onClick={() => void copyInviteCode()} aria-label="Copy staff invitation code">{inviteCodeCopied ? <Check size={15} /> : <Copy size={15} />}{inviteCodeCopied ? 'Copied' : 'Copy code'}</button></div><small>This code is shown only once. Generating another code invalidates it.</small></section>}

          <section style={panel}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 15 }}><div><h2 style={{ margin: 0, fontSize: 18 }}>Directory <span style={{ color: '#64748b', fontWeight: 500 }}>({filteredCenters.length})</span></h2><p style={{ margin: '5px 0 0', color: '#64748b', fontSize: 13 }}>{activeCount} active · {inactiveCount} inactive</p></div><div style={{ display: 'flex', gap: 9, flex: '1 1 380px', maxWidth: 600 }}><div style={{ position: 'relative', flex: 1 }}><Search size={16} color="#94a3b8" style={{ position: 'absolute', left: 12, top: 14 }} /><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search name, make, city, or state" style={{ ...input, paddingLeft: 37 }} /></div><select aria-label="Filter centers by status" value={statusFilter} onChange={e => setStatusFilter(e.target.value as typeof statusFilter)} style={{ ...input, width: 145 }}><option value="all">All statuses</option><option value="active">Active</option><option value="inactive">Inactive</option></select></div></div>
            {loading ? <div style={{ padding: '28px 10px', textAlign: 'center', color: '#64748b' }}>Loading centers…</div> : filteredCenters.length === 0 ? <div style={{ padding: '30px 16px', textAlign: 'center', border: '1px dashed #cbd5e1', borderRadius: 12, background: '#f8fafc' }}><Building2 size={24} color="#94a3b8" /><strong style={{ display: 'block', marginTop: 8 }}>{centers.length ? 'No matching centers' : 'No service centers yet'}</strong><p style={{ margin: '5px 0 0', color: '#64748b', fontSize: 13 }}>{centers.length ? 'Change the search or status filter.' : 'Create a center to start routing claims.'}</p></div> : <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(min(100%,430px),1fr))', gap: 14 }}>{filteredCenters.map(center => <article key={center.id} style={{ border: '1px solid #e2e8f0', borderRadius: 13, padding: 18, background: '#fff' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}><div><h3 style={{ margin: 0, fontSize: 16 }}>{center.name}</h3><div style={{ marginTop: 9, display: 'flex', flexWrap: 'wrap', gap: 6 }}>{center.supported_makes.map(make => <span key={make} style={{ borderRadius: 20, padding: '4px 9px', background: '#eff6ff', color: '#0369a1', fontWeight: 700, fontSize: 11 }}>{make}</span>)}</div></div><StatusBadge active={center.is_active} /></div>
              <div style={{ display: 'grid', gap: 7, margin: '15px 0', color: '#64748b', fontSize: 13 }}><div style={{ display: 'flex', alignItems: 'center', gap: 7 }}><MapPin size={15} />{[center.city, center.state].filter(Boolean).join(', ') || 'Location not specified'}</div>{center.address && <div style={{ paddingLeft: 22 }}>{center.address}</div>}</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', borderTop: '1px solid #edf2f7', paddingTop: 13 }}><button className="btn-secondary" disabled={busy || !center.is_active} onClick={() => void rotateCode(center)}><UsersRound size={15} /> New invite code</button><button className="btn-secondary" disabled={busy} onClick={() => void toggleCenter(center)}>{center.is_active ? <><CircleX size={15} /> Deactivate</> : <><CircleCheck size={15} /> Activate</>}</button></div>
              {center.is_active && <div style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'center' }}><input type="email" aria-label={`Existing service-center staff email for ${center.name}`} placeholder="Existing staff email" value={memberEmails[center.id] || ''} onChange={e => setMemberEmails(current => ({ ...current, [center.id]: e.target.value }))} style={input} /><button type="button" className="btn-secondary" disabled={busy || !memberEmails[center.id]?.trim()} onClick={() => assignStaff(center)}>Assign</button></div>}
              {center.is_active && <small style={{ display: 'block', color: '#94a3b8', marginTop: 6 }}>Staff registering with this center's invitation are linked automatically.</small>}
            </article>)}</div>}
          </section>
        </>}
      </main>
    </div>
  </div>;
};

const StatusBadge: React.FC<{ active: boolean }> = ({ active }) => <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, borderRadius: 20, padding: '5px 9px', background: active ? '#ecfdf5' : '#fff7ed', color: active ? '#047857' : '#c2410c', fontWeight: 750, fontSize: 10, letterSpacing: 0.5, whiteSpace: 'nowrap' }}>{active ? <CircleCheck size={13} /> : <CircleX size={13} />}{active ? 'ACTIVE' : 'INACTIVE'}</span>;

const labelStyle: React.CSSProperties = { display: 'grid', gap: 6, fontSize: 13, color: '#334155', fontWeight: 650 };
const navButtonStyle: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 12, width: '100%', padding: '12px 14px', border: 0, borderRadius: 9, cursor: 'pointer', textAlign: 'left', background: 'transparent', fontWeight: 650 };
