"use client";

import { ago } from "../lib/format";

// The worker heartbeats every 30s; anything older than 90s means the laptop is
// asleep, offline, or the daemon isn't running.
export const STALE_MS = 90_000;

export function isOnline(worker) {
  return Boolean(worker?.online_at && Date.now() - new Date(worker.online_at).getTime() < STALE_MS);
}

export default function WorkerBadge({ worker }) {
  const online = isOnline(worker);
  return (
    <div className="worker" title={worker?.host || ""}>
      <span className={`pulse ${online ? "on" : "off"}`} />
      {online ? (
        <span>
          laptop up
          {worker?.free_disk_gb != null && ` · ${worker.free_disk_gb} GB free`}
        </span>
      ) : (
        <span>laptop offline · {ago(worker?.online_at)}</span>
      )}
    </div>
  );
}
