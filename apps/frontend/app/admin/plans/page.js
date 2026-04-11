'use client';

import { useEffect, useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://truproplookup.trucrm.io/api';

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function AdminPlansPage() {
  const [token, setToken] = useState('');
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    const saved = typeof window !== 'undefined' ? localStorage.getItem('tpl_token') : '';
    if (saved) {
      setToken(saved);
      loadUsers(saved);
    }
  }, []);

  async function loadUsers(activeToken = token) {
    if (!activeToken) return;
    setLoading(true);
    setMessage('');
    try {
      const res = await fetch(`${API_BASE}/admin/users`, {
        headers: { ...authHeaders(activeToken) },
        cache: 'no-store',
      });

      const data = await res.json();
      if (!res.ok) {
        setMessage(data.detail || 'Failed to load users');
        setUsers([]);
        return;
      }
      setUsers(data.results || []);
    } catch {
      setMessage('Failed to load users');
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }

  async function postAction(userId, path, body) {
    setMessage('');
    const res = await fetch(`${API_BASE}/admin/users/${userId}/${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(token),
      },
      body: JSON.stringify(body || {}),
    });

    const data = await res.json();
    if (!res.ok) {
      setMessage(data.detail || 'Action failed');
      return;
    }

    setMessage(data.message || 'Updated');
    await loadUsers(token);
  }

  return (
    <div style={{ padding: 24, fontFamily: 'Arial, sans-serif', background: '#f7f7f7', minHeight: '100vh' }}>
      <div style={{ maxWidth: 1400, margin: '0 auto' }}>
        <h1 style={{ marginBottom: 8 }}>Admin Billing Actions</h1>
        <p style={{ color: '#555', marginTop: 0 }}>
          Manage plans, credits, monthly usage, and superadmin access.
        </p>

        <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
          <a href="/" style={btn}>Home</a>
          <button onClick={() => loadUsers(token)} style={btn} disabled={loading}>
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>

        {message ? <div style={notice}>{message}</div> : null}

        <div style={{ overflowX: 'auto', background: '#fff', borderRadius: 12, padding: 16, boxShadow: '0 2px 10px rgba(0,0,0,0.06)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 1200 }}>
            <thead>
              <tr>
                {['Name', 'Email', 'Plan', 'Credits', 'Monthly Used', 'Monthly Limit', 'Billing', 'Superadmin', 'Actions'].map((h) => (
                  <th key={h} style={th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td style={td}>{u.full_name}</td>
                  <td style={td}>{u.email}</td>
                  <td style={td}>{u.plan_code}</td>
                  <td style={td}>{u.credits_balance}</td>
                  <td style={td}>{u.monthly_search_count}</td>
                  <td style={td}>{u.monthly_search_limit}</td>
                  <td style={td}>{u.billing_status}</td>
                  <td style={td}>{u.is_superadmin ? 'Yes' : 'No'}</td>
                  <td style={td}>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      <button style={smallBtn} onClick={() => postAction(u.id, 'plan', { plan_code: 'starter', billing_status: 'active' })}>Starter</button>
                      <button style={smallBtn} onClick={() => postAction(u.id, 'plan', { plan_code: 'pro', billing_status: 'active' })}>Pro</button>
                      <button style={smallBtn} onClick={() => postAction(u.id, 'plan', { plan_code: 'enterprise', billing_status: 'active' })}>Enterprise</button>
                      <button style={smallBtn} onClick={() => postAction(u.id, 'credits', {
                        credits_balance: 500,
                        monthly_search_count: u.monthly_search_count || 0,
                        monthly_search_limit: 500,
                        reason: 'Admin manual credit update'
                      })}>Set 500 Credits</button>
                      <button style={smallBtn} onClick={() => postAction(u.id, 'reset-usage', {})}>Reset Usage</button>
                      <button style={smallBtn} onClick={() => postAction(u.id, 'superadmin', { is_superadmin: !u.is_superadmin })}>
                        {u.is_superadmin ? 'Remove Admin' : 'Make Admin'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!users.length && !loading ? (
                <tr>
                  <td colSpan={9} style={td}>No users found.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

const btn = {
  display: 'inline-block',
  padding: '10px 14px',
  borderRadius: 8,
  border: '1px solid #ccc',
  background: '#fff',
  cursor: 'pointer',
  textDecoration: 'none',
  color: '#111',
};

const smallBtn = {
  padding: '8px 10px',
  borderRadius: 8,
  border: '1px solid #d0d0d0',
  background: '#fafafa',
  cursor: 'pointer',
};

const th = {
  textAlign: 'left',
  padding: 10,
  borderBottom: '1px solid #ddd',
  fontSize: 14,
};

const td = {
  padding: 10,
  borderBottom: '1px solid #eee',
  verticalAlign: 'top',
  fontSize: 14,
};

const notice = {
  marginBottom: 16,
  padding: 12,
  background: '#eef6ff',
  border: '1px solid #cfe4ff',
  borderRadius: 10,
};
