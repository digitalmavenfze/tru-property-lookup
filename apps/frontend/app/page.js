"use client";

import { useEffect, useState } from "react";

export default function HomePage() {
  const [email, setEmail] = useState("admin@truproplookup.trucrm.io");
  const [password, setPassword] = useState("ChangeMe123!");
  const [loading, setLoading] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);
  const [user, setUser] = useState(null);
  const [error, setError] = useState("");

  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [profileResult, setProfileResult] = useState(null);
  const [importResult, setImportResult] = useState(null);

  const [community, setCommunity] = useState("");
  const [project, setProject] = useState("");
  const [bedrooms, setBedrooms] = useState("");
  const [unitNumber, setUnitNumber] = useState("");
  const [ownerName, setOwnerName] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchResult, setSearchResult] = useState(null);

  async function loadCurrentUser(token) {
    try {
      const res = await fetch("/api/me", {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      const data = await res.json();

      if (!res.ok) {
        localStorage.removeItem("session_token");
        setUser(null);
        return;
      }

      setUser(data.user);
    } catch {
      setUser(null);
    } finally {
      setCheckingSession(false);
    }
  }

  useEffect(() => {
    const token = localStorage.getItem("session_token");
    if (!token) {
      setCheckingSession(false);
      return;
    }
    loadCurrentUser(token);
  }, []);

  async function handleLogin(e) {
    e.preventDefault();
    setLoading(true);
    setError("");

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

      localStorage.setItem("session_token", data.session_token);
      setUser(data.user);
    } catch (err) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  async function handleProfile(e) {
    e.preventDefault();
    setError("");
    setProfileResult(null);
    setImportResult(null);

    if (!selectedFile) {
      setError("Please select a file first");
      return;
    }

    const token = localStorage.getItem("session_token");
    if (!token) {
      setError("Session missing. Please login again.");
      return;
    }

    setUploading(true);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const res = await fetch("/api/profile-upload", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`
        },
        body: formData
      });

      const text = await res.text();
      let data;

      try {
        data = JSON.parse(text);
      } catch {
        throw new Error("Profile endpoint did not return JSON");
      }

      if (!res.ok) {
        throw new Error(data.detail || "Profiling failed");
      }

      setProfileResult(data);
    } catch (err) {
      setError(err.message || "Profiling failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleImport() {
    setError("");
    setImportResult(null);

    if (!selectedFile) {
      setError("Please select a file first");
      return;
    }

    const token = localStorage.getItem("session_token");
    if (!token) {
      setError("Session missing. Please login again.");
      return;
    }

    setUploading(true);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const res = await fetch("/api/import-upload", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`
        },
        body: formData
      });

      const text = await res.text();
      let data;

      try {
        data = JSON.parse(text);
      } catch {
        throw new Error("Import endpoint did not return JSON");
      }

      if (!res.ok) {
        throw new Error(data.detail || "Import failed");
      }

      setImportResult(data);
    } catch (err) {
      setError(err.message || "Import failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleSearch(e) {
    e.preventDefault();
    setError("");
    setSearchResult(null);

    const token = localStorage.getItem("session_token");
    if (!token) {
      setError("Session missing. Please login again.");
      return;
    }

    setSearching(true);

    try {
      const params = new URLSearchParams();

      if (community) params.append("community", community);
      if (project) params.append("project", project);
      if (bedrooms) params.append("bedrooms", bedrooms);
      if (unitNumber) params.append("unit_number", unitNumber);
      if (ownerName) params.append("owner_name", ownerName);

      const res = await fetch(`/api/search?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      const text = await res.text();
      let data;

      try {
        data = JSON.parse(text);
      } catch {
        throw new Error("Search endpoint did not return JSON");
      }

      if (!res.ok) {
        throw new Error(data.detail || "Search failed");
      }

      setSearchResult(data);
    } catch (err) {
      setError(err.message || "Search failed");
    } finally {
      setSearching(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem("session_token");
    setUser(null);
    setSelectedFile(null);
    setProfileResult(null);
    setImportResult(null);
    setSearchResult(null);
    setError("");
  }

  if (checkingSession) {
    return (
      <main style={{ maxWidth: 700, margin: "60px auto", background: "#fff", padding: 32, borderRadius: 16, boxShadow: "0 10px 30px rgba(0,0,0,0.08)", fontFamily: "Arial, sans-serif" }}>
        <h1 style={{ marginTop: 0 }}>Tru Property Lookup</h1>
        <p>Checking session...</p>
      </main>
    );
  }

  if (!user) {
    return (
      <main style={{ maxWidth: 520, margin: "60px auto", background: "#fff", padding: 32, borderRadius: 16, boxShadow: "0 10px 30px rgba(0,0,0,0.08)", fontFamily: "Arial, sans-serif" }}>
        <h1 style={{ marginTop: 0 }}>Tru Property Lookup</h1>
        <p>Login to access the property search platform.</p>

        <form onSubmit={handleLogin} style={{ display: "grid", gap: 16, marginTop: 24 }}>
          <div>
            <label style={{ display: "block", marginBottom: 8, fontWeight: 600 }}>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{ width: "100%", padding: 12, borderRadius: 10, border: "1px solid #d1d5db", boxSizing: "border-box" }}
            />
          </div>

          <div>
            <label style={{ display: "block", marginBottom: 8, fontWeight: 600 }}>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{ width: "100%", padding: 12, borderRadius: 10, border: "1px solid #d1d5db", boxSizing: "border-box" }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{ padding: 12, borderRadius: 10, border: "none", cursor: "pointer", fontWeight: 700 }}
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>

        {error ? (
          <div style={{ marginTop: 20, padding: 12, borderRadius: 10, background: "#fee2e2", color: "#991b1b" }}>
            {error}
          </div>
        ) : null}
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 1100, margin: "40px auto", background: "#fff", padding: 32, borderRadius: 16, boxShadow: "0 10px 30px rgba(0,0,0,0.08)", fontFamily: "Arial, sans-serif" }}>
      <h1 style={{ marginTop: 0 }}>Tru Property Lookup</h1>
      <p>Upload developer sheets, import them, and search owners and property records.</p>

      <div style={{ marginTop: 20, padding: 16, borderRadius: 12, background: "#ecfdf5" }}>
        <div><strong>Name:</strong> {user.full_name}</div>
        <div><strong>Email:</strong> {user.email}</div>
        <div><strong>Role:</strong> {user.role}</div>
        <div><strong>Tenant:</strong> {user.tenant}</div>
      </div>

      <div style={{ marginTop: 24, padding: 20, borderRadius: 12, background: "#f9fafb" }}>
        <h2 style={{ marginTop: 0 }}>1. Profile or import Type A / Type B file</h2>

        <input
          type="file"
          onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
        />

        <div style={{ display: "flex", gap: 12, marginTop: 16, flexWrap: "wrap" }}>
          <button
            onClick={handleProfile}
            disabled={uploading}
            style={{ padding: 12, borderRadius: 10, border: "none", cursor: "pointer", fontWeight: 700 }}
          >
            {uploading ? "Working..." : "Profile File"}
          </button>

          <button
            onClick={handleImport}
            disabled={uploading}
            style={{ padding: 12, borderRadius: 10, border: "none", cursor: "pointer", fontWeight: 700 }}
          >
            {uploading ? "Working..." : "Import File"}
          </button>
        </div>
      </div>

      {profileResult ? (
        <div style={{ marginTop: 20, padding: 16, borderRadius: 10, background: "#eff6ff", color: "#1e3a8a" }}>
          <div><strong>File Profile</strong></div>
          <div style={{ marginTop: 8 }}>Source type: {profileResult.source_type}</div>
          <div>File type: {profileResult.file_type}</div>
          <div>Sheets: {profileResult.sheet_count}</div>

          {profileResult.sheets?.map((sheet, idx) => (
            <div key={idx} style={{ marginTop: 16, padding: 12, background: "#fff", borderRadius: 8 }}>
              <div><strong>{sheet.sheet_name}</strong></div>
              <div>Rows: {sheet.row_count}</div>
              <div>Columns: {sheet.column_count}</div>
              <div style={{ marginTop: 8 }}><strong>Detected columns:</strong></div>
              <pre style={{ whiteSpace: "pre-wrap", overflowX: "auto" }}>
{JSON.stringify(sheet.column_types, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      ) : null}

      {importResult ? (
        <div style={{ marginTop: 20, padding: 16, borderRadius: 10, background: "#ecfeff", color: "#155e75" }}>
          <div><strong>Import Completed</strong></div>
          <div style={{ marginTop: 8 }}>Filename: {importResult.filename}</div>
          <div>Source type: {importResult.source_type}</div>
          <div>File type: {importResult.file_type}</div>
          <div>Sheets: {importResult.sheet_count}</div>
          <div>Records imported: {importResult.records_imported}</div>
          <div>Uploaded by: {importResult.uploaded_by}</div>
        </div>
      ) : null}

      <div style={{ marginTop: 24, padding: 20, borderRadius: 12, background: "#f9fafb" }}>
        <h2 style={{ marginTop: 0 }}>2. Search owners and properties</h2>

        <form onSubmit={handleSearch} style={{ display: "grid", gap: 16 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
            <input
              placeholder="Community / Dubai Hills Estate"
              value={community}
              onChange={(e) => setCommunity(e.target.value)}
              style={{ width: "100%", padding: 12, borderRadius: 10, border: "1px solid #d1d5db", boxSizing: "border-box" }}
            />
            <input
              placeholder="Project / Maple"
              value={project}
              onChange={(e) => setProject(e.target.value)}
              style={{ width: "100%", padding: 12, borderRadius: 10, border: "1px solid #d1d5db", boxSizing: "border-box" }}
            />
            <input
              placeholder="Bedrooms / 4"
              value={bedrooms}
              onChange={(e) => setBedrooms(e.target.value)}
              style={{ width: "100%", padding: 12, borderRadius: 10, border: "1px solid #d1d5db", boxSizing: "border-box" }}
            />
            <input
              placeholder="Unit number"
              value={unitNumber}
              onChange={(e) => setUnitNumber(e.target.value)}
              style={{ width: "100%", padding: 12, borderRadius: 10, border: "1px solid #d1d5db", boxSizing: "border-box" }}
            />
            <input
              placeholder="Owner name"
              value={ownerName}
              onChange={(e) => setOwnerName(e.target.value)}
              style={{ width: "100%", padding: 12, borderRadius: 10, border: "1px solid #d1d5db", boxSizing: "border-box" }}
            />
          </div>

          <button
            type="submit"
            disabled={searching}
            style={{ padding: 12, borderRadius: 10, border: "none", cursor: "pointer", fontWeight: 700, width: 180 }}
          >
            {searching ? "Searching..." : "Search"}
          </button>
        </form>
      </div>

      {searchResult ? (
        <div style={{ marginTop: 20, padding: 16, borderRadius: 10, background: "#f8fafc" }}>
          <div><strong>Search Results:</strong> {searchResult.count}</div>

          {searchResult.results?.map((item, idx) => (
            <div key={idx} style={{ marginTop: 16, padding: 16, borderRadius: 10, background: "#fff", border: "1px solid #e5e7eb" }}>
              <div><strong>Owner:</strong> {item.owner_name || "-"}</div>
              <div><strong>Owner Arabic:</strong> {item.owner_name_ar || "-"}</div>
              <div><strong>Email:</strong> {item.email || "-"}</div>
              <div><strong>Phone:</strong> {item.phone || "-"}</div>
              <div><strong>District:</strong> {item.district || "-"}</div>
              <div><strong>Master Community:</strong> {item.master_community || "-"}</div>
              <div><strong>Project:</strong> {item.project_name || "-"}</div>
              <div><strong>Sub Community:</strong> {item.sub_community || "-"}</div>
              <div><strong>Property Type:</strong> {item.property_type || "-"}</div>
              <div><strong>Bedrooms:</strong> {item.bedroom_count || "-"}</div>
              <div><strong>Unit Number:</strong> {item.unit_number || "-"}</div>
              <div><strong>Building:</strong> {item.building_name || "-"}</div>
              <div><strong>Plot Number:</strong> {item.plot_number || "-"}</div>
              <div><strong>Developer:</strong> {item.developer_name || "-"}</div>
              <div><strong>Source Sheet:</strong> {item.source_sheet || "-"}</div>
            </div>
          ))}
        </div>
      ) : null}

      {error ? (
        <div style={{ marginTop: 20, padding: 12, borderRadius: 10, background: "#fee2e2", color: "#991b1b" }}>
          {error}
        </div>
      ) : null}

      <button
        onClick={handleLogout}
        style={{
          marginTop: 24,
          padding: 12,
          borderRadius: 10,
          border: "none",
          cursor: "pointer",
          fontWeight: 700
        }}
      >
        Logout
      </button>
    </main>
  );
}
