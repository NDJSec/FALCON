export type Message = {
  id?: number;
  role: "user" | "assistant";
  content: string;
  feedback?: number;
};

export type Conversation = {
  id: string;
  started_at: string;
};

export type Tool = {
  name: string;
  enabled: boolean;
};

export type ModelProviders = {
  [provider: string]: string[];
};

// --- API Request Payloads ---

export type ChatRequest = {
  token: string;
  prompt: string;
  provider: string;
  model: string;
  api_key?: string;
  use_mcp: boolean;
  conversation_id: string;
};

export type FeedbackRequest = {
  message_id: number;
  feedback: number; // 1 for up, -1 for down
};

// --- API Response Payloads ---

export type ChatResponse = {
  answer: string;
  conversation_id: string;
};

export type NewConversationResponse = {
  conversation_id: string;
};

