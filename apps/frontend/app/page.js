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
  const [uploadResult, setUploadResult] = useState(null);
  const [profileResult, setProfileResult] = useState(null);

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

  async function handleUpload(e) {
    e.preventDefault();
    setUploadResult(null);
    setProfileResult(null);
    setError("");

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
      const uploadFormData = new FormData();
      uploadFormData.append("file", selectedFile);

      const uploadRes = await fetch("/api/upload", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`
        },
        body: uploadFormData
      });

      const uploadData = await uploadRes.json();

      if (!uploadRes.ok) {
        throw new Error(uploadData.detail || "Upload failed");
      }

      setUploadResult(uploadData);

      const profileFormData = new FormData();
      profileFormData.append("file", selectedFile);

      const profileRes = await fetch("/api/profile-upload", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`
        },
        body: profileFormData
      });

      const profileData = await profileRes.json();

      if (!profileRes.ok) {
        throw new Error(profileData.detail || "Profiling failed");
      }

      setProfileResult(profileData);
    } catch (err) {
      setError(err.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem("session_token");
    setUser(null);
    setSelectedFile(null);
    setUploadResult(null);
    setProfileResult(null);
    setError("");
  }

  if (checkingSession) {
    return (
      <main style={{ maxWidth: 520, margin: "60px auto", background: "#fff", padding: 32, borderRadius: 16, boxShadow: "0 10px 30px rgba(0,0,0,0.08)", fontFamily: "Arial, sans-serif" }}>
        <h1 style={{ marginTop: 0 }}>Tru Property Lookup</h1>
        <p>Checking session...</p>
      </main>
    );
  }

  if (user) {
    return (
      <main style={{ maxWidth: 980, margin: "60px auto", background: "#fff", padding: 32, borderRadius: 16, boxShadow: "0 10px 30px rgba(0,0,0,0.08)", fontFamily: "Arial, sans-serif" }}>
        <h1 style={{ marginTop: 0 }}>Tru Property Lookup</h1>
        <p>Welcome to the dashboard.</p>

        <div style={{ marginTop: 24, padding: 16, borderRadius: 12, background: "#ecfdf5" }}>
          <div><strong>Name:</strong> {user.full_name}</div>
          <div><strong>Email:</strong> {user.email}</div>
          <div><strong>Role:</strong> {user.role}</div>
          <div><strong>Tenant:</strong> {user.tenant}</div>
        </div>

        <div style={{ marginTop: 24, padding: 16, borderRadius: 12, background: "#f3f4f6" }}>
          <strong>Next modules:</strong>
          <div style={{ marginTop: 8 }}>1. Excel upload</div>
          <div>2. File profiling</div>
          <div>3. Header detection</div>
          <div>4. Search screen</div>
        </div>

        <form onSubmit={handleUpload} style={{ marginTop: 24, padding: 16, borderRadius: 12, background: "#f9fafb", display: "grid", gap: 16 }}>
          <div>
            <strong>Upload Excel file</strong>
          </div>

          <input
            type="file"
            onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
          />

          <button
            type="submit"
            disabled={uploading}
            style={{
              padding: 12,
              borderRadius: 10,
              border: "none",
              cursor: "pointer",
              fontWeight: 700
            }}
          >
            {uploading ? "Uploading and profiling..." : "Upload File"}
          </button>
        </form>

        {uploadResult ? (
          <div style={{ marginTop: 20, padding: 16, borderRadius: 10, background: "#eff6ff", color: "#1e3a8a" }}>
            <div><strong>{uploadResult.message}</strong></div>
            <div style={{ marginTop: 8 }}>Filename: {uploadResult.filename}</div>
            <div>Size: {uploadResult.size_bytes} bytes</div>
            <div>Uploaded by: {uploadResult.uploaded_by}</div>
          </div>
        ) : null}

        {profileResult ? (
          <div style={{ marginTop: 20, padding: 16, borderRadius: 10, background: "#f8fafc" }}>
            <h2 style={{ marginTop: 0 }}>File Profile</h2>

            <div><strong>File type:</strong> {profileResult.file_type}</div>
            <div><strong>Rows:</strong> {profileResult.row_count}</div>
            <div><strong>Columns:</strong> {profileResult.column_count}</div>

            <div style={{ marginTop: 16 }}>
              <strong>Detected columns</strong>
              <table style={{ width: "100%", marginTop: 10, borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", padding: 10, borderBottom: "1px solid #d1d5db" }}>Column</th>
                    <th style={{ textAlign: "left", padding: 10, borderBottom: "1px solid #d1d5db" }}>Detected type</th>
                  </tr>
                </thead>
                <tbody>
                  {profileResult.columns.map((col) => (
                    <tr key={col}>
                      <td style={{ padding: 10, borderBottom: "1px solid #e5e7eb" }}>{col}</td>
                      <td style={{ padding: 10, borderBottom: "1px solid #e5e7eb" }}>
                        {profileResult.column_types?.[col] || "unknown"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{ marginTop: 20 }}>
              <strong>Preview</strong>
              <div style={{ overflowX: "auto", marginTop: 10 }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      {profileResult.columns.map((col) => (
                        <th
                          key={col}
                          style={{
                            textAlign: "left",
                            padding: 10,
                            borderBottom: "1px solid #d1d5db",
                            background: "#f1f5f9"
                          }}
                        >
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {profileResult.preview.map((row, idx) => (
                      <tr key={idx}>
                        {profileResult.columns.map((col) => (
                          <td
                            key={col}
                            style={{
                              padding: 10,
                              borderBottom: "1px solid #e5e7eb"
                            }}
                          >
                            {row[col] ?? ""}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
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
