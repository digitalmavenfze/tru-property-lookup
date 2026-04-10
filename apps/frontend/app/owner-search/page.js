'use client';

import { useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://72.61.117.207:8050';

export default function OwnerSearchPage() {
  const [phone, setPhone] = useState('971504452757');
  const [token, setToken] = useState(typeof window !== 'undefined' ? (localStorage.getItem('tpl_token') || '') : '');
  const [searchData, setSearchData] = useState(null);
  const [ownerData, setOwnerData] = useState(null);
  const [loading, setLoading] = useState(false);

  async function runOwnerFlow() {
    if (!token) return alert('Please login from dashboard first');
    setLoading(true);
    try {
      const searchRes = await fetch(`${API_BASE}/search?phone=${encodeURIComponent(phone)}&limit=1`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const searchJson = await searchRes.json();
      setSearchData(searchJson);

      const ownerId = searchJson?.results?.[0]?.owner_id;
      if (!ownerId) {
        setOwnerData({ detail: 'No owner found' });
        return;
      }

      const ownerRes = await fetch(`${API_BASE}/owners/${ownerId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const ownerJson = await ownerRes.json();
      setOwnerData(ownerJson);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ fontFamily: 'Arial, sans-serif', background: '#f6f7fb', minHeight: '100vh', padding: 24 }}>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, flexWrap: 'wrap', gap: 10 }}>
          <div>
            <h1 style={{ margin: 0 }}>Owner Detail Lookup</h1>
            <p style={{ margin: '6px 0 0', color: '#666' }}>Billing-aware owner search flow using phone search first, then owner detail</p>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <a href="/" style={btn}>Dashboard</a>
            <a href="/billing" style={btn}>Billing</a>
          </div>
        </div>

        <section style={card}>
          <h2 style={{ marginTop: 0 }}>Search Owner by Phone</h2>
          <input value={token} onChange={(e) => setToken(e.target.value)} placeholder="Session token" style={input} />
          <div style={{ height: 10 }} />
          <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Phone" style={input} />
          <button onClick={runOwnerFlow} style={primaryBtn}>
            {loading ? 'Loading...' : 'Run Owner Detail Flow'}
          </button>
        </section>

        <section style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={card}>
            <h3 style={{ marginTop: 0 }}>Search Response</h3>
            <pre style={pre}>{JSON.stringify(searchData, null, 2)}</pre>
          </div>
          <div style={card}>
            <h3 style={{ marginTop: 0 }}>Owner Detail Response</h3>
            <pre style={pre}>{JSON.stringify(ownerData, null, 2)}</pre>
          </div>
        </section>
      </div>
    </main>
  );
}

const card = { background: '#fff', borderRadius: 16, padding: 18, boxShadow: '0 8px 24px rgba(15,23,42,0.06)' };
const input = { width: '100%', padding: '12px 14px', border: '1px solid #d7deea', borderRadius: 10, fontSize: 14, boxSizing: 'border-box' };
const primaryBtn = { marginTop: 12, padding: '12px 16px', border: 0, borderRadius: 10, background: '#111827', color: '#fff', cursor: 'pointer', fontWeight: 600 };
const btn = { textDecoration: 'none', padding: '10px 14px', borderRadius: 10, background: '#111827', color: '#fff', fontWeight: 600 };
const pre = { marginTop: 14, background: '#0b1020', color: '#d1e7ff', padding: 14, borderRadius: 12, overflow: 'auto', fontSize: 12, whiteSpace: 'pre-wrap', minHeight: 320 };
