"use client";

import { useEffect, useState } from "react";
import { supabase, signedUrl } from "../lib/supabase";
import { bytes, duration, ago, reelTitle, reelDate } from "../lib/format";
import { isOnline } from "./WorkerBadge";

function Deliverables({ reel }) {
  const [video, setVideo] = useState(null);
  const [caption, setCaption] = useState(null);
  const [state, setState] = useState("loading");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const url = await signedUrl(`${reel.name}/reel_final.mp4`);
        if (!alive) return;
        setVideo(url);
        try {
          const txtUrl = await signedUrl(`${reel.name}/caption.txt`);
          const text = await fetch(txtUrl).then((r) => r.text());
          if (alive) setCaption(text);
        } catch {
          /* caption.txt is optional -- an older build may predate it */
        }
        if (alive) setState("ready");
      } catch {
        if (alive) setState("absent");
      }
    })();
    return () => { alive = false; };
  }, [reel.name]);

  if (state === "loading") return <div className="meta"><span className="spin" /> loading deliverables…</div>;

  if (state === "absent") {
    return (
      <div className="meta">
        This reel was built on the laptop but hasn&apos;t been mirrored to the cloud
        yet — that only happens after a build finishes here. The files are on the
        machine under <code>{reel.name}/output/</code>.
      </div>
    );
  }

  return (
    <>
      <video src={video} controls playsInline preload="metadata" />
      <div className="btn-row" style={{ marginTop: 11 }}>
        <a className="btn" href={video} download={`${reel.name}.mp4`}>Download MP4</a>
        {caption && (
          <button className="btn" onClick={() => navigator.clipboard.writeText(caption)}>
            Copy caption
          </button>
        )}
      </div>
      {caption && (
        <>
          <div className="section">caption.txt</div>
          <div className="caption-box">{caption}</div>
        </>
      )}
    </>
  );
}

export default function ReelDetail({ reel, worker, jobs, onBack, onOpenJob }) {
  const [queueing, setQueueing] = useState(false);
  const [driveUrl, setDriveUrl] = useState("");
  const online = isOnline(worker);
  const reelJobs = jobs.filter((j) => j.reel === reel.name).slice(0, 6);
  const busy = jobs.some((j) => ["queued", "claimed", "running"].includes(j.status));

  async function queue(kind, args = {}) {
    setQueueing(true);
    const { data, error } = await supabase
      .from("jobs")
      .insert({ reel: reel.name, kind, args })
      .select()
      .single();
    setQueueing(false);
    if (error) return alert(error.message);
    onOpenJob(data);
  }

  return (
    <>
      <button className="back" onClick={onBack}>← All reels</button>

      <div className="card-head">
        <h2 className="card-title" style={{ fontSize: 21 }}>{reelTitle(reel.name)}</h2>
        <span className="spacer" />
        <span className="card-date">{reelDate(reel.name)}</span>
      </div>

      {!reel.preflight_ok && (
        <div className="note fail" style={{ marginTop: 14 }}>
          <strong>This reel won&apos;t build yet.</strong>
          <ul>
            {reel.preflight_notes?.map((n, i) => <li key={i}>{n}</li>)}
          </ul>
        </div>
      )}

      {reel.preflight_ok && reel.missing_transcripts?.length > 0 && (
        <div className="note warn" style={{ marginTop: 14 }}>
          {reel.missing_transcripts.join(", ")} still {reel.missing_transcripts.length === 1 ? "needs" : "need"} transcribing.
          A build does that first, which adds a few minutes.
        </div>
      )}

      {!online && (
        <div className="note warn" style={{ marginTop: 14 }}>
          The laptop is offline, so nothing will start right now. You can still
          queue a job — it runs as soon as the machine is awake with the worker up.
        </div>
      )}

      <div className="section">Build</div>
      <div className="btn-row">
        <button className="btn primary" disabled={queueing || busy || !reel.preflight_ok}
                onClick={() => queue("build")}>
          Full build
        </button>
        <button className="btn" disabled={queueing || busy || !reel.preflight_ok}
                onClick={() => queue("preview")}>
          Draft preview
        </button>
        <button className="btn" disabled={queueing || busy || !reel.has_output}
                onClick={() => queue("qa")}>
          Re-run QA
        </button>
      </div>
      {busy && (
        <div className="meta" style={{ marginTop: 9 }}>
          A job is already running. Only one builds at a time — two would collide
          in the same <code>work/</code> folder.
        </div>
      )}

      <div className="section">Fetch footage from Drive</div>
      <div className="meta" style={{ marginBottom: 9 }}>
        The laptop downloads it directly. The link travels; the footage never
        passes through here.
      </div>
      <input
        type="url"
        placeholder="https://drive.google.com/…"
        value={driveUrl}
        onChange={(e) => setDriveUrl(e.target.value)}
      />
      <button
        className="btn wide"
        style={{ marginTop: 9 }}
        disabled={queueing || busy || !driveUrl.trim()}
        onClick={() => { queue("fetch", { url: driveUrl.trim() }); setDriveUrl(""); }}
      >
        Download into input/
      </button>

      <div className="section">On the laptop</div>
      <dl className="card" style={{ margin: 0 }}>
        <div className="kv"><dt>Folder</dt><dd><code>{reel.name}</code></dd></div>
        <div className="kv">
          <dt>Input</dt>
          <dd>{reel.input_clips?.map((c) => c.name + c.ext).join(", ") || "—"}</dd>
        </div>
        <div className="kv">
          <dt>Input size</dt>
          <dd>{bytes(reel.input_clips?.reduce((a, c) => a + (c.bytes || 0), 0))}</dd>
        </div>
        <div className="kv">
          <dt>Transcripts</dt>
          <dd>{reel.transcripts?.length || 0} of {reel.input_clips?.length || 0}</dd>
        </div>
        <div className="kv">
          <dt>Config</dt>
          <dd>
            {[["clips.json", reel.has_clips], ["content.json", reel.has_content],
              ["b-roll", reel.has_broll_plan], ["bg_swap.py", reel.has_bg_swap]]
              .filter(([, v]) => v).map(([k]) => k).join(", ") || "none"}
          </dd>
        </div>
        <div className="kv"><dt>Scratch</dt><dd>{bytes(reel.work_bytes)}</dd></div>
        {reel.has_output && (
          <>
            <div className="kv"><dt>Last built</dt><dd>{ago(reel.last_built_at)}</dd></div>
            <div className="kv">
              <dt>Output</dt>
              <dd>{duration(reel.duration_s)} · {bytes(reel.output_bytes)}</dd>
            </div>
          </>
        )}
      </dl>

      {reel.has_output && (
        <>
          <div className="section">Latest cut</div>
          <Deliverables reel={reel} />
        </>
      )}

      {reelJobs.length > 0 && (
        <>
          <div className="section">History</div>
          {reelJobs.map((j) => (
            <button key={j.id} className="card tappable" onClick={() => onOpenJob(j)}>
              <div className="card-head">
                <span className="card-title" style={{ fontSize: 14.5 }}>#{j.id} {j.kind}</span>
                <span className="spacer" />
                <span className={`status ${j.status}`}>{j.status}</span>
              </div>
              <div className="meta">
                {ago(j.created_at)}{j.qa_summary ? ` · ${j.qa_summary}` : ""}
              </div>
            </button>
          ))}
        </>
      )}
    </>
  );
}
