import type { Product, User } from "./types";

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return res.json() as Promise<T>;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data?.detail;
    const message = Array.isArray(detail)
      ? detail.map((d: { msg?: string }) => d.msg).join(" ")
      : typeof detail === "string"
        ? detail
        : `Request failed (${res.status})`;
    throw new Error(message);
  }
  return data as T;
}

export const fetchProducts = () => getJson<Product[]>("/api/products");
export const fetchProduct = (id: string) =>
  getJson<Product>(`/api/products/${encodeURIComponent(id)}`);

export interface SignupPayload {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  confirm_password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export const signup = (payload: SignupPayload) => postJson<User>("/api/signup", payload);
export const login = (payload: LoginPayload) => postJson<User>("/api/login", payload);

export interface ChatReply {
  reply: string;
  tools_used: string[];
  products: Product[];
}

export interface ChatHistoryMessage {
  role: "user" | "assistant";
  content: string;
  products: Product[];
  created_at: string;
}

type ChatStreamMessage = { type: "token"; text: string } | ({ type: "final" } & ChatReply);

/**
 * Sends a chat message and streams the reply: calls `onToken` with each text
 * chunk as the agent generates it (so the UI can render progressively, like a
 * normal chat), then resolves with the final ChatReply (full trace, tools
 * used, and product cards) once the agent is done.
 */
export async function sendChat(
  message: string,
  userId: number | undefined,
  currentProductId: string | undefined,
  onToken: (text: string) => void,
): Promise<ChatReply> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      user_id: userId ?? null,
      current_product_id: currentProductId ?? null,
    }),
  });
  if (!res.ok || !res.body) throw new Error(`Chat failed (${res.status})`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let final: ChatReply | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let newlineIndex: number;
    while ((newlineIndex = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, newlineIndex);
      buffer = buffer.slice(newlineIndex + 1);
      if (!line.trim()) continue;
      const msg = JSON.parse(line) as ChatStreamMessage;
      if (msg.type === "token") onToken(msg.text);
      else final = msg;
    }
  }

  if (!final) throw new Error("Chat stream ended without a response.");
  return final;
}

export const fetchChatHistory = (userId: number) =>
  getJson<ChatHistoryMessage[]>(`/api/chat/history?user_id=${userId}`);

export const formatPrice = (price: number) => `$${price.toFixed(2)}`;

export interface VisitCount {
  count: number;
}

export const recordVisit = () => postJson<VisitCount>("/api/visits", {});
export const fetchVisitCount = () => getJson<VisitCount>("/api/visits");

export interface GuestbookEntry {
  id: number;
  name: string;
  message: string;
  created_at: string;
}

export const fetchGuestbook = () => getJson<GuestbookEntry[]>("/api/guestbook");
export const signGuestbook = (name: string, message: string) =>
  postJson<GuestbookEntry>("/api/guestbook", { name, message });
