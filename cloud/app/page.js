"use client";

import { useCallback, useEffect, useState } from "react";
import { supabase, configured } from "../lib/supabase";
import Auth from "../components/Auth";
import ReelList from "../components/ReelList";
import ReelDetail from "../components/ReelDetail";
import JobView from "../components/JobView";
import WorkerBadge from "../components/WorkerBadge";

function NotConfigured() {
  return (
    <div className="shell">
      <div className="note fail">
        <strong>Not configured.</strong> This build has no Supabase credentials.
        Set <code>NEXT_PUBLIC_SUPABASE_URL</code> and{" "}
        <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code> as build environment variables
        (locally in <code>cloud/.env.local</code>, on Cloudflare Pages under
        Settings → Environment variables) and redeploy.
      </div>
    </div>
  );
}

export default function Home() {
  const [session, setSession] = useState(undefined); // undefined = still checking
  const [reels, setReels] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [worker, setWorker] = useState(null);
  const [view, setView] = useState({ name: "list" });

  useEffect(() => {
    if (!configured) return;
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => sub.subscription.unsubscribe();
  }, []);

  const refresh = useCallback(async () => {
    const [r, j, w] = await Promise.all([
      supabase.from("reels").select("*").order("name", { ascending: false }),
      supabase.from("jobs").select("*").order("id", { ascending: false }).limit(40),
      supabase.from("worker_status").select("*").eq("id", 1).maybeSingle(),
    ]);
    if (r.data) setReels(r.data);
    if (j.data) setJobs(j.data);
    if (w.data) setWorker(w.data);
  }, []);

  useEffect(() => {
    if (!session) return;
    refresh();

    // Realtime keeps the catalog and queue live; the interval is a safety net
    // for a phone that slept through the websocket.
    const channel = supabase
      .channel("control-plane")
      .on("postgres_changes", { event: "*", schema: "public", table: "jobs" }, refresh)
      .on("postgres_changes", { event: "*", schema: "public", table: "reels" }, refresh)
      .on("postgres_changes", { event: "*", schema: "public", table: "worker_status" },
          (p) => setWorker(p.new))
      .subscribe();

    const poll = setInterval(refresh, 30_000);
    const onVisible = () => document.visibilityState === "visible" && refresh();
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      supabase.removeChannel(channel);
      clearInterval(poll);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [session, refresh]);

  if (!configured) return <NotConfigured />;
  if (session === undefined) {
    return <div className="shell"><div className="empty"><span className="spin" /></div></div>;
  }
  if (!session) return <Auth />;

  // Views hold an id so realtime updates flow through, but a job queued a
  // moment ago isn't in `jobs` until the next refresh lands -- fall back to the
  // row the insert returned so the log opens immediately.
  const openReel = reels.find((r) => r.name === view.reel);
  const openJob = jobs.find((j) => j.id === view.job) || view.jobRow;

  return (
    <div className="shell">
      <header className="topbar">
        <button className="wordmark" onClick={() => setView({ name: "list" })}>
          <span className="dot" />
          PodCut
        </button>
        <span className="spacer" />
        <WorkerBadge worker={worker} />
      </header>

      {view.name === "job" && openJob ? (
        <JobView job={openJob} onBack={() => setView(
          openJob.reel ? { name: "reel", reel: openJob.reel } : { name: "list" })} />
      ) : view.name === "reel" && openReel ? (
        <ReelDetail
          reel={openReel}
          worker={worker}
          jobs={jobs}
          onBack={() => setView({ name: "list" })}
          onOpenJob={(j) => { refresh(); setView({ name: "job", job: j.id, jobRow: j }); }}
        />
      ) : (
        <ReelList
          reels={reels}
          jobs={jobs}
          onOpenReel={(r) => setView({ name: "reel", reel: r.name })}
          onOpenJob={(j) => setView({ name: "job", job: j.id, jobRow: j })}
        />
      )}

      <div style={{ marginTop: 40, textAlign: "center" }}>
        <button className="back" onClick={() => supabase.auth.signOut()}>Sign out</button>
      </div>
    </div>
  );
}
