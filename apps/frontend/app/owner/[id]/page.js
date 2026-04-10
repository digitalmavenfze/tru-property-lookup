"use client";
import { useEffect, useState } from "react";

const API_BASE = "http://72.61.117.207:8050";

export default function OwnerPage({ params }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem("token");

    fetch(`${API_BASE}/owners/${params.id}`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData({ detail: "Failed to load owner" }));
  }, [params.id]);

  if (!data) return <div style={{ padding: 20 }}>Loading...</div>;
  if (data.detail) return <div style={{ padding: 20 }}>{data.detail}</div>;

  return (
    <div style={{ maxWidth: 900, margin: "40px auto", background: "#fff", padding: 32, borderRadius: 16, fontFamily: "Arial, sans-serif" }}>
      <button onClick={() => (window.location.href = "/")} style={{ marginBottom: 20 }}>← Back</button>
      <h2 style={{ marginTop: 0 }}>{data.owner.full_name}</h2>
      <p>📞 {data.owner.phone || "-"}</p>
      <p>✉️ {data.owner.email || "-"}</p>

      <h3>Properties</h3>

      {data.properties.map((p) => (
        <div
          key={p.link_id}
          style={{ border: "1px solid #ddd", padding: 12, marginBottom: 12, borderRadius: 12 }}
        >
          <div><b>Unit:</b> {p.unit_number || "-"}</div>
          <div><b>Community:</b> {p.community || "-"}</div>
          <div><b>Master Community:</b> {p.master_community || "-"}</div>
          <div><b>Type:</b> {p.property_type || "-"}</div>
        </div>
      ))}
    </div>
  );
}
