import { useState, useEffect, useRef, useContext } from "react";
import { ServersContext } from "../shared/ServersContext";
import {
  apiGetConversations,
  apiGetMessagesForConversation,
  apiNewConversation,
  apiGetTools,
  apiGetModels,
  apiSendMessage,
  apiSendFeedback,
} from "../utils/apiClient";
import { Message, Conversation, ModelProviders } from "../shared/types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useRouter } from "next/router";

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<{ username: string; email: string } | null>(null);
  const [isVerifying, setIsVerifying] = useState(true);
  const [tokenValid, setTokenValid] = useState(false);
  const [apiKey, setApiKey] = useState("");

  const [messages, setMessages] = useState<Message[]>([]);
  const [prompt, setPrompt] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);

  const [models, setModels] = useState<ModelProviders>({});
  const [provider, setProvider] = useState("OpenAI");
  const [model, setModel] = useState("gpt-4o-mini");

  const { servers } = useContext(ServersContext);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // --- Scroll to bottom when messages change ---
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // --- Load models and tools on first load ---
  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        const fetchedModels = await apiGetModels();
        setModels(fetchedModels);
        if (fetchedModels && Object.keys(fetchedModels).length > 0) {
          const firstProvider = Object.keys(fetchedModels)[0];
          setProvider(firstProvider);
          setModel(fetchedModels[firstProvider][0]);
        }

        await apiGetTools(); // backend handles active servers
      } catch (error) {
        console.error("Failed to fetch initial data:", error);
      }
    };
    fetchInitialData();
  }, []);

  // --- Verify JWT token and fetch user ---
  useEffect(() => {
    const verifyToken = async () => {
      let storedToken = localStorage.getItem("access_token");
      if (!storedToken) {
        setIsVerifying(false);
        router.push("/login");
        return;
      }

      try {
        const fetchUser = async (tokenToUse: string) => {
          const res = await fetch(`${API_URL}/auth/me`, {
            headers: { Authorization: `Bearer ${tokenToUse}` },
          });
          if (!res.ok) throw res;
          return res.json();
        };

        let data;
        try {
          data = await fetchUser(storedToken);
        } catch (err: any) {
          if (err.status === 401) {
            // Attempt token refresh
            const refreshRes = await fetch(`${API_URL}/auth/refresh`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ token: storedToken }),
            });

            if (!refreshRes.ok) throw new Error("Token refresh failed");
            const refreshData = await refreshRes.json();
            if (!refreshData.access_token) throw new Error("No new access token");

            localStorage.setItem("access_token", refreshData.access_token);
            storedToken = refreshData.access_token;

            // Retry fetching user
            data = await fetchUser(storedToken);
          } else {
            throw err;
          }
        }

        setToken(storedToken);
        setUser({ username: data.username, email: data.email });
        setTokenValid(true);

        // Load conversations
        const convos = await apiGetConversations(storedToken);
        setConversations(convos);
        if (convos.length > 0) handleConversationSelect(convos[0].id);
      } catch (err) {
        console.warn("Auth verification failed:", err);
        localStorage.removeItem("access_token");
        setToken(null);
        setUser(null);
        setTokenValid(false);
        router.push("/login");
      } finally {
        setIsVerifying(false);
      }
    };

    verifyToken();
  }, []);

  // --- Conversation Handlers ---
  const handleConversationSelect = async (id: string) => {
    setActiveConversationId(id);
    try {
      const history = await apiGetMessagesForConversation(id);
      setMessages(history);
    } catch (error) {
      console.error("Failed to load conversation history:", error);
      setMessages([{ role: "assistant", content: "Failed to load conversation history." }]);
    }
  };

  const handleNewChat = async () => {
    if (!tokenValid || !token) return;
    try {
      const response = await apiNewConversation(token);
      const newId = response.conversation_id;
      setConversations([{ id: newId, started_at: new Date().toISOString() }, ...conversations]);
      setActiveConversationId(newId);
      setMessages([]);
    } catch (error) {
      console.error("Failed to create new chat:", error);
    }
  };

  // --- Messaging Handlers ---
  const handleSendMessage = async () => {
  if (!prompt.trim() || isLoading || !activeConversationId || !token) return;

  const userMessage: Message = { role: "user", content: prompt };
  setMessages((prev) => [...prev, userMessage]);
  setPrompt("");
  setIsLoading(true);

  try {
    const activeServerNames = Object.entries(servers)
      .filter(([_, enabled]) => enabled)
      .map(([name]) => name);

    const response = await apiSendMessage(
      {
        prompt: prompt.trim(),
        provider,
        model,
        api_key: apiKey,
        use_mcp: activeServerNames.length > 0,
        conversation_id: activeConversationId,
      },
      token
    );

    const assistantMessage: Message = { role: "assistant", content: response.answer };
    setMessages((prev) => [...prev, assistantMessage]);
  } catch (error) {
    const errorMessage: Message = {
      role: "assistant",
      content: `Error: ${error instanceof Error ? error.message : "Unknown error."}`,
    };
    setMessages((prev) => [...prev, errorMessage]);
  } finally {
    setIsLoading(false);
  }
};


  const handleSendFeedback = async (messageId: number, feedback: number) => {
    try {
      await apiSendFeedback({ message_id: messageId, feedback });
    } catch (error) {
      console.error("Failed to send feedback:", error);
    }
  };

  const getPlaceholderText = () => {
    if (!tokenValid) return "Please log in to start chatting.";
    if (!activeConversationId) return "Start a new chat to begin.";
    return "Ask me something...";
  };

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setToken(null);
    setUser(null);
    setTokenValid(false);
    router.push("/login");
  };

  return (
    <div className={`chat-layout ${sidebarOpen ? "sidebar-open" : "sidebar-closed"}`}>
      <aside className="sidebar">
        <button className="sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
          {sidebarOpen ? "‹" : "›"}
        </button>
        <div className="sidebar-content">
          <div className="user-box">
            <h3>Authenticated User</h3>
            {isVerifying ? (
              <p>Verifying session...</p>
            ) : user ? (
              <>
                <p><strong>{user.username}</strong></p>
                <p style={{ fontSize: "0.8rem", color: "#666" }}>{user.email}</p>
                <button className="validate-btn" onClick={handleLogout}>Logout</button>
              </>
            ) : (
              <p>Not logged in</p>
            )}
          </div>

          {tokenValid && (
            <>
              <div className="config-box">
                <h3>Configuration</h3>
                <select value={provider} onChange={(e) => setProvider(e.target.value)}>
                  {Object.keys(models).map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
                <select value={model} onChange={(e) => setModel(e.target.value)}>
                  {models[provider]?.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
                {provider === "Gemini" && (
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Gemini API Key (Optional)"
                  />
                )}
              </div>

              <button onClick={handleNewChat} className="new-chat-btn">＋ New Chat</button>
              <button onClick={() => router.push("/config")} className="new-chat-btn">⚙️ Configure</button>

              <div className="conversations-list">
                <h3>History</h3>
                {conversations.map((c) => (
                  <div
                    key={c.id}
                    className={`conversation-item ${c.id === activeConversationId ? "active" : ""}`}
                    onClick={() => handleConversationSelect(c.id)}
                  >
                    Chat from {new Date(c.started_at).toLocaleString()}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </aside>

      <main className="chat-main">
        <div className="chat-header">FALCON</div>
        <div className="messages">
          {messages.map((m, i) => (
            <div key={i} className={`message ${m.role}`}>
              <div className="bubble">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                {m.role === "assistant" && m.id && (
                  <div className="feedback">
                    <button onClick={() => handleSendFeedback(m.id!, 1)}>👍</button>
                    <button onClick={() => handleSendFeedback(m.id!, -1)}>👎</button>
                  </div>
                )}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="message assistant">
              <div className="bubble typing-indicator"><span></span><span></span><span></span></div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-bar">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={getPlaceholderText()}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
            disabled={!tokenValid || isLoading || !activeConversationId}
          />
          <button onClick={handleSendMessage} disabled={!tokenValid || isLoading || !activeConversationId}>
            Send
          </button>
        </div>
      </main>
    </div>
  );
}
