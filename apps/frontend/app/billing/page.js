'use client';

import { useEffect, useMemo, useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://72.61.117.207:8050';

export default function BillingPage() {
  const [token, setToken] = useState('');
  const [billing, setBilling] = useState(null);
  const [usage, setUsage] = useState([]);
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
      const [billingRes, usageRes] = await Promise.all([
        fetch(`${API_BASE}/billing/me`, {
          headers: { Authorization: `Bearer ${activeToken}` },
          cache: 'no-store',
        }),
        fetch(`${API_BASE}/billing/usage`, {
          headers: { Authorization: `Bearer ${activeToken}` },
          cache: 'no-store',
        }),
      ]);

      if (billingRes.ok) setBilling(await billingRes.json());
      if (usageRes.ok) {
        const usageData = await usageRes.json();
        setUsage(usageData.results || []);
      }
    } finally {
      setLoading(false);
    }
  }

  const usagePercent = useMemo(() => {
    if (!billing?.monthly_search_limit) return 0;
    return Math.min(100, Math.round(((billing.monthly_search_count || 0) / billing.monthly_search_limit) * 100));
  }, [billing]);

  if (!token) {
    return <main style={wrap}><div style={card}>Please login from the dashboard first.</div></main>;
  }

  return (
    <main style={wrap}>
      <div style={container}>
        <div style={topRow}>
          <div>
            <h1 style={{ margin: 0 }}>Billing & Usage</h1>
            <p style={{ color: '#666', marginTop: 6 }}>Credits, monthly usage, features, and recent billing activity</p>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <a href="/" style={btn}>Dashboard</a>
            <a href="/owner-search" style={btn}>Owner Detail</a>
          </div>
        </div>

        {loading ? (
          <div style={card}>Loading...</div>
        ) : (
          <>
            <section style={grid}>
              <div style={card}>
                <div style={label}>Plan</div>
                <div style={metric}>{billing?.plan_name || '-'}</div>
                <div style={mini}>Code: {billing?.plan_code || '-'}</div>
              </div>
              <div style={card}>
                <div style={label}>Credits</div>
                <div style={metric}>{billing?.credits_balance ?? 0}</div>
                <div style={mini}>Monthly credits: {billing?.plan_monthly_credits ?? 0}</div>
              </div>
              <div style={card}>
                <div style={label}>Monthly Search Count</div>
                <div style={metric}>{billing?.monthly_search_count ?? 0} / {billing?.monthly_search_limit ?? 0}</div>
                <div style={{ marginTop: 10, height: 10, background: '#e5e7eb', borderRadius: 999 }}>
                  <div style={{ width: `${usagePercent}%`, height: '100%', borderRadius: 999, background: '#2563eb' }} />
                </div>
              </div>
              <div style={card}>
                <div style={label}>Status</div>
                <div style={metric}>{billing?.billing_status || '-'}</div>
                <div style={mini}>Reset at: {billing?.credits_reset_at || '-'}</div>
              </div>
            </section>

            <section style={card}>
              <h2 style={{ marginTop: 0 }}>Plan Features</h2>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                {Object.entries(billing?.features || {}).map(([k, v]) => (
                  <span key={k} style={{ ...pill, background: v ? '#dcfce7' : '#fee2e2', color: '#111827' }}>
                    {k}: {String(v)}
                  </span>
                ))}
              </div>
            </section>

            <section style={card}>
              <h2 style={{ marginTop: 0 }}>Recent Usage</h2>
              <div style={{ overflowX: 'auto' }}>
                <table style={table}>
                  <thead>
                    <tr>
                      <th style={th}>Time</th>
                      <th style={th}>Endpoint</th>
                      <th style={th}>Query</th>
                      <th style={th}>Credits</th>
                      <th style={th}>Results</th>
                      <th style={th}>Tier</th>
                      <th style={th}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usage.length === 0 ? (
                      <tr><td colSpan="7" style={td}>No usage yet</td></tr>
                    ) : usage.map((row) => (
                      <tr key={row.id}>
                        <td style={td}>{row.created_at}</td>
                        <td style={td}>{row.endpoint}</td>
                        <td style={td}>{row.query_text}</td>
                        <td style={td}>{row.credits_used}</td>
                        <td style={td}>{row.result_count}</td>
                        <td style={td}>{row.area_tier}</td>
                        <td style={td}>{row.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
}

const wrap = { fontFamily: 'Arial, sans-serif', background: '#f6f7fb', minHeight: '100vh', padding: 24 };
const container = { maxWidth: 1200, margin: '0 auto' };
const topRow = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, gap: 12, flexWrap: 'wrap' };
const grid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 16, marginBottom: 20 };
const card = { background: '#fff', borderRadius: 16, padding: 18, boxShadow: '0 8px 24px rgba(15,23,42,0.06)', marginBottom: 18 };
const btn = { textDecoration: 'none', padding: '10px 14px', borderRadius: 10, background: '#111827', color: '#fff', fontWeight: 600 };
const label = { fontSize: 12, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '.06em' };
const metric = { fontSize: 28, fontWeight: 700, marginTop: 6 };
const mini = { fontSize: 13, color: '#6b7280', marginTop: 8 };
const pill = { padding: '8px 10px', borderRadius: 999, fontSize: 13, fontWeight: 600 };
const table = { width: '100%', borderCollapse: 'collapse' };
const th = { textAlign: 'left', padding: 12, borderBottom: '1px solid #e5e7eb', fontSize: 13, color: '#6b7280' };
const td = { textAlign: 'left', padding: 12, borderBottom: '1px solid #f0f2f6', fontSize: 13, verticalAlign: 'top' };
