import React, { useState } from 'react';
import { Send, Sparkles } from 'lucide-react';
import { api } from './api';

interface ChatMessage {
  sender: 'user' | 'bot';
  text: string;
  sources?: string[];
}

export const InsuranceAssistantPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      sender: 'bot',
      text: 'Hello! I am your AI Insurance Policy & Claim Assistant. Ask me anything about policy coverages, deductibles, required documents, or claim procedures.',
      sources: ['Motor Policy Guidelines § 4']
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const sendQuestion = async (question: string) => {
    const userText = question.trim();
    if (!userText || loading) return;

    setMessages((prev) => [...prev, { sender: 'user', text: userText }]);
    setInput('');
    setLoading(true);

    try {
      const res = await api.post('/chatbot/chat', { message: userText }, { timeout: 180000 });
      setMessages((prev) => [
        ...prev,
        {
          sender: 'bot',
          text: res.data.response || res.data.answer || 'The policy knowledge base returned no answer. Please try again.',
          sources: res.data.sources || []
        }
      ]);
    } catch (err: any) {
      console.error('Chatbot request error:', err);
      setMessages((prev) => [
        ...prev,
        {
          sender: 'bot',
          text: err.response?.data?.detail || 'I could not reach the policy knowledge base. Check that the backend and RAG service are running, then try again.',
          sources: []
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    void sendQuestion(input);
  };

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem', height: 'calc(100vh - 140px)' }}>
      {/* HEADER */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <div style={{ padding: '0.6rem', background: '#e0f2fe', color: '#0284c7', borderRadius: '12px' }}>
          <Sparkles size={24} />
        </div>
        <div>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0f172a' }}>Insurance Assistant</h2>
          <p style={{ color: '#475569', fontSize: '0.875rem' }}>Ask grounded questions about policy terms, claim statuses, and required documents.</p>
        </div>
      </div>

      {/* CHAT CONTAINER */}
      <div className="glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#ffffff', overflow: 'hidden' }}>
        <div style={{ flex: 1, padding: '1.5rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem', background: '#f8fafc' }}>
          {messages.map((m, idx) => (
            <div
              key={idx}
              style={{
                alignSelf: m.sender === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '85%',
                padding: '1rem 1.25rem',
                borderRadius: 'var(--radius-lg)',
                background: m.sender === 'user' ? '#0284c7' : '#ffffff',
                color: m.sender === 'user' ? 'white' : '#0f172a',
                border: m.sender === 'user' ? 'none' : '1px solid #e2e8f0',
                fontSize: '0.9rem',
                lineHeight: '1.6',
                boxShadow: 'var(--shadow-sm)',
                whiteSpace: 'pre-wrap'
              }}
            >
              <p style={{ margin: 0 }}>{m.text}</p>
              {m.sources && m.sources.length > 0 && (
                <div style={{ marginTop: '0.6rem', borderTop: '1px solid #e2e8f0', paddingTop: '0.4rem', fontSize: '0.75rem', color: m.sender === 'user' ? '#bae6fd' : '#64748b' }}>
                  <strong>Knowledge Sources:</strong> {m.sources.join(', ')}
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div
              style={{
                alignSelf: 'flex-start',
                padding: '0.75rem 1.25rem',
                borderRadius: 'var(--radius-lg)',
                background: '#ffffff',
                color: '#64748b',
                border: '1px solid #e2e8f0',
                fontSize: '0.85rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}
            >
              <span className="spinner" style={{ width: '14px', height: '14px', borderWidth: '2px', borderColor: '#0284c7', borderRightColor: 'transparent' }}></span>
              Consulting insurance policy knowledge base & generating response...
            </div>
          )}
        </div>

        {/* PROMPT CHIPS */}
        <div style={{ padding: '0.5rem 1rem', background: '#f1f5f9', display: 'flex', gap: '0.5rem', overflowX: 'auto', borderTop: '1px solid #e2e8f0' }}>
          {[
            'What documents are needed for a claim?',
            'What are the general exclusions under my policy?',
            'Is bumper replacement covered under the policy?',
            'What is the standard deductible for collision damage?',
            'How does zero-depreciation cover work?',
            'Is engine damage covered under the policy?'
          ].map((promptText, i) => (
            <button
              key={i}
              type="button"
              onClick={() => void sendQuestion(promptText)}
              disabled={loading}
              style={{
                padding: '0.35rem 0.75rem',
                fontSize: '0.78rem',
                background: '#ffffff',
                border: '1px solid #cbd5e1',
                borderRadius: '999px',
                color: '#334155',
                cursor: 'pointer',
                whiteSpace: 'nowrap'
              }}
            >
              {promptText}
            </button>
          ))}
        </div>

        {/* INPUT */}
        <form onSubmit={handleSend} style={{ padding: '1rem', borderTop: '1px solid var(--border-color)', background: '#ffffff', display: 'flex', gap: '0.75rem' }}>
          <input
            type="text"
            placeholder="Ask about policy coverage, deductible, required documents..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
            style={{
              flex: 1,
              padding: '0.85rem 1rem',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.9rem',
              outline: 'none'
            }}
          />
          <button type="submit" className="btn-primary" disabled={loading} style={{ padding: '0.85rem 1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Send size={18} />
          </button>
        </form>
      </div>
    </div>
  );
};

