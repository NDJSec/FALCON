import { useState } from "react";
import { useRouter } from "next/router";

export default function RegisterPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const handleRegister = async () => {
    setError("");
    setSuccess("");
    try {
      const res = await fetch(`${API_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, email, password }),
      });

      if (!res.ok) {
        if (res.status === 422) {
          setError("Invalid registration data. Check your input.");
        } else {
          setError(`Registration failed: ${res.statusText}`);
        }
        return;
      }

      setSuccess("Registration successful! Redirecting to login...");
      setTimeout(() => router.push("/login"), 1500);
    } catch (err) {
      setError("Network error. Please try again.");
    }
  };

  return (
    <div className="chat-layout sidebar-closed">
      <main className="chat-main" style={{ justifyContent: "center", alignItems: "center", display: "flex" }}>
        <div style={{ width: "400px", padding: "2rem", backgroundColor: "var(--bg-secondary)", borderRadius: "8px" }}>
          <h2 style={{ color: "var(--text-bright)", marginBottom: "1rem" }}>Register</h2>

          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          {error && <p style={{ color: "var(--accent-negative)", marginBottom: "0.5rem" }}>{error}</p>}
          {success && <p style={{ color: "var(--accent-positive)", marginBottom: "0.5rem" }}>{success}</p>}

          <button className="new-chat-btn" onClick={handleRegister}>Register</button>

          <p style={{ color: "var(--text-secondary)", marginTop: "1rem" }}>
            Already have an account? <a href="/login" style={{ color: "var(--text-link)" }}>Login</a>
          </p>
        </div>
      </main>
    </div>
  );
}
