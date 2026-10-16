import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { fetchChatHistory, formatPrice, sendChat } from "../api";
import { useAuth } from "../auth/AuthContext";
import StickerBadges from "./StickerBadges";
import type { Product } from "../types";

interface Message {
  role: "user" | "assistant";
  text: string;
  products?: Product[];
}

const GREETING: Message = {
  role: "assistant",
  text: "Hi! I'm the Campus Customs assistant. Ask me about our Yale gear.",
};

// The model can generate (and the server can stream) faster than this, so
// reveal text at a steady, readable pace instead of however fast chunks
// happen to arrive - a deliberately slower, consistent typewriter effect.
const REVEAL_CHARS_PER_SECOND = 40;
const REVEAL_TICK_MS = 50;
const REVEAL_CHARS_PER_TICK = Math.max(1, Math.round((REVEAL_CHARS_PER_SECOND * REVEAL_TICK_MS) / 1000));

/** product_id of the current page, if we're on a product detail page (page context). */
function currentProductId(pathname: string): string | undefined {
  const match = pathname.match(/^\/products\/([^/]+)$/);
  return match ? decodeURIComponent(match[1]) : undefined;
}

export default function ChatWidget() {
  const { user } = useAuth();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([GREETING]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // Throttled reveal: tokens arrive into `buffer` as fast as the network
  // delivers them, but `shown` only advances REVEAL_CHARS_PER_TICK
  // characters at a time, on a fixed timer - so the chat bubble fills in at
  // a steady ~40 chars/sec regardless of how quickly the model responds.
  const bufferRef = useRef("");
  const shownRef = useRef(0);
  const timerRef = useRef<number | null>(null);
  const streamDoneRef = useRef(false);
  const onFullyRevealedRef = useRef<() => void>(() => {});

  useEffect(() => {
    // Stop the reveal timer if the widget unmounts mid-stream.
    return () => {
      if (timerRef.current !== null) window.clearInterval(timerRef.current);
    };
  }, []);

  function ensureRevealTimer() {
    if (timerRef.current !== null) return;
    timerRef.current = window.setInterval(() => {
      if (shownRef.current < bufferRef.current.length) {
        shownRef.current = Math.min(bufferRef.current.length, shownRef.current + REVEAL_CHARS_PER_TICK);
        setMessages((m) => {
          const next = [...m];
          const last = next[next.length - 1];
          next[next.length - 1] = { ...last, text: bufferRef.current.slice(0, shownRef.current) };
          return next;
        });
      } else if (streamDoneRef.current) {
        window.clearInterval(timerRef.current!);
        timerRef.current = null;
        onFullyRevealedRef.current();
      }
    }, REVEAL_TICK_MS);
  }

  // Reload the saved conversation whenever who's logged in changes (login,
  // logout, or a page refresh that restores the session). Guests always get
  // a fresh greeting, since their chats aren't persisted.
  useEffect(() => {
    let cancelled = false;
    if (!user) {
      setMessages([GREETING]);
      return;
    }
    fetchChatHistory(user.id)
      .then((history) => {
        if (cancelled) return;
        setMessages(
          history.length
            ? history.map((h) => ({
                role: h.role,
                text: h.content,
                products: h.products.length ? h.products : undefined,
              }))
            : [GREETING],
        );
      })
      .catch(() => {
        if (!cancelled) setMessages([GREETING]);
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, open]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);

    bufferRef.current = "";
    shownRef.current = 0;
    streamDoneRef.current = false;
    onFullyRevealedRef.current = () => {};

    // The user's message, plus an empty assistant placeholder that fills in
    // at a steady pace as the reply streams in, instead of waiting for it all at once.
    setMessages((m) => [...m, { role: "user", text }, { role: "assistant", text: "" }]);
    try {
      const reply = await sendChat(text, user?.id, currentProductId(location.pathname), (delta) => {
        bufferRef.current += delta;
        ensureRevealTimer();
      });
      streamDoneRef.current = true;
      // Let the throttled reveal finish catching up to the buffer before
      // swapping in the final message (which also adds product cards).
      await new Promise<void>((resolve) => {
        if (shownRef.current >= bufferRef.current.length) {
          resolve();
          return;
        }
        onFullyRevealedRef.current = resolve;
        ensureRevealTimer();
      });
      setMessages((m) => [
        ...m.slice(0, -1),
        { role: "assistant", text: reply.reply, products: reply.products.length ? reply.products : undefined },
      ]);
    } catch {
      streamDoneRef.current = true;
      if (timerRef.current !== null) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
      setMessages((m) => [
        ...m.slice(0, -1),
        { role: "assistant", text: "Sorry, I couldn't reach the server. Please try again." },
      ]);
    } finally {
      setSending(false);
    }
  }

  if (!open) {
    return (
      <button className="chat-fab" onClick={() => setOpen(true)} aria-label="Open chat">
        Chat
      </button>
    );
  }

  return (
    <section className="chat-panel" aria-label="Chat">
      <div className="chat-header">
        <div>
          <span>Campus Customs Assistant</span>
          <div className="aim-status">
            <span className={`aim-status-dot ${sending ? "typing" : "online"}`} aria-hidden="true" />
            {sending ? "typing…" : "online"}
          </div>
        </div>
        <button onClick={() => setOpen(false)} aria-label="Close chat">
          ×
        </button>
      </div>
      <div className="chat-messages">
        {messages.map((m, i) => {
          const isStreamingPlaceholder = sending && i === messages.length - 1 && m.role === "assistant" && m.text === "";
          return (
            <div key={i} className={`chat-turn ${m.role}`}>
              <div className={`chat-bubble ${m.role}`}>{isStreamingPlaceholder ? "…" : m.text}</div>
              {m.products && (
                <div className="chat-product-cards">
                  {m.products.map((p) => (
                    <Link key={p.product_id} to={`/products/${p.product_id}`} className="chat-product-card">
                      <StickerBadges product={p} />
                      <img src={p.image_url} alt={p.name} loading="lazy" />
                      <div className="chat-product-card-body">
                        <p className="cpc-name">{p.name}</p>
                        <p className="cpc-price">{formatPrice(p.price)}</p>
                        <p className="cpc-desc">{p.description}</p>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          );
        })}
        <div ref={endRef} />
      </div>
      <form className="chat-input" onSubmit={onSubmit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          aria-label="Message"
        />
        <button type="submit" disabled={sending || !input.trim()}>
          Send
        </button>
      </form>
    </section>
  );
}
