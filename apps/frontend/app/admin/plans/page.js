"use client";
import { useEffect, useState } from "react";

const API_BASE = "http://72.61.117.207:8050";

export default function AdminPlansPage() {
  const [plans, setPlans] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      window.location.href = "/";
      return;
    }

    fetch(`${API_BASE}/admin/plans`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    })
      .then(async (r) => {
        const text = await r.text();
        const data = JSON.parse(text);
        if (!r.ok) throw new Error(data.detail || "Failed to load plans");
        return data;
      })
      .then((data) => setPlans(data.plans || []))
      .catch((err) => setError(err.message || "Failed to load plans"));
  }, []);

  if (error) {
    return <div style={{ maxWidth: 1000, margin: "40px auto", padding: 24, fontFamily: "Arial, sans-serif" }}>{error}</div>;
  }

  return (
    <main style={{ maxWidth: 1000, margin: "32px auto", fontFamily: "Arial, sans-serif" }}>
      <div style={{ background: "#fff", borderRadius: 18, padding: 24, boxShadow: "0 10px 30px rgba(0,0,0,0.08)" }}>
        <button onClick={() => (window.location.href = "/")} style={{ padding: "10px 16px", borderRadius: 10, border: "1px solid #ddd", background: "#fff", cursor: "pointer", marginBottom: 20 }}>
          ← Back
        </button>
        <h1 style={{ marginTop: 0 }}>Admin Plans</h1>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0,1fr))", gap: 16 }}>
          {plans.map((plan) => (
            <div key={plan.code} style={{ border: "1px solid #e5e7eb", borderRadius: 16, padding: 18 }}>
              <div style={{ fontSize: 24, fontWeight: 700 }}>{plan.name}</div>
              <div style={{ color: "#666", marginTop: 6 }}>{plan.code}</div>
              <div style={{ marginTop: 14 }}>Price: <b>${plan.price_usd}</b></div>
              <div>Monthly Credits: <b>{plan.monthly_credits}</b></div>
              <div>Monthly Search Limit: <b>{plan.monthly_search_limit}</b></div>
              <div>Status: <b>{plan.is_active ? "Active" : "Inactive"}</b></div>
              <pre style={{ background: "#f8fafc", padding: 12, borderRadius: 12, marginTop: 14, overflow: "auto", fontSize: 12 }}>
{JSON.stringify(plan.features || {}, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
