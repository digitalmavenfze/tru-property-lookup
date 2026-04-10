'use client';

import { useEffect, useMemo, useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://72.61.117.207:8050';

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function HomePage() {
  const [token, setToken] = useState('');
  const [me, setMe] = useState(null);
  const [billing, setBilling] = useState(null);
  const [loadingMe, setLoadingMe] = useState(false);

  const [searchPhone, setSearchPhone] = useState('971504452757');
  const [searchResult, setSearchResult] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);

  const [aiQuery, setAiQuery] = useState('find villas owned by Lara in Palma');
  const [aiResult, setAiResult] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);

  useEffect(() => {
    const saved = typeof window !== 'undefined' ? localStorage.getItem('tpl_token') : '';
    if (saved) {
      setToken(saved);
      loadProfile(saved);
    }
  }, []);

  async function loadProfile(activeToken = token) {
    if (!activeToken) return;
    setLoadingMe(true);
    try {
      const [meRes, billingRes] = await Promise.all([
        fetch(`${API_BASE}/me`, { headers: { ...authHeaders(activeToken) }, cache: 'no-store' }),
        fetch(`${API_BASE}/billing/me`, { headers: { ...authHeaders(activeToken) }, cache: 'no-store' }),
      ]);

      if (meRes.ok) setMe(await meRes.json());
      if (billingRes.ok) setBilling(await billingRes.json());
    } finally {
      setLoadingMe(false);
    }
  }

  async function handleLogin(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const payload = {
      email: String(form.get('email') || ''),
      password: String(form.get('password') || ''),
    };

    const res = await fetch(`${API_BASE}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || 'Login failed');
      return;
    }

    setToken(data.session_token);
    localStorage.setItem('tpl_token', data.session_token);
    setMe(data.user);
    await loadProfile(data.session_token);
  }

  async function runSearch() {
    if (!token) return alert('Please login first');
    setSearchLoading(true);
    try {
      const url = new URL(`${API_BASE}/search`);
      url.searchParams.set('phone', searchPhone);
      url.searchParams.set('limit', '1');

      const res = await fetch(url.toString(), {
        headers: { ...authHeaders(token) },
      });
      const data = await res.json();
      setSearchResult(data);
      await loadProfile(token);
    } finally {
      setSearchLoading(false);
    }
  }

  async function runAiSearch() {
    if (!token) return alert('Please login first');
    setAiLoading(true);
    try {
      const url = new URL(`${API_BASE}/search-ai`);
      url.searchParams.set('q', aiQuery);

      const res = await fetch(url.toString(), {
        headers: { ...authHeaders(token) },
      });
      const data = await res.json();
      setAiResult(data);
      await loadProfile(token);
    } finally {
      setAiLoading(false);
    }
  }

  const usagePercent = useMemo(() => {
    if (!billing?.monthly_search_limit) return 0;
    return Math.min(
      100,
      Math.round(((billing.monthly_search_count || 0) / billing.monthly_search_limit) * 100)
    );
  }, [billing]);

  return (
    <main style={{ fontFamily: 'Arial, sans-serif', background: '#f6f7fb', minHeight: '100vh', padding: 24 }}>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, gap: 12, flexWrap: 'wrap' }}>
          <div>
            <h1 style={{ margin: 0 }}>Tru Property Lookup</h1>
            <p style={{ margin: '6px 0 0', color: '#666' }}>SaaS dashboard, billing, search, AI search, and owner lookup</p>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <a href="/" style={navBtn}>Dashboard</a>
            <a href="/billing" style={navBtn}>Billing</a>
            <a href="/owner-search" style={navBtn}>Owner Detail</a>
            <a href="/admin/plans" style={navBtn}>Admin Plans</a>
          </div>
        </div>

        {!token ? (
          <section style={card}>
            <h2 style={{ marginTop: 0 }}>Login</h2>
            <form onSubmit={handleLogin} style={{ display: 'grid', gap: 12, maxWidth: 420 }}>
              <input name="email" defaultValue="demo@truproplookup.trucrm.io" placeholder="Email" style={input} />
              <input name="password" defaultValue="Demo@123456" type="password" placeholder="Password" style={input} />
              <button type="submit" style={primaryBtn}>Login</button>
            </form>
          </section>
        ) : (
          <>
            <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 16, marginBottom: 20 }}>
              <div style={card}>
                <div style={label}>Plan</div>
                <div style={metric}>{billing?.plan_name || me?.plan_name || '-'}</div>
                <div style={subtle}>{me?.email}</div>
              </div>
              <div style={card}>
                <div style={label}>Credits Balance</div>
                <div style={metric}>{billing?.credits_balance ?? me?.credits_balance ?? 0}</div>
                <div style={subtle}>Remaining credits</div>
              </div>
              <div style={card}>
                <div style={label}>Monthly Search Usage</div>
                <div style={metric}>{billing?.monthly_search_count ?? 0} / {billing?.monthly_search_limit ?? 0}</div>
                <div style={{ marginTop: 10, height: 10, background: '#e8ecf5', borderRadius: 999 }}>
                  <div style={{ width: `${usagePercent}%`, height: '100%', borderRadius: 999, background: '#1d4ed8' }} />
                </div>
              </div>
              <div style={card}>
                <div style={label}>Billing Status</div>
                <div style={metric}>{billing?.billing_status || me?.billing_status || '-'}</div>
                <div style={subtle}>Reset: {billing?.credits_reset_at || me?.credits_reset_at || '-'}</div>
              </div>
            </section>

            <section style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
              <div style={card}>
                <h3 style={{ marginTop: 0 }}>Standard Search</h3>
                <input value={searchPhone} onChange={(e) => setSearchPhone(e.target.value)} style={input} />
                <button onClick={runSearch} disabled={searchLoading} style={primaryBtn}>
                  {searchLoading ? 'Searching...' : 'Run Search'}
                </button>
                {searchResult && <pre style={pre}>{JSON.stringify(searchResult, null, 2)}</pre>}
              </div>

              <div style={card}>
                <h3 style={{ marginTop: 0 }}>AI Search</h3>
                <textarea value={aiQuery} onChange={(e) => setAiQuery(e.target.value)} style={{ ...input, minHeight: 90 }} />
                <button onClick={runAiSearch} disabled={aiLoading} style={primaryBtn}>
                  {aiLoading ? 'Running...' : 'Run AI Search'}
                </button>
                {aiResult && <pre style={pre}>{JSON.stringify(aiResult, null, 2)}</pre>}
              </div>
            </section>

            <section style={card}>
              <h3 style={{ marginTop: 0 }}>Session</h3>
              {loadingMe ? <p>Loading profile...</p> : <pre style={pre}>{JSON.stringify({ me, billing }, null, 2)}</pre>}
            </section>
          </>
        )}
      </div>
    </main>
  );
}

const card = {
  background: '#fff',
  borderRadius: 16,
  padding: 18,
  boxShadow: '0 8px 24px rgba(15,23,42,0.06)',
};

const input = {
  width: '100%',
  padding: '12px 14px',
  border: '1px solid #d7deea',
  borderRadius: 10,
  fontSize: 14,
  boxSizing: 'border-box',
};

const primaryBtn = {
  marginTop: 12,
  padding: '12px 16px',
  border: 0,
  borderRadius: 10,
  background: '#111827',
  color: '#fff',
  cursor: 'pointer',
  fontWeight: 600,
};

const navBtn = {
  textDecoration: 'none',
  padding: '10px 14px',
  borderRadius: 10,
  background: '#111827',
  color: '#fff',
  fontWeight: 600,
};

const metric = {
  fontSize: 28,
  fontWeight: 700,
  marginTop: 6,
};

const label = {
  fontSize: 12,
  color: '#6b7280',
  textTransform: 'uppercase',
  letterSpacing: '.06em',
};

const subtle = {
  color: '#6b7280',
  marginTop: 8,
  fontSize: 13,
};

const pre = {
  marginTop: 14,
  background: '#0b1020',
  color: '#d1e7ff',
  padding: 14,
  borderRadius: 12,
  overflow: 'auto',
  fontSize: 12,
  whiteSpace: 'pre-wrap',
};
