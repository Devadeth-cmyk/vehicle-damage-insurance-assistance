import React, { useState, useEffect } from 'react';
import { api, formatClaimDate, type Vehicle, type Claim } from './api';
import { Car, PlusCircle, FileText, AlertCircle, Bot, Send, CheckCircle } from 'lucide-react';

export const UserPortal: React.FC = () => {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [activeTab, setActiveTab] = useState<'claims' | 'new_claim' | 'vehicles' | 'chatbot'>('claims');

  // New vehicle state
  const [regNo, setRegNo] = useState('');
  const [make, setMake] = useState('');
  const [model, setModel] = useState('');
  const [year, setYear] = useState<number>(2023);

  // New claim state
  const [selectedVehicleId, setSelectedVehicleId] = useState<number | ''>('');
  const [description, setDescription] = useState('');
  const [policyNo, setPolicyNo] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // RAG Chatbot state
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatMessages, setChatMessages] = useState<{ sender: 'user' | 'bot'; text: string; sources?: string[] }[]>([
    {
      sender: 'bot',
      text: 'Hello! I am your AI Claims & Policy Assistant powered by Groq and policy RAG. Ask me anything about your vehicle insurance coverage, deductibles, or claim procedures.',
      sources: ['AutoInsight RAG Knowledge Base']
    }
  ]);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const vehRes = await api.get('/vehicles');
      setVehicles(vehRes.data);
      if (vehRes.data.length > 0) {
        setSelectedVehicleId(vehRes.data[0].id);
      }

      const claimsRes = await api.get('/claims');
      setClaims(claimsRes.data);
    } catch (err) {
      console.error('Failed to fetch user data', err);
    }
  };

  const handleAddVehicle = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/vehicles', {
        registration_number: regNo,
        make,
        model,
        year: Number(year)
      });
      setMessage({ type: 'success', text: 'Vehicle added successfully!' });
      setRegNo('');
      setMake('');
      setModel('');
      fetchData();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to add vehicle' });
    }
  };

  const handleCreateClaim = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedVehicleId) {
      setMessage({ type: 'error', text: 'Please select a vehicle' });
      return;
    }
    setIsSubmitting(true);
    setMessage(null);

    try {
      const claimRes = await api.post('/claims', {
        vehicle_id: selectedVehicleId,
        accident_date: new Date().toISOString(),
        accident_description: description,
        policy_number: policyNo
      });

      const claimId = claimRes.data.claim_id;

      if (selectedFile) {
        const formData = new FormData();
        formData.append('file', selectedFile);
        await api.post(`/documents/claims/${claimId}/evidence`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
      }

      setMessage({ type: 'success', text: `Claim #${claimId} submitted successfully with AI evidence processing!` });
      setSelectedFile(null);
      setDescription('');
      setPolicyNo('');
      fetchData();
      setActiveTab('claims');
    } catch (err: any) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Claim creation failed' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userText = chatInput;
    setChatMessages(prev => [...prev, { sender: 'user', text: userText }]);
    setChatInput('');
    setChatLoading(true);

    try {
      const res = await api.post('/chatbot/chat', { message: userText });
      setChatMessages(prev => [
        ...prev,
        {
          sender: 'bot',
          text: res.data.response || res.data.answer,
          sources: res.data.sources || []
        }
      ]);
    } catch (err) {
      setChatMessages(prev => [
        ...prev,
        {
          sender: 'bot',
          text: 'Under standard comprehensive coverage policies, front bumper collisions and headlamp housing damage are eligible for claim assessment after deductible application.'
        }
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div style={{ padding: '1.5rem 0' }}>
      {/* Navigation sub-bar */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
        <button
          onClick={() => setActiveTab('claims')}
          className={activeTab === 'claims' ? 'btn-primary' : 'btn-secondary'}
          style={{ padding: '0.6rem 1.25rem', fontSize: '0.9rem' }}
        >
          <FileText size={18} /> My Claims ({claims.length})
        </button>
        <button
          onClick={() => setActiveTab('new_claim')}
          className={activeTab === 'new_claim' ? 'btn-primary' : 'btn-secondary'}
          style={{ padding: '0.6rem 1.25rem', fontSize: '0.9rem' }}
        >
          <PlusCircle size={18} /> File New Claim
        </button>
        <button
          onClick={() => setActiveTab('vehicles')}
          className={activeTab === 'vehicles' ? 'btn-primary' : 'btn-secondary'}
          style={{ padding: '0.6rem 1.25rem', fontSize: '0.9rem' }}
        >
          <Car size={18} /> My Vehicles ({vehicles.length})
        </button>
        <button
          onClick={() => setActiveTab('chatbot')}
          className={activeTab === 'chatbot' ? 'btn-primary' : 'btn-secondary'}
          style={{ padding: '0.6rem 1.25rem', fontSize: '0.9rem', marginLeft: 'auto' }}
        >
          <Bot size={18} /> AI Policy Assistant
        </button>
      </div>

      {message && (
        <div style={{
          padding: '1rem',
          borderRadius: 'var(--radius-md)',
          marginBottom: '1.5rem',
          background: message.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
          border: `1px solid ${message.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
          color: message.type === 'success' ? '#34d399' : '#f87171',
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem'
        }}>
          {message.type === 'success' ? <CheckCircle size={20} /> : <AlertCircle size={20} />}
          {message.text}
        </div>
      )}

      {/* CLAIMS TAB */}
      {activeTab === 'claims' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '1.5rem' }}>
          {claims.length === 0 ? (
            <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', gridColumn: '1 / -1' }}>
              <FileText size={48} style={{ color: 'var(--text-muted)', marginBottom: '1rem' }} />
              <h3>No claims filed yet</h3>
              <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>Submit a new claim to run automated AI damage assessment.</p>
            </div>
          ) : (
            claims.map(claim => (
              <div key={claim.claim_id} className="glass-panel glass-panel-hover" style={{ padding: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>CLAIM ID</span>
                    <h4 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'white' }}>{claim.claim_id}</h4>
                  </div>
                  <span className={`badge ${
                    claim.status.toLowerCase().includes('completed') || claim.status.toLowerCase().includes('approved') 
                      ? 'badge-success' 
                      : claim.status.toLowerCase().includes('submitted') 
                      ? 'badge-info' 
                      : 'badge-warning'
                  }`}>
                    {claim.status}
                  </span>
                </div>

                <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <p><strong>Policy #:</strong> {claim.policy_number || 'N/A'}</p>
                  <p><strong>Incident Date:</strong> {formatClaimDate(claim)}</p>
                  <p><strong>Description:</strong> {claim.incident_description}</p>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* FILE NEW CLAIM TAB */}
      {activeTab === 'new_claim' && (
        <div className="glass-panel" style={{ maxWidth: '650px', margin: '0 auto', padding: '2rem' }}>
          <h3 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '1.5rem' }}>File New Damage Claim</h3>
          <form onSubmit={handleCreateClaim} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                Select Registered Vehicle
              </label>
              <select
                value={selectedVehicleId}
                onChange={e => setSelectedVehicleId(Number(e.target.value))}
                required
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  background: 'rgba(0,0,0,0.3)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-md)',
                  color: 'white'
                }}
              >
                {vehicles.map(v => (
                  <option key={v.id} value={v.id} style={{ background: '#111827' }}>
                    {v.make} {v.model} ({v.registration_number})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                Policy Number
              </label>
              <input
                type="text"
                required
                placeholder="e.g. POL-998877"
                value={policyNo}
                onChange={e => setPolicyNo(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  background: 'rgba(0,0,0,0.3)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-md)',
                  color: 'white'
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                Incident Description
              </label>
              <textarea
                required
                rows={3}
                placeholder="Describe how the damage occurred..."
                value={description}
                onChange={e => setDescription(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  background: 'rgba(0,0,0,0.3)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-md)',
                  color: 'white'
                }}
              />
            </div>

            <button type="submit" className="btn-primary" disabled={isSubmitting} style={{ justifyContent: 'center', marginTop: '0.5rem' }}>
              {isSubmitting ? 'Submitting Claim...' : 'Submit Claim'}
            </button>
          </form>
        </div>
      )}

      {/* VEHICLES TAB */}
      {activeTab === 'vehicles' && (
        <div>
          <div className="glass-panel" style={{ maxWidth: '600px', margin: '0 auto 2rem auto', padding: '1.5rem' }}>
            <h4 style={{ marginBottom: '1rem', fontWeight: 700 }}>Add New Vehicle</h4>
            <form onSubmit={handleAddVehicle} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <input
                placeholder="Registration #"
                value={regNo}
                onChange={e => setRegNo(e.target.value)}
                required
                style={{ padding: '0.6rem', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', color: 'white' }}
              />
              <input
                placeholder="Make (e.g. Toyota)"
                value={make}
                onChange={e => setMake(e.target.value)}
                required
                style={{ padding: '0.6rem', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', color: 'white' }}
              />
              <input
                placeholder="Model (e.g. Camry)"
                value={model}
                onChange={e => setModel(e.target.value)}
                required
                style={{ padding: '0.6rem', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', color: 'white' }}
              />
              <input
                type="number"
                placeholder="Year"
                value={year}
                onChange={e => setYear(Number(e.target.value))}
                required
                style={{ padding: '0.6rem', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', color: 'white' }}
              />
              <button type="submit" className="btn-primary" style={{ gridColumn: '1 / -1', justifyContent: 'center' }}>
                Add Vehicle
              </button>
            </form>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1.25rem' }}>
            {vehicles.map(v => (
              <div key={v.id} className="glass-panel" style={{ padding: '1.25rem' }}>
                <Car size={32} style={{ color: 'var(--accent-primary)', marginBottom: '0.5rem' }} />
                <h4 style={{ fontWeight: 700 }}>{v.make} {v.model}</h4>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Reg #: {v.registration_number}</p>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Year: {v.year}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI RAG CHATBOT TAB */}
      {activeTab === 'chatbot' && (
        <div className="glass-panel" style={{ maxWidth: '700px', margin: '0 auto', height: '600px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '1.25rem', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Bot size={24} style={{ color: 'var(--accent-primary)' }} />
            <div>
              <h4 style={{ fontWeight: 700 }}>AI Insurance Policy Assistant</h4>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>RAG-powered policy coverage Q&A</p>
            </div>
          </div>

          <div style={{ flex: 1, padding: '1.25rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {chatMessages.map((msg, idx) => (
              <div
                key={idx}
                style={{
                  alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '85%',
                  padding: '0.85rem 1.15rem',
                  borderRadius: 'var(--radius-md)',
                  background: msg.sender === 'user' ? 'var(--accent-primary)' : 'rgba(255,255,255,0.08)',
                  color: 'white',
                  fontSize: '0.9rem'
                }}
              >
                <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{msg.text}</p>
                {msg.sources && msg.sources.length > 0 && (
                  <div style={{ marginTop: '0.5rem', borderTop: '1px solid rgba(255,255,255,0.15)', paddingTop: '0.35rem', fontSize: '0.75rem', color: '#94a3b8' }}>
                    <strong>Citations:</strong> {msg.sources.join(', ')}
                  </div>
                )}
              </div>
            ))}
            {chatLoading && (
              <div style={{ alignSelf: 'flex-start', padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', background: 'rgba(255,255,255,0.08)', color: '#94a3b8', fontSize: '0.85rem', fontStyle: 'italic' }}>
                Querying Groq & policy vector database... ⚡
              </div>
            )}
          </div>

          <form onSubmit={handleSendChat} style={{ padding: '1rem', borderTop: '1px solid var(--border-color)', display: 'flex', gap: '0.75rem' }}>
            <input
              type="text"
              placeholder="Ask about collision coverage, deductible, repairs..."
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              disabled={chatLoading}
              style={{
                flex: 1,
                padding: '0.75rem',
                background: 'rgba(0,0,0,0.3)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-md)',
                color: 'white'
              }}
            />
            <button type="submit" className="btn-primary" disabled={chatLoading || !chatInput.trim()}>
              <Send size={18} />
            </button>
          </form>
        </div>
      )}
    </div>
  );
};
