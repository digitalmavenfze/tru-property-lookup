"use client";

import { useState } from "react";

export default function HomePage() {
  const [email, setEmail] = useState("admin@truproplookup.trucrm.io");
  const [password, setPassword] = useState("ChangeMe123!");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function handleLogin(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ email, password })
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Login failed");
      }

      setResult(data);
    } catch (err) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main
      style={{
        maxWidth: 520,
        margin: "60px auto",
        background: "#fff",
        padding: 32,
        borderRadius: 16,
        boxShadow: "0 10px 30px rgba(0,0,0,0.08)",
        fontFamily: "Arial, sans-serif"
      }}
    >
      <h1 style={{ marginTop: 0 }}>Tru Property Lookup</h1>
      <p>Login to access the property search platform.</p>

      <form onSubmit={handleLogin} style={{ display: "grid", gap: 16, marginTop: 24 }}>
        <div>
          <label style={{ display: "block", marginBottom: 8, fontWeight: 600 }}>Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{
              width: "100%",
              padding: 12,
              borderRadius: 10,
              border: "1px solid #d1d5db",
              boxSizing: "border-box"
            }}
          />
        </div>

        <div>
          <label style={{ display: "block", marginBottom: 8, fontWeight: 600 }}>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{
              width: "100%",
              padding: 12,
              borderRadius: 10,
              border: "1px solid #d1d5db",
              boxSizing: "border-box"
            }}
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          style={{
            padding: 12,
            borderRadius: 10,
            border: "none",
            cursor: "pointer",
            fontWeight: 700
          }}
        >
          {loading ? "Signing in..." : "Sign In"}
        </button>
      </form>

      {error ? (
        <div
          style={{
            marginTop: 20,
            padding: 12,
            borderRadius: 10,
            background: "#fee2e2",
            color: "#991b1b"
          }}
        >
          {error}
        </div>
      ) : null}

      {result ? (
        <div
          style={{
            marginTop: 20,
            padding: 16,
            borderRadius: 10,
            background: "#ecfdf5",
            color: "#065f46"
          }}
        >
          <div><strong>{result.message}</strong></div>
          <div style={{ marginTop: 8 }}>Name: {result.user.full_name}</div>
          <div>Email: {result.user.email}</div>
          <div>Role: {result.user.role}</div>
          <div>Tenant: {result.user.tenant}</div>
        </div>
      ) : null}
    </main>
  );
}
