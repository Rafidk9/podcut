export function bytes(n) {
  if (n === null || n === undefined) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1e6) return `${(n / 1e3).toFixed(0)} KB`;
  if (n < 1e9) return `${(n / 1e6).toFixed(1)} MB`;
  return `${(n / 1e9).toFixed(2)} GB`;
}

export function duration(s) {
  if (!s && s !== 0) return "—";
  const m = Math.floor(s / 60);
  const rest = (s % 60).toFixed(0).padStart(m ? 2 : 1, "0");
  return m ? `${m}:${rest}` : `${rest}s`;
}

export function ago(iso) {
  if (!iso) return "never";
  const secs = (Date.now() - new Date(iso).getTime()) / 1000;
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  const days = Math.floor(secs / 86400);
  return days < 30 ? `${days}d ago` : new Date(iso).toLocaleDateString();
}

/** Elapsed time for a job, live-updating while it runs. */
export function elapsed(startIso, endIso) {
  if (!startIso) return "—";
  const end = endIso ? new Date(endIso).getTime() : Date.now();
  const secs = Math.max(0, Math.round((end - new Date(startIso).getTime()) / 1000));
  const m = Math.floor(secs / 60);
  return m ? `${m}m ${secs % 60}s` : `${secs}s`;
}

/** "2026-08-07_maheesha-just-ask-expo" -> "Maheesha Just Ask Expo" */
export function reelTitle(name) {
  const slug = name.replace(/^\d{4}-\d{2}-\d{2}_/, "");
  return slug.split("-").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

export function reelDate(name) {
  const m = name.match(/^(\d{4}-\d{2}-\d{2})_/);
  return m ? m[1] : "";
}
