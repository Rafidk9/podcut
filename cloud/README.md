# PodCut cloud UI

The hosted half of the remote control plane: a static single-page app for
queueing reel renders and watching them happen. The laptop does the rendering —
see [`worker/README.md`](../worker/README.md).

This is a **static export**. There is no server and no API routes: the browser
talks to Supabase directly for auth, data, live logs and signed download links.
That is what makes a 9-minute render possible on free hosting — nothing here has
a request timeout to exceed.

> Not to be confused with [`../web/`](../web), which is the local Next.js UI for
> the podcast / single-speaker engine and still runs on your own machine.

## Deploy (free, no card)

1. **Supabase** — create a free project, then run `supabase/schema.sql` in the
   SQL editor. Copy the project URL and the **anon** key from *Project settings →
   API*.
2. **Cloudflare Pages** — *Workers & Pages → Create → Pages → Connect to Git*,
   pick `Rafidk9/podcut`, and set:

   | Setting | Value |
   |---|---|
   | Build command | `npm install && npm run build` |
   | Build output directory | `out` |
   | Root directory | `cloud` |

   Add two environment variables (*Settings → Environment variables*), for both
   Production and Preview:

   ```
   NEXT_PUBLIC_SUPABASE_URL   = https://YOUR-REF.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY = eyJ...
   ```

3. **Allow your email to sign in.** In Supabase, *Authentication → URL
   Configuration*, add your Pages URL as a Site URL and redirect URL. The
   database only accepts the address hardcoded in `public.allowed_user()`.
4. **Start the worker** on the laptop. Until it does, the UI shows "laptop
   offline" and the reel list is empty — the catalog is published by the worker,
   not by this app.

## Local development

```bash
cd cloud
npm install
cp .env.example .env.local     # fill in URL + anon key
npm run dev                    # http://localhost:3100
```

## Security model

The anon key ships inside the bundle, which is fine and by design. Every table
has row-level security that checks the signed-in user's email against
`public.allowed_user()`, so the key alone grants nothing. A trigger further
restricts the browser to inserting jobs and requesting cancellation — it cannot
write the result columns the worker owns. The service-role key exists only in
`worker/.env` on the laptop.

## What this app can and can't see

It shows reel folder names, clip filenames and sizes, which config files exist,
log output, and the three deliverables. It has no access to raw footage,
transcripts, or the `work/` scratch — those never leave the laptop.
