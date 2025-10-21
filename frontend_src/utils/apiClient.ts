import {
  Message,
  Conversation,
  Tool,
  ModelProviders,
  ChatRequest,
  ChatResponse,
  FeedbackRequest,
  NewConversationResponse,
} from "../shared/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// --- Helper for API calls ---
async function fetcher<T>(url: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
  }

  return response.json();
}

// --- New: Login function ---
export const loginUser = async (payload: {
  username: string;
  password: string;
}): Promise<{ access_token: string; refresh_token?: string }> => {
  return fetcher(`${API_BASE}/auth/login`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
};

// --- Optional: Refresh token ---
export const refreshToken = async (): Promise<{ access_token: string }> => {
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) throw new Error("No refresh token available");

  return fetcher(`${API_BASE}/auth/refresh`, {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
};

// --- Existing API Functions ---
export const apiGetConversations = (token?: string | null): Promise<Conversation[]> =>
  fetcher(`${API_BASE}/conversations`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });

export const apiGetMessagesForConversation = (conversationId: string): Promise<Message[]> =>
  fetcher(`${API_BASE}/messages/${conversationId}`);

export const apiNewConversation = (token?: string): Promise<NewConversationResponse> =>
  fetcher(`${API_BASE}/conversations/new`, { method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {} });

export const apiGetTools = (): Promise<Tool[]> => fetcher(`${API_BASE}/tools`);

export const apiGetModels = (): Promise<ModelProviders> => fetcher(`${API_BASE}/models`);

export const apiSendMessage = (payload: ChatRequest, token?: string): Promise<ChatResponse> =>
  fetcher(`${API_BASE}/chat`, {
    method: "POST",
    body: JSON.stringify(payload),
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

export const apiSendFeedback = (payload: FeedbackRequest): Promise<{ status: string }> =>
  fetcher(`${API_BASE}/feedback`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
