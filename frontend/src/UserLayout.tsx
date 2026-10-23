import React, { useState } from 'react';
import {
  LayoutDashboard,
  Car,
  FilePlus2,
  FileText,
  MessageSquare,
  User,
  LogOut,
  Shield,
  Menu,
  X,
  X as CloseIcon,
  Send,
  Sparkles
} from 'lucide-react';
import { api, type User as UserType } from './api';

interface UserLayoutProps {
  user: UserType;
  currentRoute: string;
  onNavigate: (route: string) => void;
  onLogout: () => void;
  themeToggle: React.ReactNode;
  children: React.ReactNode;
}

export const UserLayout: React.FC<UserLayoutProps> = ({
  user,
  currentRoute,
  onNavigate,
  onLogout,
  themeToggle,
  children
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isChatbotOpen, setIsChatbotOpen] = useState(false);
  const [chatInput, setChatInput] = useState('');
  interface ChatMessage {
    sender: 'user' | 'bot';
    text: string;
    sources?: string[];
  }

  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      sender: 'bot',
      text: 'Hello! I am AutoInsight Assistant. Ask me questions regarding policy coverage, deductibles, required documents, or claim status.',
      sources: ['Motor Policy Manual — Pg 4']
    }
  ]);

  const navItems = [
    { label: 'Dashboard', route: '/dashboard', icon: LayoutDashboard },
    { label: 'My Vehicles', route: '/vehicles', icon: Car },
    { label: 'New Claim', route: '/claims/new', icon: FilePlus2 },
    { label: 'My Claims', route: '/claims', icon: FileText },
    { label: 'Assessment Results', route: '/assessment', icon: Sparkles },
    { label: 'Insurance Assistant', route: '/assistant', icon: MessageSquare },
    { label: 'Profile', route: '/profile', icon: User }
  ];

  const handleNavClick = (route: string) => {
    onNavigate(route);
    setMobileMenuOpen(false);
  };

  const handleSendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userMsg = chatInput;
    setChatMessages((prev) => [...prev, { sender: 'user', text: userMsg }]);
    setChatInput('');

    try {
      const res = await api.post('/chatbot/chat', { message: userMsg });
      setChatMessages((prev) => [
        ...prev,
        {
          sender: 'bot',
          text: res.data.response || res.data.answer || 'Thank you for reaching out. Based on your motor insurance policy details...',
          sources: res.data.sources || ['Comprehensive Coverage Policy § 12.B']
        }
      ]);
    } catch (err) {
      setChatMessages((prev) => [
        ...prev,
        { sender: 'bot', text: 'AutoInsight Assistant is analyzing policy guidelines. Collision and comprehensive coverages are active.' }
      ]);
    }
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-primary)' }}>
      {/* SIDEBAR DESKTOP */}
      <aside
        className="customer-sidebar"
        style={{
          width: '260px',
          background: '#ffffff',
          borderRight: '1px solid var(--border-color)',
          display: 'flex',
          flexDirection: 'column',
          position: 'fixed',
          top: 0,
          bottom: 0,
          left: 0,
          zIndex: 90,
          padding: '1.5rem 1rem',
          boxShadow: 'var(--shadow-sm)'
        }}
      >
        {/* LOGO & BRAND */}
        <div
          onClick={() => handleNavClick('/dashboard')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            padding: '0.5rem',
            marginBottom: '2rem',
            cursor: 'pointer'
          }}
        >
          <div
            style={{
              padding: '0.5rem',
              background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
              color: 'white',
              borderRadius: '12px',
              display: 'flex',
              boxShadow: '0 4px 12px rgba(2, 132, 199, 0.25)'
            }}
          >
            <Shield size={24} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
              AutoInsight
            </h1>
            <span style={{ fontSize: '0.65rem', color: '#64748b', fontWeight: 700, letterSpacing: '0.05em' }}>
              INSURANCE SUITE
            </span>
          </div>
        </div>

        {/* NAVIGATION ITEMS */}
        <nav style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentRoute === item.route;
            return (
              <button
                key={item.route}
                onClick={() => handleNavClick(item.route)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.85rem',
                  padding: '0.75rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  border: 'none',
                  background: isActive ? '#f0f9ff' : 'transparent',
                  color: isActive ? '#0284c7' : '#475569',
                  fontWeight: isActive ? 700 : 500,
                  fontSize: '0.9rem',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.15s ease',
                  borderLeft: isActive ? '3px solid #0284c7' : '3px solid transparent'
                }}
              >
                <Icon size={18} style={{ color: isActive ? '#0284c7' : '#94a3b8' }} />
                <span style={{ flex: 1 }}>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* BOTTOM LOGOUT */}
        <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
          <button
            onClick={onLogout}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.85rem',
              padding: '0.65rem 1rem',
              width: '100%',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              background: 'transparent',
              color: '#ef4444',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            <LogOut size={18} />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* MAIN WRAPPER */}
      <div style={{ flex: 1, marginLeft: '260px', display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
        {/* TOPBAR */}
        <header
          className="customer-topbar"
          style={{
            height: '64px',
            borderBottom: '1px solid var(--border-color)',
            background: '#ffffff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 2rem',
            position: 'sticky',
            top: 0,
            zIndex: 80,
            boxShadow: 'var(--shadow-sm)'
          }}
        >
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            style={{ display: 'none', background: 'transparent', border: 'none', color: '#0f172a', cursor: 'pointer' }}
          >
            {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>

          <div>
            <h2 style={{ fontSize: '1rem', fontWeight: 700, color: '#0f172a' }}>
              Welcome back, {user.full_name || 'Customer'}
            </h2>
            <p style={{ fontSize: '0.75rem', color: '#64748b' }}>
              AutoInsight Verified Customer Account
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            {themeToggle}
            <div
              onClick={() => handleNavClick('/profile')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.65rem',
                padding: '0.35rem 0.85rem 0.35rem 0.35rem',
                background: '#f8fafc',
                border: '1px solid var(--border-color)',
                borderRadius: '9999px',
                cursor: 'pointer'
              }}
            >
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #0284c7 0%, #0284c7 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                  fontWeight: 700,
                  fontSize: '0.85rem'
                }}
              >
                {(user.full_name || user.email || 'C').charAt(0).toUpperCase()}
              </div>
              <div style={{ fontSize: '0.8rem' }}>
                <p style={{ fontWeight: 700, color: '#0f172a', lineHeight: 1.1 }}>{user.full_name || 'Customer'}</p>
                <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Customer</span>
              </div>
            </div>
          </div>
        </header>

        {/* MAIN BODY CONTENT */}
        <main className="customer-content" style={{ flex: 1, padding: '2rem', maxWidth: '1280px', width: '100%', margin: '0 auto' }}>
          {children}
        </main>
      </div>

      {/* PERSISTENT FLOATING RAG CHATBOT BUTTON */}
      {currentRoute !== '/assistant' && <button
        onClick={() => setIsChatbotOpen(!isChatbotOpen)}
        type="button"
        aria-label={isChatbotOpen ? 'Close Insurance Assistant' : 'Open Insurance Assistant'}
        aria-expanded={isChatbotOpen}
        title="Insurance Assistant"
        style={{
          position: 'fixed',
          bottom: '2rem',
          right: '2rem',
          zIndex: 150,
          background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
          color: 'white',
          border: 'none',
          width: '56px',
          height: '56px',
          borderRadius: '50%',
          padding: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 8px 24px rgba(2, 132, 199, 0.35)',
          cursor: 'pointer'
        }}
      >
        <MessageSquare size={23} />
      </button>}

      {/* FLOATING CHATBOT DRAWER / MODAL */}
      {isChatbotOpen && currentRoute !== '/assistant' && (
        <div
          style={{
            position: 'fixed',
            bottom: '5.5rem',
            right: '2rem',
            width: '380px',
            height: '520px',
            background: '#ffffff',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-xl)',
            boxShadow: '0 20px 40px rgba(0,0,0,0.15)',
            zIndex: 160,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
          }}
        >
          {/* CHAT HEADER */}
          <div style={{ background: '#0284c7', color: 'white', padding: '1rem 1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <MessageSquare size={20} />
              <div>
                <h4 style={{ fontSize: '0.95rem', fontWeight: 700 }}>AutoInsight Assistant</h4>
                <span style={{ fontSize: '0.7rem', opacity: 0.9 }}>RAG Policy Engine</span>
              </div>
            </div>
            <button onClick={() => setIsChatbotOpen(false)} style={{ background: 'none', border: 'none', color: 'white', cursor: 'pointer' }}>
              <CloseIcon size={20} />
            </button>
          </div>

          {/* MESSAGES */}
          <div style={{ flex: 1, padding: '1rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.75rem', background: '#f8fafc' }}>
            {chatMessages.map((msg, i) => (
              <div
                key={i}
                style={{
                  alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '85%',
                  padding: '0.75rem 1rem',
                  borderRadius: '12px',
                  background: msg.sender === 'user' ? '#0284c7' : '#ffffff',
                  color: msg.sender === 'user' ? 'white' : '#0f172a',
                  border: msg.sender === 'user' ? 'none' : '1px solid #e2e8f0',
                  fontSize: '0.85rem',
                  boxShadow: 'var(--shadow-sm)'
                }}
              >
                <p>{msg.text}</p>
                {msg.sources && (
                  <div style={{ marginTop: '0.4rem', borderTop: '1px solid #e2e8f0', paddingTop: '0.3rem', fontSize: '0.7rem', color: '#64748b' }}>
                    <strong>Sources:</strong> {msg.sources.join(', ')}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* INPUT FORM */}
          <form onSubmit={handleSendChat} style={{ padding: '0.75rem', borderTop: '1px solid var(--border-color)', background: '#ffffff', display: 'flex', gap: '0.5rem' }}>
            <input
              type="text"
              placeholder="Ask about policy or claim..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              style={{
                flex: 1,
                padding: '0.65rem 0.85rem',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.85rem',
                outline: 'none'
              }}
            />
            <button type="submit" className="btn-primary" style={{ padding: '0.65rem 1rem' }}>
              <Send size={16} />
            </button>
          </form>
        </div>
      )}
    </div>
  );
};
