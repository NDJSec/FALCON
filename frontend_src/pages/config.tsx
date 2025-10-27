import { useContext } from "react";
import { useRouter } from "next/router";
import { ServersContext } from "../shared/ServersContext";

export default function ConfigPage() {
  const router = useRouter();
  const { servers, setServers } = useContext(ServersContext);

  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const handleToggle = async (server: string) => {
    const newState = { ...servers, [server]: !servers[server] };
    setServers(newState);

    const activeServers = Object.entries(newState)
      .filter(([_, enabled]) => enabled)
      .map(([name]) => name);

    try {
      const res = await fetch(`${API_URL}/servers/toggle`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
             ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ active_servers: activeServers }),
      });
      if (!res.ok) throw new Error(`Failed to toggle servers: ${res.status}`);
    } catch (err) {
      console.error("Error toggling servers:", err);
    }
  };

  return (
    <div className="chat-layout">
      <aside className="sidebar">
        <div className="sidebar-content">
          <button onClick={() => router.push("/")} className="new-chat-btn">
            💬 Back to Chat
          </button>

          <div style={{ height: "10px" }} />

          <div className="tools-box">
            <h3>MCP Servers</h3>
            {Object.keys(servers).length === 0 && (
              <p style={{ fontSize: "0.9rem", color: "#666" }}>No servers available.</p>
            )}
            {Object.entries(servers).map(([server, enabled]) => (
              <div key={server} className="tool-toggle">
                <label style={{ flex: 1, textTransform: "capitalize" }}>{server}</label>
                <label className="switch">
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={() => handleToggle(server)}
                  />
                  <span className="slider"></span>
                </label>
              </div>
            ))}
          </div>
        </div>
      </aside>

      <main className="chat-main">
        <div className="chat-header">Configuration</div>
        <div className="messages">
          <div className="bubble">
            <p>Use the toggles in the sidebar to enable or disable MCP servers.</p>
          </div>
          <div className="bubble">
            <p>
              Current server states:
              <br />
              <code>{JSON.stringify(servers, null, 2)}</code>
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
