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
