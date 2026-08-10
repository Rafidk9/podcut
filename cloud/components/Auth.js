"use client";

import { useState } from "react";
import { supabase } from "../lib/supabase";

export default function Auth() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState("idle"); // idle | sending | sent | error
  const [error, setError] = useState("");

  async function send(e) {
    e.preventDefault();
    setState("sending");
    setError("");
    const { error } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: { emailRedirectTo: window.location.origin },
    });
    if (error) {
      setError(error.message);
      setState("error");
    } else {
      setState("sent");
    }
  }

  if (state === "sent") {
    return (
      <div className="auth">
        <h1>Check your email</h1>
        <p>
          A sign-in link is on its way to <strong>{email}</strong>. Open it on this
          device and you&apos;ll land straight back here.
        </p>
        <button className="btn wide" onClick={() => setState("idle")}>
          Use a different address
        </button>
      </div>
    );
  }

  return (
    <div className="auth">
      <h1>PodCut</h1>
      <p>
        Queue and watch reel renders from anywhere. The rendering happens on your
        laptop — nothing here can start without it.
      </p>
      <form onSubmit={send}>
        <input
          type="email"
          required
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <button className="btn primary wide" disabled={state === "sending"}>
          {state === "sending" ? "Sending…" : "Email me a sign-in link"}
        </button>
      </form>
      {error && <p style={{ color: "var(--fail)", marginTop: 14 }}>{error}</p>}
    </div>
  );
}
