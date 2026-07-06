import { NextResponse } from "next/server";
import { mkdir, writeFile, readFile } from "fs/promises";
import path from "path";
import { jobPaths, runEngine } from "../engine";

export const runtime = "nodejs";
export const maxDuration = 600;

function extOf(f) {
  if (f && f.name) { const e = path.extname(f.name); return e || ".mp4"; }
  return ".mp4";
}

async function saveFile(form, field, destDir, baseName) {
  const f = form.get(field);
  if (!f || typeof f === "string") return null;
  const buf = Buffer.from(await f.arrayBuffer());
  const p = path.join(destDir, baseName + extOf(f));
  await writeFile(p, buf);
  return p;
}

export async function POST(req) {
  const form = await req.formData();
  const mode = form.get("mode") || "podcast";
  // review=true runs analysis only (`plan` subcommand) and returns the cut
  // list for the user to tweak; /api/render-plan finishes the job.
  const review = form.get("review") === "true";
  const jobId = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  const { jobDir, work, out } = jobPaths(jobId);
  await mkdir(jobDir, { recursive: true });

  let args;
  try {
    if (mode === "podcast") {
      const cam1 = await saveFile(form, "cam1", jobDir, "cam1");
      const cam2 = await saveFile(form, "cam2", jobDir, "cam2");
      if (!cam1 || !cam2)
        return NextResponse.json({ ok: false, error: "Both camera files are required." }, { status: 400 });
      args = review
        ? ["-m", "podcut", "plan", "--cam1", cam1, "--cam2", cam2, "--out", out, "--workdir", work]
        : ["-m", "podcut", "podcast", "--cam1", cam1, "--cam2", cam2, "--out", out, "--workdir", work];
    } else {
      const video = await saveFile(form, "video", jobDir, "video");
      if (!video)
        return NextResponse.json({ ok: false, error: "A video file is required." }, { status: 400 });
      args = review
        ? ["-m", "podcut", "plan", "--video", video, "--out", out, "--workdir", work]
        : ["-m", "podcut", "single", "--video", video, "--out", out, "--workdir", work];
    }
    const transcript = await saveFile(form, "transcript", jobDir, "transcript");
    if (transcript) args.push("--transcript", transcript);
    if (form.get("noFillers") === "true") args.push("--no-fillers");
    if (form.get("noSilence") === "true") args.push("--no-silence");
    const speakerA = (form.get("speakerA") || "").toString().trim();
    const speakerB = (form.get("speakerB") || "").toString().trim();
    if (speakerA) args.push("--speaker-a", speakerA);
    if (speakerB) args.push("--speaker-b", speakerB);
    // Captions on by default (ffmpeg burn, or HyperFrames if HYPERFRAMES_PATH set).
    // video-use is an interactive handoff, so skip it from the web flow.
    args.push("--no-video-use");
    if (form.get("noCaptions") === "true") args.push("--no-hyperframes");
  } catch (e) {
    return NextResponse.json({ ok: false, error: "Upload failed: " + String(e) }, { status: 500 });
  }

  const result = await runEngine(args);

  if (review) {
    let plan = null;
    try { plan = JSON.parse(await readFile(path.join(work, "plan.json"), "utf-8")); } catch {}
    return NextResponse.json({
      ok: result.code === 0 && !!plan,
      error: result.code === 0 ? undefined : "Plan step exited with code " + result.code,
      jobId,
      plan,
      logs: result.logs,
    });
  }

  let report = null;
  try { report = JSON.parse(await readFile(path.join(work, "report.json"), "utf-8")); } catch {}

  const outputFile = report?.output ? path.basename(report.output) : "final.mp4";
  return NextResponse.json({
    ok: result.code === 0,
    error: result.code === 0 ? undefined : "Pipeline exited with code " + result.code,
    jobId,
    report,
    logs: result.logs,
    download: `/api/download?job=${jobId}&file=${encodeURIComponent(outputFile)}`,
  });
}
