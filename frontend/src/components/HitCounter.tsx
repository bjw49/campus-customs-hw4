import { useEffect, useState } from "react";
import { fetchVisitCount, recordVisit } from "../api";

const SESSION_FLAG = "cc_visit_counted";

/** A real hit counter: counts once per browser session (not per page load),
 * styled like the "you are visitor #" counters every 90s personal site had. */
export default function HitCounter() {
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    const alreadyCounted = sessionStorage.getItem(SESSION_FLAG);
    const request = alreadyCounted ? fetchVisitCount() : recordVisit();
    request
      .then((v) => {
        sessionStorage.setItem(SESSION_FLAG, "1");
        setCount(v.count);
      })
      .catch(() => {});
  }, []);

  const digits = String(count ?? 0).padStart(6, "0").split("");

  return (
    <div className="hit-counter" aria-label={count === null ? "Loading visitor count" : `Visitor number ${count}`}>
      <span className="hit-counter-label">you are visitor #</span>
      <span className="hit-counter-digits">
        {digits.map((d, i) => (
          <span key={i}>{d}</span>
        ))}
      </span>
    </div>
  );
}
