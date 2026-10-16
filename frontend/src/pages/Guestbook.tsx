import { FormEvent, useEffect, useState } from "react";
import { fetchGuestbook, signGuestbook } from "../api";
import type { GuestbookEntry } from "../api";

export default function Guestbook() {
  const [entries, setEntries] = useState<GuestbookEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchGuestbook().then(setEntries).catch((e: Error) => setError(e.message));
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || !message.trim() || submitting) return;
    setSubmitting(true);
    try {
      const entry = await signGuestbook(name.trim(), message.trim());
      setEntries((prev) => (prev ? [entry, ...prev] : [entry]));
      setName("");
      setMessage("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't sign the guestbook.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="guestbook">
      <h1 className="guestbook-title">~*~ sign my guestbook ~*~</h1>
      <p className="guestbook-subtitle">thanks for stopping by campus customs dot com!! leave a msg below</p>

      <form className="guestbook-form" onSubmit={onSubmit}>
        <input
          placeholder="your name / screen name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={40}
          aria-label="Your name"
        />
        <textarea
          placeholder="say something nice (or just say hi)"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          maxLength={300}
          rows={3}
          aria-label="Your message"
        />
        <button type="submit" disabled={submitting || !name.trim() || !message.trim()}>
          {submitting ? "signing…" : "sign guestbook"}
        </button>
        {error && <p className="error">{error}</p>}
      </form>

      {!entries ? (
        <p>loading guestbook…</p>
      ) : (
        <div className="guestbook-wall">
          {entries.map((entry) => (
            <div key={entry.id} className="guestbook-entry">
              <p className="guestbook-entry-name">{entry.name}</p>
              <p className="guestbook-entry-message">{entry.message}</p>
              <p className="guestbook-entry-date">{entry.created_at}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
