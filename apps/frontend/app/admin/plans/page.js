'use client';

import { useEffect, useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://72.61.117.207:8050';

export default function AdminPlansPage() {
  const [token, setToken] = useState('');
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const saved = localStorage.getItem('tpl_token') || '';
    setToken(saved);
    if (saved) load(saved);
    else setLoading(false);
  }, []);

  async function load(activeToken) {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/plans`, {
        headers: { Authorization: `Bearer ${activeToken}` },
        cache: 'no-store',
      });
      const data = await res.json();
      setPlans(data.results || data || []);
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return <main style={wrap}><div style={card}>Please login first.</div></main>;
  }

  return (
    <main style={wrap}>
      <div style={container}>
        <div style={topRow}>
          <div>
            <h1 style={{ margin: 0 }}>Admin Plans</h1>
            <p style={{ color: '#666', marginTop: 6 }}>View active subscription plans and SaaS pricing configuration</p>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <a href="/" style={btn}>Dashboard</a>
            <a href="/billing" style={btn}>Billing</a>
          </div>
        </div>

        <section style={card}>
          {loading ? (
            <p>Loading plans...</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={table}>
                <thead>
                  <tr>
                    <th style={th}>Code</th>
                    <th style={th}>Name</th>
                    <th style={th}>Monthly Credits</th>
                    <th style={th}>Monthly Search Limit</th>
                    <th style={th}>Price USD</th>
                    <th style={th}>Active</th>
                  </tr>
                </thead>
                <tbody>
                  {plans.length === 0 ? (
                    <tr><td colSpan="6" style={td}>No plans found</td></tr>
                  ) : plans.map((p) => (
                    <tr key={p.code}>
                      <td style={td}>{p.code}</td>
                      <td style={td}>{p.name}</td>
                      <td style={td}>{p.monthly_credits}</td>
                      <td style={td}>{p.monthly_search_limit}</td>
                      <td style={td}>{p.price_usd}</td>
                      <td style={td}>{String(p.is_active)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

const wrap = { fontFamily: 'Arial, sans-serif', background: '#f6f7fb', minHeight: '100vh', padding: 24 };
const container = { maxWidth: 1100, margin: '0 auto' };
const topRow = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, gap: 12, flexWrap: 'wrap' };
const card = { background: '#fff', borderRadius: 16, padding: 18, boxShadow: '0 8px 24px rgba(15,23,42,0.06)' };
const btn = { textDecoration: 'none', padding: '10px 14px', borderRadius: 10, background: '#111827', color: '#fff', fontWeight: 600 };
const table = { width: '100%', borderCollapse: 'collapse' };
const th = { textAlign: 'left', padding: 12, borderBottom: '1px solid #e5e7eb', fontSize: 13, color: '#6b7280' };
const td = { textAlign: 'left', padding: 12, borderBottom: '1px solid #f0f2f6', fontSize: 14 };
