/** A scrolling 90s-style ticker, purely decorative chrome for the theme. */
export default function MarqueeTicker() {
  const text =
    "★ NEW DROP ★ HOODIES RESTOCKED ★ SIGN THE GUESTBOOK ★ ASK THE CHAT BOT ANYTHING ★ CAMPUS CUSTOMS DOT COM ★";
  return (
    <div className="marquee-ticker" aria-hidden="true">
      <span>{text}</span>
    </div>
  );
}
