import { NextResponse } from "next/server";
import { spawn } from "child_process";
import { mkdir, readFile } from "fs/promises";
import { existsSync } from "fs";
import path from "path";
import { jobPaths, FFMPEG_DIR } from "../engine";

export const runtime = "nodejs";
export const maxDuration = 120;

const MAX_PREVIEW_SECONDS = 4;

// Cut a small, cached, low-res snippet from an uploaded source so the review
// card can show what a segment/cut actually looks & sounds like — without
// waiting for (or committing to) the full render.
export async function GET(req) {
  const { searchParams } = new URL(req.url);
  const job = (searchParams.get("job") || "").replace(/[^a-z0-9]/gi, "");
  const camera = searchParams.get("camera") || "src";
  const start = Number(searchParams.get("start"));
  const end = Number(searchParams.get("end"));
  if (!job || !/^(cam1|cam2|src)$/.test(camera) ||
      !Number.isFinite(start) || !Number.isFinite(end) || end <= start)
    return NextResponse.json({ error: "Bad preview params." }, { status: 400 });

  const { jobDir, work } = jobPaths(job);
  let plan;
  try { plan = JSON.parse(await readFile(path.join(work, "plan.json"), "utf-8")); }
  catch { return NextResponse.json({ error: "No plan for this job." }, { status: 404 }); }

  // Source + time mapping: plan times live on the reference (cam1) timeline;
  // cam2's own clock is ref + sync offset (same mapping render.py uses).
  let src, offset = 0;
  if (plan.mode === "podcast") {
    src = camera === "cam2" ? plan.inputs.cam2 : plan.inputs.cam1;
    if (camera === "cam2") offset = plan.sync?.offset || 0;
  } else {
    src = plan.inputs.video;
  }
  if (!src || !existsSync(src))
    return NextResponse.json({ error: "Source footage not found." }, { status: 404 });

  const pad = 0.15;
  const ss = Math.max(0, start + offset - pad);
  const dur = Math.min(end - start + 2 * pad, MAX_PREVIEW_SECONDS);

  const prevDir = path.join(jobDir, "previews");
  await mkdir(prevDir, { recursive: true });
  const cachePath = path.join(prevDir,
    `${camera}_${Math.round(start * 1000)}_${Math.round(end * 1000)}.mp4`);

  if (!existsSync(cachePath)) {
    const env = { ...process.env };
    env.PATH = FFMPEG_DIR + path.delimiter + (env.PATH || "");
    const args = [
      "-y", "-hide_banner", "-loglevel", "error",
      "-ss", ss.toFixed(3), "-i", src, "-t", dur.toFixed(3),
      "-vf", "scale=-2:240,fps=15",
      "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30", "-pix_fmt", "yuv420p",
      "-c:a", "aac", "-b:a", "64k", "-ac", "1",
      "-movflags", "+faststart",
      cachePath,
    ];
    const { code, logs } = await new Promise((resolve) => {
      const proc = spawn("ffmpeg", args, { env });
      let logs = "";
      proc.stderr.on("data", (d) => (logs += d.toString()));
      proc.on("error", (err) => resolve({ code: -1, logs: logs + err.message }));
      proc.on("close", (code) => resolve({ code, logs }));
    });
    if (code !== 0)
      return NextResponse.json({ error: "Preview encode failed: " + logs.slice(-300) }, { status: 500 });
  }

  const data = await readFile(cachePath);
  return new NextResponse(data, {
    headers: {
      "Content-Type": "video/mp4",
      "Content-Length": String(data.length),
      "Cache-Control": "private, max-age=3600",
    },
  });
}
