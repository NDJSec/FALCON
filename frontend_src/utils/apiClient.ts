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

// Use the NEXT_PUBLIC_ prefix for environment variables exposed to the browser.
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

// --- Helper for API calls ---
async function fetcher<T>(url: string, options: RequestInit = {}): Promise<T> {
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({})); // Gracefully handle non-json errors
    throw new Error(
      errorData.detail || `HTTP error! status: ${response.status}`
    );
  }

  return response.json();
}

// --- API Functions ---

export const apiGetConversations = (token: string): Promise<Conversation[]> => {
  return fetcher(`${API_BASE}/conversations/${token}`);
};

export const apiGetMessagesForConversation = (
  conversationId: string
): Promise<Message[]> => {
  return fetcher(`${API_BASE}/messages/${conversationId}`);
};

export const apiNewConversation = (
  token: string
): Promise<NewConversationResponse> => {
  return fetcher(`${API_BASE}/conversations/new/${token}`, {
    method: "POST",
  });
};

export const apiGetTools = (): Promise<Tool[]> => {
  return fetcher(`${API_BASE}/tools`);
};

export const apiGetModels = (): Promise<ModelProviders> => {
  return fetcher(`${API_BASE}/models`);
};

export const apiSendMessage = (payload: ChatRequest): Promise<ChatResponse> => {
  return fetcher(`${API_BASE}/chat`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
};

export const apiSendFeedback = (payload: FeedbackRequest): Promise<{ status: string }> => {
  return fetcher(`${API_BASE}/feedback`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
};
