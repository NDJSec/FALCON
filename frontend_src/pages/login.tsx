import { useState } from "react";
import { useRouter } from "next/router";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState("");

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const handleLogin = async () => {
    setError("");
    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      if (!res.ok) {
        if (res.status === 422) {
          setError("Invalid credentials, please try again.");
        } else {
          setError(`Login failed: ${res.statusText}`);
        }
        return;
      }

      const data = await res.json();
      if (data.access_token) {
        localStorage.setItem("access_token", data.access_token);
        if (rememberMe) {
          localStorage.setItem("remember_me", "true");
        }
        router.push("/");
      }
    } catch (err) {
      setError("Network error. Please try again.");
    }
  };

  return (
    <div className="chat-layout sidebar-closed">
      <main className="chat-main" style={{ justifyContent: "center", alignItems: "center", display: "flex" }}>
        <div style={{ width: "400px", padding: "2rem", backgroundColor: "var(--bg-secondary)", borderRadius: "8px" }}>
          <h2 style={{ color: "var(--text-bright)", marginBottom: "1rem" }}>Login</h2>

          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <div style={{ display: "flex", alignItems: "center", margin: "0.5rem 0" }}>
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              id="rememberMe"
            />
            <label htmlFor="rememberMe" style={{ marginLeft: "0.5rem", fontSize: "0.9rem", color: "var(--text-primary)" }}>
              Remember Me
            </label>
          </div>

          {error && <p style={{ color: "var(--accent-negative)", marginBottom: "0.5rem" }}>{error}</p>}

          <button className="new-chat-btn" onClick={handleLogin}>Login</button>

          <p style={{ color: "var(--text-secondary)", marginTop: "1rem" }}>
            Don't have an account? <a href="/register" style={{ color: "var(--text-link)" }}>Register</a>
          </p>
        </div>
      </main>
    </div>
  );
}
