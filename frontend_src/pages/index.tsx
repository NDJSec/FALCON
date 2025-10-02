import { useState, useEffect, useRef } from "react";
import {
  apiGetConversations,
  apiGetMessagesForConversation,
  apiNewConversation,
  apiGetTools,
  apiGetModels,
  apiSendMessage,
  apiSendFeedback,
} from "../utils/apiClient";
import {
  Message,
  Conversation,
  Tool,
  ModelProviders,
} from "../shared/types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function Home() {
  // --- State Management ---
  const [token, setToken] = useState("");
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
  const [tools, setTools] = useState<Tool[]>([]);
  
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // --- Effects ---

  // Scroll to the bottom of the messages list when new messages are added
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Fetch initial data (models and tools) when the component mounts
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
        
        const fetchedTools = await apiGetTools();
        setTools(fetchedTools.map(t => ({...t, enabled: true})));
      } catch (error) {
        console.error("Failed to fetch initial data:", error);
      }
    };
    fetchInitialData();
  }, []);

  // --- Event Handlers ---

  const handleTokenValidation = async () => {
    if (!token) {
      setTokenValid(false);
      return;
    }
    try {
      const convos = await apiGetConversations(token);
      setConversations(convos);
      setTokenValid(true);
      if (convos.length > 0) {
        handleConversationSelect(convos[0].id);
      } else {
        // No conversations exist, prompt user to create one
        setMessages([{ role: 'assistant', content: 'Token is valid. Start a new chat to begin.' }]);
        setActiveConversationId(null);
      }
    } catch (error) {
      console.error("Token validation failed:", error);
      setTokenValid(false);
      setConversations([]);
      setMessages([{ role: 'assistant', content: 'Invalid token. Please check and try again.' }]);
    }
  };

  const handleConversationSelect = async (id: string) => {
    setActiveConversationId(id);
    try {
      const history = await apiGetMessagesForConversation(id);
      setMessages(history);
    } catch (error) {
      console.error("Failed to load conversation history:", error);
      setMessages([{ role: 'assistant', content: 'Failed to load conversation history.' }]);
    }
  };

  const handleNewChat = async () => {
    if (!tokenValid) return;
    try {
      const response = await apiNewConversation(token);
      const newId = response.conversation_id;
      // Add to top of list and make it active
      setConversations([{ id: newId, started_at: new Date().toISOString() }, ...conversations]);
      setActiveConversationId(newId);
      setMessages([]);
    } catch (error) {
      console.error("Failed to create new chat:", error);
    }
  };

  const handleSendMessage = async () => {
    // Guard against sending without an active conversation
    if (!prompt.trim() || isLoading || !activeConversationId) return;

    const userMessage: Message = { role: "user", content: prompt };
    setMessages((prev) => [...prev, userMessage]);
    setPrompt("");
    setIsLoading(true);

    try {
      const response = await apiSendMessage({
        token,
        prompt: prompt.trim(),
        provider,
        model,
        api_key: apiKey,
        use_mcp: tools.some(t => t.enabled),
        conversation_id: activeConversationId,
      });

      const assistantMessage: Message = { role: "assistant", content: response.answer };
      setMessages((prev) => [...prev, assistantMessage]);

    } catch (error) {
        const errorMessage: Message = { role: "assistant", content: `Error: ${error instanceof Error ? error.message : 'An unknown error occurred.'}` };
        setMessages(prev => [...prev, errorMessage]);
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

  const toggleTool = (index: number) => {
    setTools(tools.map((t, i) => i === index ? { ...t, enabled: !t.enabled } : t));
  };
  
  const getPlaceholderText = () => {
      if (!tokenValid) return "Please enter and validate your token.";
      if (!activeConversationId) return "Start a new chat to begin.";
      return "Ask me something...";
  }


  return (
    <div className={`chat-layout ${sidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
      <aside className="sidebar">
        <button className="sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
          {sidebarOpen ? '‹' : '›'}
        </button>
        <div className="sidebar-content">
            <div className="user-box">
                <h3>User Authentication</h3>
                <div className="token-input-group">
                    <input
                      type="text"
                      value={token}
                      onChange={(e) => setToken(e.target.value)}
                      placeholder="Enter User Token"
                    />
                    <button onClick={handleTokenValidation} className="validate-btn">Validate</button>
                </div>
                <span className={`token-status ${tokenValid ? "valid" : "invalid"}`}>
                    {token ? (tokenValid ? "● Token Valid" : "● Token Invalid") : ""}
                </span>
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
                        <div className="tools-box">
                            <h4>MCP Tools</h4>
                            {tools.map((t, i) => (
                                <label key={i} className="tool-toggle">
                                    <input type="checkbox" checked={t.enabled} onChange={() => toggleTool(i)} /> 
                                    {t.name}
                                </label>
                            ))}
                        </div>
                    </div>

                    <button onClick={handleNewChat} className="new-chat-btn">
                        ＋ New Chat
                    </button>

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
        <div className="chat-header">
            FALCON
        </div>
        <div className="messages">
          {messages.map((m, i) => (
            <div key={i} className={`message ${m.role}`}>
              <div className="bubble">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {m.content}
                </ReactMarkdown>
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
                  <div className="bubble typing-indicator">
                      <span></span><span></span><span></span>
                  </div>
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
