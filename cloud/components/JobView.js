"use client";

import { useEffect, useRef, useState } from "react";
import { supabase } from "../lib/supabase";
import { ago, elapsed, reelTitle } from "../lib/format";

const LIVE = ["queued", "claimed", "running"];

export default function JobView({ job: initial, onBack }) {
  const [job, setJob] = useState(initial);
  const [lines, setLines] = useState([]);
  const [tick, setTick] = useState(0);
  const [stick, setStick] = useState(true);
  const logRef = useRef(null);

  const live = LIVE.includes(job.status);

  // Backfill, then follow. Realtime only delivers rows inserted after we
  // subscribe, so a job opened mid-run needs both.
  useEffect(() => {
    let alive = true;
    (async () => {
      const { data } = await supabase
        .from("job_logs").select("*").eq("job_id", job.id).order("seq");
      if (alive && data) setLines(data);
    })();

    const channel = supabase
      .channel(`job-${job.id}`)
      .on("postgres_changes",
          { event: "INSERT", schema: "public", table: "job_logs", filter: `job_id=eq.${job.id}` },
          (p) => setLines((prev) => (prev.some((l) => l.seq === p.new.seq) ? prev : [...prev, p.new])))
      .on("postgres_changes",
          { event: "UPDATE", schema: "public", table: "jobs", filter: `id=eq.${job.id}` },
          (p) => setJob(p.new))
      .subscribe();

    return () => { alive = false; supabase.removeChannel(channel); };
  }, [job.id]);

  // Keep the elapsed counter moving while it runs.
  useEffect(() => {
    if (!live) return;
    const t = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [live]);

  // Follow the tail unless the user has scrolled up to read something.
  useEffect(() => {
    if (stick && logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [lines, stick]);

  function onScroll(e) {
    const el = e.currentTarget;
    setStick(el.scrollHeight - el.scrollTop - el.clientHeight < 40);
  }

  async function cancel() {
    await supabase.from("jobs").update({ cancel_requested: true }).eq("id", job.id);
  }

  return (
    <>
      <button className="back" onClick={onBack}>← Back</button>

      <div className="card-head">
        <h2 className="card-title" style={{ fontSize: 20 }}>
          {reelTitle(job.reel)}
        </h2>
        <span className="spacer" />
        <span className={`status ${job.status}`}>
          {live && <span className="spin" style={{ marginRight: 7 }} />}
          {job.status}
        </span>
      </div>
      <div className="meta">
        #{job.id} · {job.kind} · queued {ago(job.created_at)}
        {job.started_at && ` · ran ${elapsed(job.started_at, job.finished_at)}`}
      </div>

      {job.error && <div className="note fail" style={{ marginTop: 13 }}>{job.error}</div>}

      {job.qa_summary && (
        <div className={`note ${job.qa_summary.startsWith("FAIL") ? "fail" : "warn"}`}
             style={{ marginTop: 13 }}>
          {job.qa_summary}
        </div>
      )}

      {job.status === "done" && job.deliverables?.length > 0 && (
        <div className="chips" style={{ marginTop: 13 }}>
          {job.deliverables.map((d) => (
            <span key={d.path} className="chip ok">{d.path.split("/").pop()}</span>
          ))}
        </div>
      )}

      <div className="section">
        Log{!stick && live ? " (scrolled up — paused following)" : ""}
      </div>
      <div className="log" ref={logRef} onScroll={onScroll}>
        {lines.length === 0 ? (
          <div className="log-empty">
            {live ? "Waiting for the laptop to pick this up…" : "No output was recorded."}
          </div>
        ) : (
          lines.map((l) => (
            <div key={l.seq} className={`log-line ${l.stream}`}>{l.line}</div>
          ))
        )}
      </div>

      {live && (
        <button className="btn danger wide" style={{ marginTop: 13 }} onClick={cancel}
                disabled={job.cancel_requested}>
          {job.cancel_requested ? "Stopping…" : "Cancel this job"}
        </button>
      )}
    </>
  );
}
