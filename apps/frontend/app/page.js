"use client";
import { useEffect, useState } from "react";

const API_BASE = "http://72.61.117.207:8050";

export default function Home() {
  const [checking, setChecking] = useState(true);
  const [email, setEmail] = useState("admin@truproplookup.trucrm.io");
  const [password, setPassword] = useState("Admin@123456");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      setChecking(false);
      return;
    }
    setChecking(false);
  }, []);

  const login = async () => {
    setError("");
    const res = await fetch(`${API_BASE}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setError(data.detail || "Login failed");
      return;
    }

    localStorage.setItem("token", data.session_token);
    setChecking(false);
  };

  const searchAI = async () => {
    setError("");
    const token = localStorage.getItem("token");
    if (!token) {
      setError("Please login first");
      return;
    }

    const res = await fetch(`${API_BASE}/search-ai?q=${encodeURIComponent(query)}`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setError(data.detail || "Search failed");
      return;
    }

    setResults(data.results || []);
  };

  if (checking) {
    return <main style={{ maxWidth: 700, margin: "60px auto", background: "#fff", padding: 32, borderRadius: 16 }}>Checking session...</main>;
  }

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  if (!token) {
    return (
      <main style={{ maxWidth: 700, margin: "60px auto", background: "#fff", padding: 32, borderRadius: 16, fontFamily: "Arial, sans-serif" }}>
        <h1>Tru Property Lookup</h1>
        <h2>Login</h2>
        <input
          style={{ width: "100%", padding: 10, marginBottom: 10 }}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
        />
        <input
          style={{ width: "100%", padding: 10, marginBottom: 10 }}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          type="password"
        />
        <button onClick={login} style={{ padding: "10px 16px" }}>Login</button>
        {error ? <p style={{ color: "red" }}>{error}</p> : null}
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 900, margin: "40px auto", background: "#fff", padding: 32, borderRadius: 16, fontFamily: "Arial, sans-serif" }}>
      <h1 style={{ marginTop: 0 }}>AI Property Search</h1>

      <div style={{ display: "flex", gap: 10 }}>
        <input
          style={{ flex: 1, padding: 12 }}
          placeholder="Find villas owned by Lara in Palma..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button onClick={searchAI} style={{ padding: "12px 18px" }}>Search</button>
      </div>

      {error ? <p style={{ color: "red" }}>{error}</p> : null}

      <div style={{ marginTop: 20 }}>
        {results.map((r) => (
          <div
            key={r.link_id || r.id}
            style={{
              border: "1px solid #ddd",
              padding: 14,
              marginBottom: 12,
              borderRadius: 12,
              cursor: "pointer",
            }}
            onClick={() => {
              const id = r.owner_id || r.id;
              window.location.href = `/owner/${id}`;
            }}
          >
            <div style={{ fontWeight: 700 }}>{r.owner_name}</div>
            <div>📞 {r.phone || "-"}</div>
            <div>🏠 {r.unit_number || "-"} — {r.project_name || "-"}</div>
            <div>{r.property_type || "-"}</div>
          </div>
        ))}
      </div>
    </main>
  );
}
