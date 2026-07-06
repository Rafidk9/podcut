"use client";

import { useState } from "react";

function fmt(t) {
  const m = Math.floor(t / 60), s = t - m * 60;
  return `${m}:${s.toFixed(1).padStart(4, "0")}`;
}

const CUT_LABEL = { filler: "filler", pause: "dead air", lead: "lead-in", tail: "tail" };

export default function Home() {
  const [mode, setMode] = useState("podcast");
  const [busy, setBusy] = useState(false);
  const [logs, setLogs] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [review, setReview] = useState(true);
  // review state
  const [jobId, setJobId] = useState(null);
  const [plan, setPlan] = useState(null);
  const [restores, setRestores] = useState({});   // cut index -> bool
  const [flips, setFlips] = useState({});         // segment index -> camera
  const [zoomOff, setZoomOff] = useState({});     // reason -> bool
  const [preview, setPreview] = useState(null);   // "seg-3" | "cut-2" | null
  const [names, setNames] = useState({ A: "", B: "" }); // lower-third names

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true); setError(""); setResult(null); setPlan(null);
    setRestores({}); setFlips({}); setZoomOff({}); setPreview(null);
    setLogs(review
      ? "Uploading & analyzing… nothing is rendered until you approve the cut list."
      : "Uploading & processing… this runs ffmpeg, so give it a moment.");
    try {
      const fd = new FormData(e.target);
      fd.set("mode", mode);
      if (review) fd.set("review", "true");
      const res = await fetch("/api/process", { method: "POST", body: fd });
      const data = await res.json();
      if (!data.ok) { setError(data.error || "Processing failed."); setLogs(data.logs || ""); }
      else if (review) {
        setJobId(data.jobId); setPlan(data.plan); setLogs(data.logs || "");
        const n = data.plan?.options?.speaker_names || {};
        setNames({ A: n.A || "", B: n.B || "" });
      }
      else { setResult(data); setLogs(data.logs || ""); }
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onRender() {
    setBusy(true); setError(""); setLogs("Rendering the approved cut… this runs ffmpeg, so give it a moment.");
    try {
      const edited = structuredClone(plan);
      edited.cuts.forEach((c, i) => { c.restore = !!restores[i]; });
      edited.camera_overrides = Object.entries(flips)
        .filter(([i, cam]) => cam !== plan.segments[i].camera)
        .map(([i, cam]) => ({
          start: plan.segments[i].src_start, end: plan.segments[i].src_end, camera: cam,
        }));
      edited.zoom_disabled_reasons = Object.keys(zoomOff).filter((r) => zoomOff[r]);
      edited.options.speaker_names = {
        ...(names.A.trim() ? { A: names.A.trim() } : {}),
        ...(names.B.trim() ? { B: names.B.trim() } : {}),
      };
      const res = await fetch("/api/render-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId, plan: edited }),
      });
      const data = await res.json();
      if (!data.ok) { setError(data.error || "Render failed."); setLogs(data.logs || ""); }
      else { setResult(data); setPlan(null); setLogs(data.logs || ""); }
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  const r = result?.report || {};
  const isPodcast = plan?.mode === "podcast";
  const zoomReasons = plan ? [...new Set(plan.zoom_events.map((z) => z.reason))] : [];
  const nRestored = Object.values(restores).filter(Boolean).length;
  const nFlipped = plan ? Object.entries(flips)
    .filter(([i, cam]) => cam !== plan.segments[i].camera).length : 0;

  return (
    <div className="wrap">
      <div className="brand">
        <div className="logo">▸</div>
        <h1>PodCut</h1>
      </div>
      <p className="sub">
        Auto-edit raw footage: remove filler words &amp; dead air, and — for two-camera
        interviews — cut to whoever is speaking (and to a person just before they answer).
      </p>

      <form onSubmit={onSubmit}>
        <div className="modes">
          <div className={`mode ${mode === "podcast" ? "active" : ""}`} onClick={() => setMode("podcast")}>
            <h3>🎙️ Podcast / Interview</h3>
            <p>Two camera angles → sync → speaker-aware switching → clean up.</p>
          </div>
          <div className={`mode ${mode === "single" ? "active" : ""}`} onClick={() => setMode("single")}>
            <h3>🎬 Single speaker</h3>
            <p>One talking-head clip → filler &amp; pause removal.</p>
          </div>
        </div>

        <div className="card">
          {mode === "podcast" ? (
            <div className="row">
              <div>
                <label className="field">Camera 1 <span className="hint">(speaker A near mic)</span></label>
                <input type="file" name="cam1" accept="video/*" required />
              </div>
              <div>
                <label className="field">Camera 2 <span className="hint">(speaker B near mic)</span></label>
                <input type="file" name="cam2" accept="video/*" required />
              </div>
            </div>
          ) : (
            <div>
              <label className="field">Video</label>
              <input type="file" name="video" accept="video/*" required />
            </div>
          )}

          <label className="field">
            Transcript JSON <span className="hint">(optional — skips transcription; enables smart annotation offline)</span>
          </label>
          <input type="file" name="transcript" accept="application/json,.json" />

          {mode === "podcast" ? (
            <div className="row">
              <div>
                <label className="field">Speaker A name <span className="hint">(optional — animated lower-third)</span></label>
                <input type="text" name="speakerA" className="text" placeholder="e.g. Alice Ford" />
              </div>
              <div>
                <label className="field">Speaker B name <span className="hint">(optional)</span></label>
                <input type="text" name="speakerB" className="text" placeholder="e.g. Bob Reyes" />
              </div>
            </div>
          ) : (
            <div>
              <label className="field">Speaker name <span className="hint">(optional — animated lower-third)</span></label>
              <input type="text" name="speakerA" className="text" placeholder="e.g. Alice Ford" />
            </div>
          )}

          <div className="checks">
            <label><input type="checkbox" name="noFillers" value="true" /> Keep filler words</label>
            <label><input type="checkbox" name="noSilence" value="true" /> Keep long pauses</label>
            <label><input type="checkbox" name="noCaptions" value="true" /> Skip captions</label>
            <label>
              <input type="checkbox" checked={review} onChange={(e) => setReview(e.target.checked)} />
              Review cuts before rendering
            </label>
          </div>

          <button className="run" type="submit" disabled={busy}>
            {busy ? <><span className="spinner" />Processing…</>
              : review ? "Analyze footage →" : "Edit footage →"}
          </button>
        </div>
      </form>

      {error && <div className="card err">⚠ {error}</div>}

      {plan && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Review the cut</h3>
          <p className="hint" style={{ marginTop: -8 }}>
            Nothing has been rendered yet. Flip a camera, restore a cut you want to keep,
            or turn off zoom moves — then render.
          </p>

          <h4 className="rev-h">Camera plan <span className="hint">({plan.segments.length} shots — ▶ plays the first seconds)</span></h4>
          <div className="seg-list">
            {plan.segments.map((s, i) => {
              const cam = flips[i] ?? s.camera;
              const key = `seg-${i}`;
              const pvCam = isPodcast ? cam : "src";
              return (
                <div key={i}>
                  <div className="seg">
                    <button type="button" className={`pv-btn ${preview === key ? "on" : ""}`}
                      title="Preview this shot"
                      onClick={() => setPreview(preview === key ? null : key)}>
                      {preview === key ? "■" : "▶"}
                    </button>
                    <span className="seg-time">{fmt(s.src_start)}–{fmt(s.src_end)}</span>
                    {isPodcast ? (
                      <button type="button"
                        className={`cam-badge ${cam} ${cam !== s.camera ? "flipped" : ""}`}
                        title="Click to flip camera"
                        onClick={() => setFlips({ ...flips, [i]: cam === "cam1" ? "cam2" : "cam1" })}>
                        {cam === "cam1" ? "Cam 1" : cam === "cam2" ? "Cam 2" : cam}
                      </button>
                    ) : (
                      <span className="cam-badge">clip</span>
                    )}
                    <span className="seg-reason">{s.reason}</span>
                    <span className="seg-preview">{s.preview || "—"}</span>
                  </div>
                  {preview === key && (
                    <video className="pv-video" controls autoPlay
                      src={`/api/preview?job=${jobId}&camera=${pvCam}&start=${s.src_start}&end=${s.src_end}`} />
                  )}
                </div>
              );
            })}
          </div>

          <h4 className="rev-h">Removed cuts <span className="hint">(▶ to hear what was cut; tick to put back in)</span></h4>
          <div className="cut-list">
            {plan.cuts.map((c, i) => {
              const key = `cut-${i}`;
              return (
                <div key={i}>
                  <label className={`cut ${restores[i] ? "restored" : ""}`}>
                    <button type="button" className={`pv-btn ${preview === key ? "on" : ""}`}
                      title="Preview the removed material"
                      onClick={(e) => { e.preventDefault(); setPreview(preview === key ? null : key); }}>
                      {preview === key ? "■" : "▶"}
                    </button>
                    <input type="checkbox" checked={!!restores[i]}
                      onChange={(e) => setRestores({ ...restores, [i]: e.target.checked })} />
                    <span className="cut-kind">{CUT_LABEL[c.kind] || c.kind}</span>
                    <span className="seg-time">{fmt(c.start)}–{fmt(c.end)}</span>
                    {c.text && <span className="cut-text">“{c.text}”</span>}
                  </label>
                  {preview === key && (
                    <video className="pv-video" controls autoPlay
                      src={`/api/preview?job=${jobId}&camera=${isPodcast ? "cam1" : "src"}&start=${c.start}&end=${c.end}`} />
                  )}
                </div>
              );
            })}
            {plan.cuts.length === 0 && <p className="hint">Nothing was removed.</p>}
          </div>

          <h4 className="rev-h">Lower-thirds <span className="hint">(shown on each speaker's first appearance; leave blank for none)</span></h4>
          <div className="row">
            <div>
              <input type="text" className="text" placeholder={isPodcast ? "Speaker A name (Cam 1)" : "Speaker name"}
                value={names.A} onChange={(e) => setNames({ ...names, A: e.target.value })} />
            </div>
            {isPodcast && (
              <div>
                <input type="text" className="text" placeholder="Speaker B name (Cam 2)"
                  value={names.B} onChange={(e) => setNames({ ...names, B: e.target.value })} />
              </div>
            )}
          </div>

          {zoomReasons.length > 0 && (
            <>
              <h4 className="rev-h">Zoom moves</h4>
              <div className="checks">
                {zoomReasons.map((reason) => (
                  <label key={reason}>
                    <input type="checkbox" checked={!zoomOff[reason]}
                      onChange={(e) => setZoomOff({ ...zoomOff, [reason]: !e.target.checked })} />
                    {reason} ({plan.zoom_events.filter((z) => z.reason === reason).length})
                  </label>
                ))}
              </div>
            </>
          )}

          <button className="run" type="button" disabled={busy} onClick={onRender}>
            {busy ? <><span className="spinner" />Rendering…</>
              : `Render${nRestored || nFlipped ? ` with ${[
                  nRestored ? `${nRestored} restored cut${nRestored > 1 ? "s" : ""}` : "",
                  nFlipped ? `${nFlipped} camera change${nFlipped > 1 ? "s" : ""}` : "",
                ].filter(Boolean).join(", ")}` : " as planned"} →`}
          </button>
        </div>
      )}

      {result && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Result</h3>
          {r.filler_report && (
            <div className="stat-grid">
              <div className="stat"><b>{r.segments ?? "—"}</b><span>segments</span></div>
              <div className="stat"><b>{r.anticipation_cuts ?? 0}</b><span>anticipation cuts</span></div>
              <div className="stat"><b>{r.filler_report.removed_pct}%</b><span>removed</span></div>
              <div className="stat"><b>{r.sync_offset != null ? r.sync_offset.toFixed(2) + "s" : "—"}</b><span>cam sync</span></div>
            </div>
          )}
          <video src={result.download} controls />
          <p><a className="dl" href={result.download} download>⬇ Download final.mp4</a></p>
        </div>
      )}

      {logs && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Pipeline log</h3>
          <div className="log">{logs}</div>
        </div>
      )}
    </div>
  );
}
