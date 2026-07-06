import { NextResponse } from "next/server";
import { writeFile, readFile } from "fs/promises";
import path from "path";
import { jobPaths, runEngine } from "../engine";

export const runtime = "nodejs";
export const maxDuration = 600;

// Phase 2 of the review flow: persist the (possibly edited) plan and render it.
export async function POST(req) {
  const { jobId, plan } = await req.json();
  if (!jobId || !/^[a-z0-9]+$/.test(jobId))
    return NextResponse.json({ ok: false, error: "Bad job id." }, { status: 400 });
  if (!plan || typeof plan !== "object")
    return NextResponse.json({ ok: false, error: "Missing plan." }, { status: 400 });

  const { work } = jobPaths(jobId);
  await writeFile(path.join(work, "plan.json"), JSON.stringify(plan, null, 2));

  const result = await runEngine(["-m", "podcut", "render-plan", "--workdir", work]);

  let report = null;
  try { report = JSON.parse(await readFile(path.join(work, "report.json"), "utf-8")); } catch {}

  const outputFile = report?.output ? path.basename(report.output) : "final.mp4";
  return NextResponse.json({
    ok: result.code === 0,
    error: result.code === 0 ? undefined : "Render exited with code " + result.code,
    jobId,
    report,
    logs: result.logs,
    download: `/api/download?job=${jobId}&file=${encodeURIComponent(outputFile)}`,
  });
}
