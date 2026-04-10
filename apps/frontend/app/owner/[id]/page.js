"use client";
import { useEffect, useState } from "react";

const API_BASE = "http://72.61.117.207:8050";

export default function OwnerPage({ params }) {
  const [data, setData] = useState(null);
  const [billing, setBilling] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      window.location.href = "/";
      return;
    }

    async function load() {
      try {
        const [ownerRes, billingRes] = await Promise.all([
          fetch(`${API_BASE}/owners/${params.id}`, {
            headers: { Authorization: `Bearer ${token}` },
            cache: "no-store",
          }),
          fetch(`${API_BASE}/billing/me`, {
            headers: { Authorization: `Bearer ${token}` },
            cache: "no-store",
          }),
        ]);

        const ownerText = await ownerRes.text();
        const billingText = await billingRes.text();

        const ownerData = JSON.parse(ownerText);
        const billingData = JSON.parse(billingText);

        if (!ownerRes.ok) throw new Error(ownerData.detail || "Failed to load owner");
        if (!billingRes.ok) throw new Error(billingData.detail || "Failed to load billing");

        setData(ownerData);
        setBilling(billingData);
      } catch (err) {
        setError(err.message || "Failed to load owner");
      }
    }

    load();
  }, [params.id]);

  if (error) {
    return <div style={{ maxWidth: 900, margin: "40px auto", padding: 24, fontFamily: "Arial, sans-serif" }}>{error}</div>;
  }

  if (!data) {
    return <div style={{ maxWidth: 900, margin: "40px auto", padding: 24, fontFamily: "Arial, sans-serif" }}>Loading...</div>;
  }

  return (
    <main style={{ maxWidth: 980, margin: "32px auto", fontFamily: "Arial, sans-serif" }}>
      <div style={{ background: "#fff", borderRadius: 18, padding: 24, boxShadow: "0 10px 30px rgba(0,0,0,0.08)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <button onClick={() => (window.location.href = "/")} style={{ padding: "10px 16px", borderRadius: 10, border: "1px solid #ddd", background: "#fff", cursor: "pointer" }}>
            ← Back
          </button>
          <div style={{ fontSize: 14, color: "#555" }}>
            Credits: <b>{billing?.credits_balance ?? "-"}</b>
          </div>
        </div>

        <h1 style={{ marginTop: 20, marginBottom: 8 }}>{data.owner.full_name}</h1>
        <div style={{ color: "#555", marginBottom: 20 }}>
          {data.owner.email || "No email"} · {data.owner.phone || "No phone"}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0,1fr))", gap: 12, marginBottom: 20 }}>
          <div style={{ background: "#f8fafc", padding: 16, borderRadius: 14 }}>
            <div style={{ fontSize: 12, color: "#666" }}>Properties</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{data.properties_count}</div>
          </div>
          <div style={{ background: "#f8fafc", padding: 16, borderRadius: 14 }}>
            <div style={{ fontSize: 12, color: "#666" }}>Credits Used</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{data.credits_used ?? 0}</div>
          </div>
          <div style={{ background: "#f8fafc", padding: 16, borderRadius: 14 }}>
            <div style={{ fontSize: 12, color: "#666" }}>Credits Left</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{data.credits_balance ?? billing?.credits_balance ?? 0}</div>
          </div>
          <div style={{ background: "#f8fafc", padding: 16, borderRadius: 14 }}>
            <div style={{ fontSize: 12, color: "#666" }}>Plan</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{billing?.plan_name || "-"}</div>
          </div>
        </div>

        <h2>Properties</h2>
        {data.properties.map((p) => (
          <div key={p.link_id} style={{ border: "1px solid #e5e7eb", borderRadius: 14, padding: 16, marginBottom: 12 }}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>{p.community || "-"}</div>
            <div>Unit: {p.unit_number || "-"}</div>
            <div>Master Community: {p.master_community || "-"}</div>
            <div>Type: {p.property_type || "-"}</div>
            <div>Plot: {p.plot_number || "-"}</div>
            <div>Developer: {p.developer_name || "-"}</div>
          </div>
        ))}

        <h2 style={{ marginTop: 28 }}>Raw Owner Data</h2>
        <pre style={{ background: "#0f172a", color: "#e2e8f0", padding: 16, borderRadius: 14, overflow: "auto", fontSize: 12 }}>
{JSON.stringify(data.owner.raw_data || {}, null, 2)}
        </pre>
      </div>
    </main>
  );
}
