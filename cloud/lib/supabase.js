"use client";

import { createClient } from "@supabase/supabase-js";

// Baked in at build time by Cloudflare Pages. The anon key is safe to ship --
// every table is behind row-level security that checks the signed-in email
// against public.allowed_user(). The service key never comes near this app;
// only the laptop worker holds it.
const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const configured = Boolean(url && anonKey);

export const supabase = configured
  ? createClient(url, anonKey, {
      auth: { persistSession: true, detectSessionInUrl: true, autoRefreshToken: true },
    })
  : null;

export const BUCKET = "deliverables";

/** Short-lived download link for a deliverable. The bucket is private. */
export async function signedUrl(path, seconds = 3600) {
  const { data, error } = await supabase.storage
    .from(BUCKET)
    .createSignedUrl(path, seconds);
  if (error) throw error;
  return data.signedUrl;
}
