// Shared engine-invocation helpers for the API routes.
import { spawn } from "child_process";
import path from "path";

export const ENGINE = path.resolve(process.cwd(), "..", "engine");
export const PY = process.platform === "win32"
  ? path.join(ENGINE, ".venv", "Scripts", "python.exe")
  : path.join(ENGINE, ".venv", "bin", "python");

// ffmpeg dir (winget install location); override with FFMPEG_DIR env.
export const FFMPEG_DIR = process.env.FFMPEG_DIR ||
  path.join(process.env.LOCALAPPDATA || "", "Microsoft", "WinGet", "Packages",
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe",
    "ffmpeg-8.1.2-full_build", "bin");

export function jobPaths(jobId) {
  const jobDir = path.join(ENGINE, ".podcut_jobs", jobId);
  return { jobDir, work: path.join(jobDir, "work"), out: path.join(jobDir, "final.mp4") };
}

export function runEngine(args) {
  const env = { ...process.env };
  env.PATH = FFMPEG_DIR + path.delimiter + (env.PATH || "");
  return new Promise((resolve) => {
    const proc = spawn(PY, args, { cwd: ENGINE, env });
    let logs = "";
    proc.stdout.on("data", (d) => (logs += d.toString()));
    proc.stderr.on("data", (d) => (logs += d.toString()));
    proc.on("error", (err) => resolve({ code: -1, logs: logs + "\n[spawn error] " + err.message }));
    proc.on("close", (code) => resolve({ code, logs }));
  });
}
