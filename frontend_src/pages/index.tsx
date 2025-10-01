import { useState, useEffect } from "react";

type Message = { id?: number; role: "user" | "assistant"; content: string; feedback?: number };
type Conversation = { id: string; started_at: string };
type Tool = { name: string; enabled: boolean };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export default function Home() {
  const [token, setToken] = useState("");
  const [tokenValid, setTokenValid] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [prompt, setPrompt] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [provider, setProvider] = useState("OpenAI");
  const [model, setModel] = useState("gpt-4o-mini");
  const [tools, setTools] = useState<Tool[]>([]);
  const [darkMode, setDarkMode] = useState(false);

  // Load dark mode preference
  useEffect(() => {
    const saved = localStorage.getItem("darkMode");
    if (saved) setDarkMode(saved === "true");
  }, []);

  // Apply dark mode to body
  useEffect(() => {
    if (darkMode) document.body.classList.add("dark");
    else document.body.classList.remove("dark");
    localStorage.setItem("darkMode", String(darkMode));
  }, [darkMode]);

  async function validateToken() {
    const res = await fetch(`${API_BASE}/conversations/${token}`);
    if (res.ok) {
      const convs: Conversation[] = await res.json();
      setTokenValid(true);
      setConversations(convs);
      if (convs.length > 0) {
        setConversationId(convs[convs.length - 1].id);
        loadMessages(convs[convs.length - 1].id);
      } else {
        setConversationId(null);
        setMessages([]);
      }
      const toolsRes = await fetch(`${API_BASE}/tools`);
      if (toolsRes.ok) setTools(await toolsRes.json());
    } else {
      setTokenValid(false);
      setMessages([]);
    }
  }

  async function loadMessages(convId: string) {
    const res = await fetch(`${API_BASE}/messages/${convId}`);
    if (res.ok) setMessages(await res.json());
  }

  async function sendMessage() {
    if (!token || !prompt) return;
    const selectedTools = tools.filter(t => t.enabled).map(t => t.name);

    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token,
        prompt,
        provider,
        model,
        api_key: "",
        use_mcp: true,
        conversation_id: conversationId,
        tools: selectedTools
      }),
    });
    if (res.ok) {
      const data = await res.json();
      setConversationId(data.conversation_id);
      setMessages(prev => [
        ...prev,
        { role: "user", content: prompt },
        { role: "assistant", content: data.answer }
      ]);
      setPrompt("");
    } else alert("Error: " + await res.text());
  }

  function toggleTool(index: number) {
    const newTools = [...tools];
    newTools[index].enabled = !newTools[index].enabled;
    setTools(newTools);
  }

  async function sendFeedback(messageId: number, value: number) {
    await fetch(`${API_BASE}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message_id: messageId, feedback: value }),
    });
    setMessages(prev => prev.map(m => m.id === messageId ? { ...m, feedback: value } : m));
  }

  async function newChat() {
    setConversationId(null);
    setMessages([]);
  }

  return (
    <div className="chat-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <h2>💬 FALCON</h2>
        <button className="dark-toggle" onClick={() => setDarkMode(!darkMode)}>
          {darkMode ? "🌞 Light Mode" : "🌙 Dark Mode"}
        </button>

        <div className="token-box">
          <label>Token:</label>
          <input value={token} onChange={e => setToken(e.target.value)} />
          {tokenValid ? <span className="valid">✅</span> :
                        token && <span className="invalid">❌</span>}
        </div>

        {tokenValid && (
          <>
            <div className="config-box">
              <label>Provider:</label>
              <select value={provider} onChange={e => setProvider(e.target.value)}>
                <option value="OpenAI">OpenAI</option>
                <option value="Gemini">Gemini</option>
              </select>
              <label>Model:</label>
              <select value={model} onChange={e => setModel(e.target.value)}>
                {provider === "OpenAI" ? (
                  <>
                    <option value="gpt-4o-mini">gpt-4o-mini</option>
                    <option value="gpt-4o">gpt-4o</option>
                  </>
                ) : (
                  <>
                    <option value="gemini-2.5-flash">gemini-2.5-flash</option>
                    <option value="gemini-2.5-pro">gemini-2.5-pro</option>
                    <option value="gemini-1.5-flash">gemini-1.5-flash</option>
                    <option value="gemini-1.5-pro">gemini-1.5-pro</option>
                  </>
                )}
              </select>
              <button onClick={newChat}>➕ New Chat</button>
            </div>

            <div className="tools-box">
              <h3>MCP Tools</h3>
              {tools.map((t, i) => (
                <label key={i}>
                  <input type="checkbox" checked={t.enabled} onChange={() => toggleTool(i)} /> {t.name}
                </label>
              ))}
            </div>
          </>
        )}
      </aside>

      {/* Chat area */}
      <main className="chat-main">
        <div className="messages">
          {messages.map((m, i) => (
            <div key={i} className={`message ${m.role}`}>
              <div className="bubble">
                {m.content}
                {m.role === "assistant" && m.id && (
                  <div className="feedback">
                    <button onClick={() => sendFeedback(m.id!, 1)} disabled={m.feedback === 1}>👍</button>
                    <button onClick={() => sendFeedback(m.id!, -1)} disabled={m.feedback === -1}>👎</button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {tokenValid && (
          <div className="input-bar">
            <textarea
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              placeholder="Ask me something..."
            />
            <button onClick={sendMessage}>Send</button>
          </div>
        )}
      </main>
    </div>
  );
}
