"use client";
import { useEffect, useState } from "react";

const API_BASE = "http://72.61.117.207:8050";

export default function Home() {
  const [token, setToken] = useState("");
  const [me, setMe] = useState(null);
  const [billing, setBilling] = useState(null);
  const [usage, setUsage] = useState([]);
  const [email, setEmail] = useState("admin@truproplookup.trucrm.io");
  const [password, setPassword] = useState("Admin@123456");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("token") || "";
    setToken(saved);
  }, []);

  useEffect(() => {
    if (token) {
      loadDashboard(token);
    }
  }, [token]);

  async function apiGet(path, sessionToken) {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { Authorization: `Bearer ${sessionToken}` },
      cache: "no-store",
    });
    const text = await res.text();
    let data = {};
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(text || "Invalid response");
    }
    if (!res.ok) throw new Error(data.detail || "Request failed");
    return data;
  }

  async function loadDashboard(sessionToken) {
    try {
      setError("");
      const [meData, billingData, usageData] = await Promise.all([
        apiGet("/me", sessionToken),
        apiGet("/billing/me", sessionToken),
        apiGet("/billing/usage?limit=10", sessionToken).catch(() => ({ results: [] })),
      ]);
      setMe(meData);
      setBilling(billingData);
      setUsage(usageData.results || []);
    } catch (err) {
      setError(err.message || "Failed to load dashboard");
    }
  }

  async function login() {
    try {
      setLoading(true);
      setError("");
      const res = await fetch(`${API_BASE}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const text = await res.text();
      let data = {};
      try {
        data = JSON.parse(text);
      } catch {
        throw new Error(text || "Invalid login response");
      }
      if (!res.ok) throw new Error(data.detail || "Login failed");
      localStorage.setItem("token", data.session_token);
      setToken(data.session_token);
    } catch (err) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem("token");
    setToken("");
    setMe(null);
    setBilling(null);
    setUsage([]);
    setResults([]);
    setError("");
  }

  async function searchAI() {
    try {
      setLoading(true);
      setError("");
      const data = await apiGet(`/search-ai?q=${encodeURIComponent(query)}`, token);
      setResults(data.results || []);
      await loadDashboard(token);
    } catch (err) {
      setError(err.message || "Search failed");
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <main style={{ maxWidth: 520, margin: "60px auto", background: "#fff", padding: 32, borderRadius: 16, fontFamily: "Arial, sans-serif", boxShadow: "0 12px 32px rgba(0,0,0,0.08)" }}>
        <h1 style={{ marginTop: 0 }}>Tru Property Lookup</h1>
        <p>Login to access search, owner detail, and billing.</p>
        <input style={{ width: "100%", padding: 12, marginBottom: 12, border: "1px solid #ddd", borderRadius: 10 }} value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
        <input style={{ width: "100%", padding: 12, marginBottom: 12, border: "1px solid #ddd", borderRadius: 10 }} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" type="password" />
        <button onClick={login} disabled={loading} style={{ padding: "12px 18px", borderRadius: 10, border: 0, background: "#111827", color: "#fff", cursor: "pointer" }}>
          {loading ? "Logging in..." : "Login"}
        </button>
        {error ? <p style={{ color: "crimson", marginTop: 12 }}>{error}</p> : null}
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 1100, margin: "32px auto", fontFamily: "Arial, sans-serif" }}>
      <div style={{ background: "#fff", padding: 24, borderRadius: 18, boxShadow: "0 10px 30px rgba(0,0,0,0.08)", marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
          <div>
            <h1 style={{ margin: 0 }}>Tru Property Lookup</h1>
            <div style={{ marginTop: 8, color: "#555" }}>{me?.full_name} · {me?.email}</div>
          </div>
          <button onClick={logout} style={{ padding: "10px 16px", borderRadius: 10, border: "1px solid #ddd", background: "#fff", cursor: "pointer" }}>
            Logout
          </button>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0,1fr))", gap: 12, marginTop: 20 }}>
          <div style={{ background: "#f8fafc", padding: 16, borderRadius: 14 }}>
            <div style={{ fontSize: 12, color: "#666" }}>Plan</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{billing?.plan_name || me?.plan_name || "-"}</div>
          </div>
          <div style={{ background: "#f8fafc", padding: 16, borderRadius: 14 }}>
            <div style={{ fontSize: 12, color: "#666" }}>Credits</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{billing?.credits_balance ?? me?.credits_balance ?? 0}</div>
          </div>
          <div style={{ background: "#f8fafc", padding: 16, borderRadius: 14 }}>
            <div style={{ fontSize: 12, color: "#666" }}>Monthly Searches</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{billing?.monthly_search_count ?? me?.monthly_search_count ?? 0}</div>
          </div>
          <div style={{ background: "#f8fafc", padding: 16, borderRadius: 14 }}>
            <div style={{ fontSize: 12, color: "#666" }}>Monthly Limit</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{billing?.monthly_search_limit ?? me?.monthly_search_limit ?? 0}</div>
          </div>
        </div>
      </div>

      <div style={{ background: "#fff", padding: 24, borderRadius: 18, boxShadow: "0 10px 30px rgba(0,0,0,0.08)", marginBottom: 20 }}>
        <h2 style={{ marginTop: 0 }}>AI Search</h2>
        <div style={{ display: "flex", gap: 10 }}>
          <input
            style={{ flex: 1, padding: 14, border: "1px solid #ddd", borderRadius: 12 }}
            placeholder="find villas owned by Lara in Palma"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button onClick={searchAI} disabled={loading} style={{ padding: "14px 18px", borderRadius: 12, border: 0, background: "#111827", color: "#fff", cursor: "pointer" }}>
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
        {error ? <p style={{ color: "crimson", marginTop: 12 }}>{error}</p> : null}

        <div style={{ marginTop: 20 }}>
          {results.map((r) => (
            <div
              key={r.link_id || r.id}
              onClick={() => window.location.href = `/owner/${r.owner_id || r.id}`}
              style={{ border: "1px solid #e5e7eb", borderRadius: 14, padding: 14, marginBottom: 12, cursor: "pointer" }}
            >
              <div style={{ fontWeight: 700, marginBottom: 6 }}>{r.owner_name}</div>
              <div>Phone: {r.phone || "-"}</div>
              <div>Unit: {r.unit_number || "-"}</div>
              <div>Project: {r.project_name || "-"}</div>
              <div>Type: {r.property_type || "-"}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ background: "#fff", padding: 24, borderRadius: 18, boxShadow: "0 10px 30px rgba(0,0,0,0.08)" }}>
        <h2 style={{ marginTop: 0 }}>Recent Usage</h2>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid #e5e7eb" }}>
                <th style={{ padding: "10px 8px" }}>Endpoint</th>
                <th style={{ padding: "10px 8px" }}>Query</th>
                <th style={{ padding: "10px 8px" }}>Credits</th>
                <th style={{ padding: "10px 8px" }}>Results</th>
                <th style={{ padding: "10px 8px" }}>Area Tier</th>
                <th style={{ padding: "10px 8px" }}>Created</th>
              </tr>
            </thead>
            <tbody>
              {usage.map((u) => (
                <tr key={u.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                  <td style={{ padding: "10px 8px" }}>{u.endpoint}</td>
                  <td style={{ padding: "10px 8px" }}>{u.query_text || u.phone || u.owner_name || "-"}</td>
                  <td style={{ padding: "10px 8px" }}>{u.credits_used}</td>
                  <td style={{ padding: "10px 8px" }}>{u.result_count}</td>
                  <td style={{ padding: "10px 8px" }}>{u.area_tier}</td>
                  <td style={{ padding: "10px 8px" }}>{u.created_at ? new Date(u.created_at).toLocaleString() : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
