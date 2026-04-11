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
    try {
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

      setMessage(data.message || 'Action completed');
      await loadUsers(token);
    } catch {
      setMessage('Action failed');
    }
  }

  const page = {
    minHeight: '100vh',
    background: '#f6f8fb',
    padding: '24px',
    fontFamily: 'Arial, sans-serif',
  };

  const card = {
    maxWidth: 1400,
    margin: '0 auto',
    background: '#fff',
    borderRadius: 16,
    padding: 24,
    boxShadow: '0 10px 30px rgba(0,0,0,0.08)',
  };

  const tableWrap = {
    overflowX: 'auto',
    marginTop: 20,
    border: '1px solid #e5e7eb',
    borderRadius: 12,
  };

  const table = {
    width: '100%',
    borderCollapse: 'collapse',
    minWidth: 1200,
  };

  const th = {
    textAlign: 'left',
    padding: 12,
    background: '#f3f4f6',
    borderBottom: '1px solid #e5e7eb',
    fontSize: 14,
  };

  const td = {
    padding: 12,
    borderBottom: '1px solid #e5e7eb',
    fontSize: 14,
    verticalAlign: 'top',
  };

  const btn = {
    border: 'none',
    borderRadius: 8,
    padding: '8px 10px',
    cursor: 'pointer',
    fontWeight: 600,
    marginRight: 8,
    marginBottom: 8,
  };

  const greenBtn = { ...btn, background: '#dcfce7', color: '#166534' };
  const blueBtn = { ...btn, background: '#dbeafe', color: '#1d4ed8' };
  const amberBtn = { ...btn, background: '#fef3c7', color: '#92400e' };
  const redBtn = { ...btn, background: '#fee2e2', color: '#b91c1c' };
  const darkBtn = { ...btn, background: '#e5e7eb', color: '#111827' };

  return (
    <div style={page}>
      <div style={card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 30 }}>Admin Billing Actions</h1>
            <p style={{ color: '#6b7280', marginTop: 8 }}>
              Manage plans, credits, usage reset, billing status, and superadmin access.
            </p>
          </div>
          <button onClick={() => loadUsers()} style={darkBtn}>
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>

        {message ? (
          <div style={{
            marginTop: 16,
            padding: 12,
            borderRadius: 10,
            background: '#eff6ff',
            border: '1px solid #bfdbfe',
            color: '#1d4ed8',
            fontWeight: 600,
          }}>
            {message}
          </div>
        ) : null}

        <div style={tableWrap}>
          <table style={table}>
            <thead>
              <tr>
                <th style={th}>User</th>
                <th style={th}>Role</th>
                <th style={th}>Plan</th>
                <th style={th}>Credits</th>
                <th style={th}>Usage</th>
                <th style={th}>Billing</th>
                <th style={th}>Superadmin</th>
                <th style={th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 ? (
                <tr>
                  <td colSpan={8} style={td}>No users found.</td>
                </tr>
              ) : users.map((u) => (
                <tr key={u.id}>
                  <td style={td}>
                    <div style={{ fontWeight: 700 }}>{u.full_name || '—'}</div>
                    <div style={{ color: '#6b7280', marginTop: 4 }}>{u.email}</div>
                    <div style={{ color: '#9ca3af', marginTop: 4, fontSize: 12 }}>{u.id}</div>
                  </td>
                  <td style={td}>{u.role || '—'}</td>
                  <td style={td}>{u.plan_code || '—'}</td>
                  <td style={td}>{u.credits_balance ?? 0}</td>
                  <td style={td}>
                    {u.monthly_search_count ?? 0} / {u.monthly_search_limit ?? 0}
                  </td>
                  <td style={td}>{u.billing_status || '—'}</td>
                  <td style={td}>{u.is_superadmin ? 'Yes' : 'No'}</td>
                  <td style={td}>
                    <div>
                      <button onClick={() => postAction(u.id, 'plan', { plan_code: 'starter', billing_status: 'active' })} style={blueBtn}>Starter</button>
                      <button onClick={() => postAction(u.id, 'plan', { plan_code: 'pro', billing_status: 'active' })} style={greenBtn}>Pro</button>
                      <button onClick={() => postAction(u.id, 'plan', { plan_code: 'enterprise', billing_status: 'active' })} style={amberBtn}>Enterprise</button>
                    </div>

                    <div>
                      <button onClick={() => postAction(u.id, 'credits', { amount: 100, mode: 'add' })} style={greenBtn}>+100</button>
                      <button onClick={() => postAction(u.id, 'credits', { amount: 500, mode: 'add' })} style={greenBtn}>+500</button>
                      <button onClick={() => postAction(u.id, 'credits', { amount: 100, mode: 'deduct' })} style={redBtn}>-100</button>
                      <button onClick={() => postAction(u.id, 'credits', { amount: 500, mode: 'deduct' })} style={redBtn}>-500</button>
                    </div>

                    <div>
                      <button onClick={() => postAction(u.id, 'reset-usage', {})} style={darkBtn}>Reset Usage</button>
                      <button onClick={() => postAction(u.id, 'superadmin', { is_superadmin: !u.is_superadmin })} style={blueBtn}>
                        {u.is_superadmin ? 'Remove Admin' : 'Make Admin'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
