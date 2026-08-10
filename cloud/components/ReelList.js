"use client";

import { bytes, duration, ago, reelTitle, reelDate } from "../lib/format";

function JobRow({ job, onOpen }) {
  return (
    <button className="card tappable" onClick={() => onOpen(job)}>
      <div className="card-head">
        <span className="card-title">{reelTitle(job.reel)}</span>
        <span className="spacer" />
        <span className={`status ${job.status}`}>{job.status}</span>
      </div>
      <div className="meta">
        {job.kind} · queued {ago(job.created_at)}
        {job.qa_summary ? ` · ${job.qa_summary}` : ""}
      </div>
    </button>
  );
}

export default function ReelList({ reels, jobs, onOpenReel, onOpenJob }) {
  const active = jobs.filter((j) => ["queued", "claimed", "running"].includes(j.status));
  const recent = jobs.filter((j) => !["queued", "claimed", "running"].includes(j.status)).slice(0, 5);

  if (!reels.length) {
    return (
      <div className="empty">
        No reels yet.
        <br />
        Once the worker runs on your laptop it publishes every folder under{" "}
        <code>reels/</code> that has an <code>input/</code> directory.
      </div>
    );
  }

  return (
    <>
      {active.length > 0 && (
        <>
          <div className="section">In progress</div>
          {active.map((j) => <JobRow key={j.id} job={j} onOpen={onOpenJob} />)}
        </>
      )}

      <div className="section">Reels</div>
      {reels.map((r) => (
        <button key={r.name} className="card tappable" onClick={() => onOpenReel(r)}>
          <div className="card-head">
            <span className="card-title">{reelTitle(r.name)}</span>
            <span className="spacer" />
            <span className="card-date">{reelDate(r.name)}</span>
          </div>
          <div className="meta">
            {r.input_clips?.length || 0} clip{r.input_clips?.length === 1 ? "" : "s"}
            {r.has_output
              ? ` · built ${ago(r.last_built_at)} · ${duration(r.duration_s)} · ${bytes(r.output_bytes)}`
              : " · never built"}
          </div>
          <div className="chips">
            {r.preflight_ok
              ? <span className="chip ok">ready to build</span>
              : <span className="chip fail">{r.preflight_notes?.length || 0} blocker{r.preflight_notes?.length === 1 ? "" : "s"}</span>}
            {r.missing_transcripts?.length > 0 && (
              <span className="chip warn">{r.missing_transcripts.length} to transcribe</span>
            )}
            {r.has_bg_swap && <span className="chip gold">bg swap</span>}
            {r.work_bytes > 0 && <span className="chip">{bytes(r.work_bytes)} scratch</span>}
          </div>
        </button>
      ))}

      {recent.length > 0 && (
        <>
          <div className="section">Recent jobs</div>
          {recent.map((j) => <JobRow key={j.id} job={j} onOpen={onOpenJob} />)}
        </>
      )}
    </>
  );
}
