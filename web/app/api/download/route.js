import { NextResponse } from "next/server";
import { readFile } from "fs/promises";
import path from "path";

export const runtime = "nodejs";

const ENGINE = path.resolve(process.cwd(), "..", "engine");

export async function GET(req) {
  const { searchParams } = new URL(req.url);
  const job = (searchParams.get("job") || "").replace(/[^a-z0-9]/gi, "");
  const file = path.basename(searchParams.get("file") || "final.mp4");
  const p = path.join(ENGINE, ".podcut_jobs", job, file);
  try {
    const data = await readFile(p);
    return new NextResponse(data, {
      headers: {
        "Content-Type": "video/mp4",
        "Content-Length": String(data.length),
        "Content-Disposition": `inline; filename="${file}"`,
      },
    });
  } catch {
    return NextResponse.json({ error: "Output not found." }, { status: 404 });
  }
}
