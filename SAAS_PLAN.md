# ReelKit — AI Branded-Reel SaaS: Build Plan

> **What this document is:** a build-ready specification for turning the PFEC reel
> pipeline (`podcut/reels/`) + PodCut engine learnings into a multi-tenant SaaS.
> It is structured as sequential, session-sized milestones (M0–M10), each written
> as a self-contained brief with acceptance criteria, so Claude (Sonnet 5 in
> Claude Code) can execute them one at a time. Paste one milestone per session,
> along with the "Standing context" block below.
>
> Working name "ReelKit" — placeholder, rename freely.

---

## 0. Product definition

**One-liner:** Upload raw talking-head phone footage → get back a fully branded,
compliance-checked vertical reel (captions, B-roll, overlay cards, end cards,
music, social caption text) in minutes — locked to YOUR brand system, not a
generic template.

**Wedge / differentiation (why this wins vs Opus Clip / Submagic / Captions):**
1. **Brand-locked output.** Competitors give generic captions with a font picker.
   ReelKit encodes an agency's ENTIRE editing standard (composite order, card
   grammar, motion language, music rules, loudness targets) as a "Brand Kit" —
   every reel is on-brand without a designer touching it.
2. **Compliance engine.** For regulated verticals (migration agents, finance,
   health), the system enforces rules a human editor forgets: who may speak on
   which topics, mandatory disclaimers, credential banners. The PFEC pipeline
   already caught a real violation (an Education Counsellor fronting a PR-topic
   video) that a human team had shipped to "finished". That story is the pitch.
3. **Review checkpoint, not black box.** The PodCut plan→review→render pattern:
   the AI proposes the full edit (cuts, B-roll spots, card timings) as an
   editable plan BEFORE any render. Users trust what they can veto.

**Personas:**
- P1 — Marketing lead at a multi-office agency (PFEC itself = design partner /
  first customer). Needs volume, consistency, compliance.
- P2 — Social media freelancer/agency serving several regulated-industry clients.
  Needs multiple brand kits + white label.
- P3 — Developer at a marketing platform. Wants the API only.

**Core design principle (carried over from PodCut — do not violate):**
> The AI annotates structure (topics, key phrases, connecting phrases, speaker
> roles). A **deterministic engine** converts annotations into timings, cuts and
> card placements. **The LLM never emits raw timecodes.**

---

## 1. Architecture

```
apps/
  web/          Next.js 14 app — dashboard, upload, review UI, brand kit editor
  api/          Public REST API (same Next.js app, /api/v1/*, key-authenticated)
services/
  planner/      Python (FastAPI worker) — transcribe → annotate → editorial plan
  renderer/     Node worker — HyperFrames + ffmpeg, consumes render jobs
  compliance/   Python — topic gate, disclaimer/credential checks (runs inside planner)
packages/
  brandkit/     JSON-schema types + validators for Brand Kits & Compliance Packs
infra/
  queue         Postgres-backed job queue to start (SKIP Redis/SQS until scale);
                jobs table + FOR UPDATE SKIP LOCKED polling
  storage       S3-compatible (R2 recommended: zero egress fees — video product!)
  db            Postgres (Neon/Supabase) — tenants, jobs, plans, ledger
  billing       Stripe (subscriptions + metered credits)
```

**Key decisions (already made — don't relitigate in build sessions):**
- Monorepo (pnpm workspaces + a `services/` python dir with uv).
- Render workers are plain VMs/containers with Chrome-headless-shell + ffmpeg,
  pulling from the queue. HyperFrames Lambda (`hyperframes lambda`) is the
  scale-out path later — the worker interface must not assume local rendering.
- All AI calls behind one internal `ai/` module with per-tenant metering hooks.
  Models: Claude Sonnet 5 (`claude-sonnet-5`) for editorial planning & caption
  text; Haiku 4.5 for cheap classification (topic gate pre-check, ASR fixes).
- Transcription: ElevenLabs Scribe primary, faster-whisper self-hosted fallback
  (the PodCut provider-fallback pattern, engine/podcut/transcribe.py).
- Every ffmpeg encode in the platform ships the HDR discipline learned twice in
  this codebase: probe input colour; tone-map HDR (PQ/HLG/BT.2020) via the
  zscale/tonemap chain with explicit tin/min/pin; stamp frames with `setparams`
  AND pass `-color_*` flags; ffprobe-verify bt709/tv on output as a pipeline
  gate (a failed colour check fails the job). Port `engine/podcut/render.py`'s
  `hdr_to_sdr_vf()` + `ffutil.probe_color/is_hdr` as the shared library.
- Transparent overlay webms are ALWAYS decoded with `-c:v libvpx-vp9` (default
  decoder silently drops alpha).

---

## 2. Data model (Postgres)

```
tenants        id, name, plan, stripe_customer_id, created_at
users          id, tenant_id, email, role (owner|editor|viewer)
api_keys       id, tenant_id, key_hash, label, scopes, last_used_at
brand_kits     id, tenant_id, name, version, json (validated against schema §3)
compliance_packs id, tenant_id, name, version, json (schema §4)
speakers       id, tenant_id, name, role_title, credentials jsonb
               (e.g. {"type":"MARN","value":"2117037"}), allowed_topics text[]
projects       id, tenant_id, brand_kit_id, compliance_pack_id, title, status
assets         id, project_id, kind (raw_clip|logo|endcard|music|document),
               s3_key, probe jsonb (dims/fps/colour/duration), status
jobs           id, project_id, kind (transcribe|plan|render|preview), status
               (queued|running|succeeded|failed), worker_id, error, timings jsonb
plans          id, project_id, version, json (the editable edit plan §5),
               approved_by, approved_at
renders        id, project_id, plan_version, s3_key, duration, qc jsonb
               (colour tags, loudness, frame-check results)
credit_ledger  id, tenant_id, delta, reason (subscription_grant|purchase|
               render|transcribe_min|ai_tokens|refund), job_id, created_at
usage_events   id, tenant_id, metric (scribe_seconds|llm_in_tokens|llm_out_tokens|
               render_seconds), qty, job_id, created_at   -- raw metering
```

Rules: every AI/render action writes `usage_events` (raw truth) AND a
`credit_ledger` row (billing truth). Ledger is append-only; balance = SUM(delta).

---

## 3. Brand Kit schema — PFEC is the seed row

The Brand Kit is the productized "DNA". PFEC's kit ships as the reference
implementation and the demo tenant. Schema (JSON, versioned):

```jsonc
{
  "format": { "w": 1080, "h": 1920, "fps": 30 },
  "colors": {
    "primary":  "#100796",   // PFEC dark blue
    "cta":      "#E84B37",   // passion red — CTAs/urgency ONLY
    "info":     "#00B3E3",   // links/info blocks
    "accent":   "#FFC500",   // gold — keywords, credential banner
    "success":  "#31EB7C",
    "bg":       "#FDFDFD"
  },
  "typography": { "family": "Poppins", "weights": [700, 800, 900] },
  "logo": {
    "asset": "logo_chip.png",
    "placement": "top-center", "width_pct": 40, "top_margin_pct": 2,
    "variants": { "on_dark": "logo_white.png" },
    "rules": ["never stretch", "never recolor beyond variants", "never rotate"]
  },
  "captions": {
    "grammar": "two_word_uppercase",       // 2-word chunks, sentence-end breaks
    "position": { "anchor": "center", "y_pct": 62 },
    "font_size": 96, "bottom_safe_px": 90,
    "keyword_style": { "color": "accent", "pulse_scale": 1.08 },
    "keywords": ["VISA","EOI","IELTS","PTE","NAATI","189","POINTS","PR",
                 "RESIDENCY","PERMANENT","PATHWAY","MIGRATION","SEMINAR",
                 "ASSESSMENT","INVITATION","ROUND"],   // per-kit, LLM may propose additions for approval
    "drop_fillers": true,
    "asr_fixes": { "pfc": "PFEC", "pfpc": "PFEC", "ils": "IELTS" },
    "spoken_vs_designed": "captions verbatim as spoken; designed cards use corrected/official names"
  },
  "cards": {
    "max_bottom_slots": 2, "bottom_zone_px": [1360, 1420],
    "exit_rule": "card exits when its topic ends",
    "cta": { "shape": "pill", "bg": "cta", "default_text": "BOOK A FREE CONSULTATION" },
    "name_lower_third": { "bg": "primary", "bar": "accent", "pos": "bottom-left",
                          "window_s": [0.6, 4.8] }
  },
  "broll": {
    "placement_rule": "only over connecting/filler phrases, NEVER over key information",
    "count_rule": "AI-judged from the script: one candidate per genuine connecting/filler span found in the transcript, scaled to video length — NOT a fixed count. A reel with few/no such spans gets few/zero B-roll cuts.",
    "context_rule": "each stinger's concept/copy must be specific to what THIS speaker is saying at THAT anchor phrase in THIS reel — no generic filler, no reuse of another project's stingers as a silent fallback",
    "audio_rule": "B-roll replaces VIDEO only; speech audio continuous underneath",
    "style": "topical designed stingers (HyperFrames), not stock; brand-only content at most once",
    "banned_imagery": ["sydney scenery"],       // per-kit override list
    "transition": "brand-navy grid wipe"
  },
  "audio": {
    "music_mood": ["corporate", "uplifting", "bright"],  "music_banned": ["cutesy"],
    "music_bed": { "base_volume": 0.05, "sidechain": { "threshold": 0.04, "ratio": 10, "attack": 40, "release": 450 } },
    "fades": { "in_s": 1.5, "out_s": 2.4 },
    "loudnorm": { "i": -14, "tp": -1, "two_pass": true }
  },
  "ending": [ { "card": "disclaimer", "s": 3 }, { "card": "consultation", "s": 3 } ],
  "caption_txt_structure": [
    "bold_unicode_title_hook", "news_paragraphs", "what_you_should_know_bullets",
    "urgency_line_📌", "contact_cta_with_credential_📲", "office_address_block",
    "website_line_🌏", "hashtags_#askPFEC", "music_credit_if_ccby", "verbatim_disclaimer"
  ]
}
```

## 4. Compliance Pack schema — the moat

```jsonc
{
  "name": "AU migration agency (MARA)",
  "topic_rules": [
    {
      "topics": ["visa", "PR", "pathway advice", "points", "EOI", "grants"],
      "allowed_speaker_credential": "MARN",
      "on_violation": "block_render",   // hard gate; owner can override WITH logged acknowledgement
      "message": "Education Counsellors never speak on visa/PR topics — Registered Migration Agents only."
    }
  ],
  "required_elements": [
    { "when": "speaker_has_credential:MARN",
      "element": "credential_banner",   // gold MARA lower-third w/ correct MARN
      "rule": "visible while that agent speaks" },
    { "always": true, "element": "disclaimer_endcard", "verbatim_asset": "disclaimer_v1" },
    { "always": true, "element": "disclaimer_in_caption_txt", "verbatim_asset": "disclaimer_v1" },
    { "when": "music_license:CC-BY", "element": "music_credit_line" }
  ],
  "verbatim_assets": {
    "disclaimer_v1": "Disclaimer: The information shared by PFEC Global – Education | Migration is intended for general awareness only... [FULL VERBATIM TEXT — en-dashes and 'does not assure' exactly as written; store byte-exact, never let the LLM paraphrase]"
  },
  "credential_registry": "speakers table",   // e.g. Ali Ehsan MARN 2117037, Nic Soltani 1387104, Tushar Chopra 2418420, Kapil Kamar 2418610
  "pii_rules": {
    "documents_on_screen": "must pass redaction review; auto-detect name/DOB/passport/TRN fields; block until owner approves the redacted frame"
  }
}
```

**Compliance flow:** planner classifies reel topics (Haiku pre-check, Sonnet
confirm) → joins against speaker credentials → violations attach to the PLAN
(not the render) so the user sees them at review time → `block_render`
violations disable the render button; owner-role override writes an audit row.

---

## 5. The Edit Plan (the product's heart)

Direct generalization of PodCut's `plan.json` + the reels pipeline's hand-made
decisions, produced automatically:

```jsonc
{
  "version": 3,
  "source": { "clips": [...], "transcript": "s3://.../assembled.transcript.json" },
  "trims": [ { "clip": "IMG_6897", "keep": [0.9, 9.1], "reason": "trailing filler dropped" } ],
  "captions": { "cards": [...], "keywords_detected": ["PR","PATHWAY"] },
  "broll": [
    { "at": 8.19, "concept": "wrong-path warning / diverging roads",
      "anchor_phrase": "choosing the wrong course can cost you lots",
      "rationale": "connecting phrase; illustrates the stake being spoken" }
  ],
  "cards": [
    { "kind": "name_lower_third", "speaker_id": "...", "window": [0.6, 4.8] },
    { "kind": "info", "window": [40.2, 43.5], "content": { "kicker": "FREE MIGRATION SEMINAR", "date": "13 JULY", "venue": "Lakemba Senior Citizens' Centre" },
      "anchor_phrase": "seminar on 13th of July" },
    { "kind": "cta", "window": [48.75, 50.75], "text": "REGISTER NOW!",
      "anchor_phrase": "Link in below to register" }
  ],
  "document_highlights": [   // the visa-grant-letter feature
    { "asset_id": "...", "window": [22.0, 27.5], "anchor_phrase": "his 189 grant came through",
      "redactions": [ {"bbox": [x,y,w,h], "field": "passport_no"} ], "redaction_approved": false }
  ],
  "music": { "track_id": "...", "license": "CC-BY", "credit": "Funky Chunk — Kevin MacLeod (incompetech.com)" },
  "compliance": { "violations": [...], "acknowledged_by": null },
  "user_edits": { ... }      // same restore/override grammar as PodCut plan.json
}
```

**Review UI = PodCut's review checkpoint, upgraded:** every row has a ▶ preview
(reuse the lazy 240p snippet pattern from `web/app/api/preview/route.js`);
B-roll concepts show a rendered thumbnail; compliance violations render as
red blocking banners; approve → render.

**Anchor-phrase timing:** the LLM outputs `anchor_phrase` (words, not times);
the deterministic engine locates the phrase in the word-timestamped transcript
and computes the window (PodCut principle). If the phrase isn't found verbatim,
fuzzy-match ≥0.8 or flag for human placement — never guess a number.

---

## 6. Public API (v1) — the "API usage system"

Auth: `Authorization: Bearer rk_live_...` per-tenant keys, scoped.

```
POST /v1/projects                        create project (brand_kit_id, compliance_pack_id)
POST /v1/projects/:id/assets             presigned upload URLs (clips, docs, logos)
POST /v1/projects/:id/plan               run the AI planner        [meters: scribe+llm]
GET  /v1/projects/:id/plan               fetch plan (incl. violations)
PATCH /v1/projects/:id/plan              apply edits (same grammar as UI)
POST /v1/projects/:id/render             render approved plan       [meters: render+llm]
GET  /v1/renders/:id                     status + download URL + QC report
POST /v1/webhooks                        register (plan.ready, render.succeeded,
                                         render.failed, compliance.violation)
GET  /v1/usage?from=&to=                 metered usage + credit balance
```

Semantics: `plan` and `render` are async → 202 + job id; webhooks or polling.
Renders are idempotent per (project, plan_version). Compliance violations with
`block_render` return 409 from `/render` unless plan carries a logged override.

---

## 7. Pricing (see chat summary for rationale; implement exactly this)

**Credit system:** 1 credit = $0.10 face value. Metered debits:
| Action | Credits |
|---|---|
| Transcription | 2 / raw-footage-minute |
| AI plan (full editorial pass) | 8 flat |
| Plan revision (re-plan after edits) | 2 |
| Render (≤75s output, standard) | 25 |
| Preview window render (draft) | 3 |
| caption.txt generation | 2 |
| Document redaction assist | 4 / document |

Typical reel ≈ 10 min footage + 1 plan + 2 revisions + 1 preview + 1.3 renders
≈ **70 credits ≈ $7 retail** (COGS ≈ $1.2–1.8 → ~75% gross margin).

**Plans:**
| Tier | Price | Included credits | ≈ reels | Extras |
|---|---|---|---|---|
| Trial | $0 | 100 one-time | ~1–2 (watermarked, 720p) | 1 brand kit |
| Creator | $49/mo | 700 | ~10 | 1 brand kit, 2 seats |
| Agency | $149/mo | 2,800 | ~40 | 5 brand kits, compliance packs, API, webhooks, 10 seats |
| Scale | $499/mo | 12,000 | ~170 | white label, SSO, priority queue, custom packs |
| API pay-as-you-go | $0 base | buy packs: $50→500cr, $200→2,200cr, $1k→12,000cr | — | requires card on file |

Overage: auto-buy next credit pack (opt-in) or hard stop. Credits expire after
12 months (grants) / never (purchased). Stripe: subscription + metered credits
as invoice items; ledger in our DB is the source of truth, Stripe mirrors it.

---

## 8. Render pipeline requirements (non-negotiable QC gates)

Port these as automated gates — each failed gate fails the job with a typed error:
1. **Colour:** every output must ffprobe as bt709/bt709/bt709/tv. HDR inputs
   get the zscale/tonemap chain (explicit input params from probe); every
   libx264 encode carries `setparams` vf + `-color_*` flags.
2. **Alpha:** overlay webms decoded with `-c:v libvpx-vp9`, verified alpha
   present (pix_fmt yuva420p) before compositing.
3. **Loudness:** two-pass loudnorm to kit target; measured output within ±0.5 LU.
4. **Sync audit:** captions must use the EDITED-timeline transcript
   (remap-through-EDL, PodCut `remap_transcript_to_edit`); automated check:
   sample 5 caption cards, verify word midpoint falls inside card window.
5. **Frame checks:** extract frames at each card window midpoint + each B-roll
   boundary; run cheap vision QC (Haiku): "is the expected element visible and
   not overlapping captions?" — failures attach screenshots to the QC report.
6. **Duration invariant:** B-roll insertion must not change duration (audio
   continuity rule); assert output duration == base duration ± 1 frame.

---

## 9. Security / privacy

- Tenant isolation at the storage-prefix and DB-row level (RLS if Supabase).
- API keys hashed (argon2); scoped; rotatable; last-used tracking.
- Uploaded documents (grant letters!) are PII: encrypted at rest, auto-purge
  raw documents 30 days after project completion, redaction approval required
  before any document appears in a render.
- All provider keys (Anthropic, ElevenLabs, Stripe) in a secrets manager,
  never in repo/.env committed. Per-tenant AI spend caps.
- Verbatim compliance texts are byte-exact assets, checksummed; renders record
  the checksum used (audit trail for regulators).

---

## 10. Build milestones (one Claude Code session each)

> **Standing context to paste with every milestone:** this file, plus:
> "Reference implementations live in this repo: `podcut/reels/` (the PFEC
> pipeline — captions/B-roll/composite/compliance DNA), `podcut/engine/`
> (plan→review→render checkpoint, HDR-safe render.py, provider fallbacks,
> transcript remapping), `podcut/web/` (review UI + lazy preview route).
> Port patterns, don't rewrite blindly. Verify like this repo verifies:
> ffprobe colour tags, extracted frames, real end-to-end runs — never pixel
> diffs alone, never 'it compiles'."

- **M0 — Monorepo scaffold.** pnpm workspaces (`apps/web`, `packages/brandkit`),
  `services/planner` (FastAPI+uv), `services/renderer` (Node), Postgres schema
  §2 as migrations, S3/R2 + presigned uploads, job queue (SKIP LOCKED), CI.
  ✅: `pnpm test` green; enqueue a no-op job → worker claims → succeeds.
- **M1 — Brand Kit + Compliance Pack packages.** JSON schemas §3/§4 +
  validators + versioning; seed the full PFEC kit and MARA pack as fixtures
  (copy every value from §3/§4 — this is the DNA transplant). ✅: fixtures
  validate; snapshot tests lock the verbatim disclaimer byte-exact.
- **M2 — Ingest + transcription service.** Upload → probe (dims/fps/COLOUR) →
  Scribe with faster-whisper fallback → per-clip word transcripts → assembled
  transcript with trailing-filler trims (port `build_base.py` logic, incl. the
  HDR tone-map VF chain + colour gates §8.1). ✅: 9-clip PFEC input set
  reproduces today's assembled transcript ±50ms; colour gate passes.
- **M3 — Editorial planner.** Sonnet 5 annotation → Edit Plan §5. Anchor-phrase
  grammar, deterministic phrase→time resolution, keyword detection constrained
  to kit list + proposals, B-roll concept selection (topical, placement rule),
  card content extraction (dates/venues → designed-card corrected text vs
  as-spoken captions). ✅: on the Lakemba transcript, planner independently
  places B-roll within ±1.5s of the 4 hand-chosen spots and drafts date/CTA
  cards on the right phrases.
- **M4 — Compliance engine.** Topic classification, credential join, violation
  attachment, override audit trail, required-elements checklist (credential
  banner, disclaimer cards, music credit). ✅: the real Niyama case blocks with
  the exact rule message; adding a MARN speaker to the same transcript unblocks
  and requires the banner element.
- **M5 — Renderer service.** HyperFrames composition generator driven ENTIRELY
  by (Brand Kit + Edit Plan): captions block, card system (kicker/date/venue,
  CTA pill, name lower-third), grid-wipe B-roll inserts, end-card concat,
  music bed with sidechain ducking, loudnorm — port `build_captions.py` /
  `insert_broll.py` / `build_composite.py` into kit-parameterized templates.
  All §8 QC gates automated. ✅: rendering the seeded PFEC kit + a plan
  reproducing today's Lakemba plan yields a reel whose extracted frames match
  the current `reel_final.mp4` at the 7 landmark timestamps.
- **M6 — Review UI.** Plan viewer/editor (port PodCut review card): per-row ▶
  previews (lazy 240p route), card text editing, B-roll concept swap,
  compliance banners with override flow, approve→render. ✅: browser-driven
  e2e (like this repo's preview_eval verifications) covering edit→persist→
  render round-trip.
- **M7 — Billing + metering.** usage_events on every AI/render call, credit
  ledger, Stripe subscription + packs, hard caps, `/v1/usage`. ✅: ledger
  balance equals Stripe invoice preview across a scripted month of usage.
- **M8 — Public API + webhooks.** §6 endpoints, key auth, idempotency, 409
  compliance semantics, webhook delivery with retries + signatures. ✅: a
  script drives clip→plan→render purely via API and downloads the reel.
- **M9 — caption.txt + document highlights.** 10-part caption generator
  (kit-driven, verbatim disclaimer injection); grant-letter feature: PDF page →
  image, PII field detection, redaction boxes, approval gate, designed
  "paper card + stamp" render treatment. ✅: caption.txt matches structure
  fixture; a sample letter renders with masked fields only after approval.
- **M10 — Hardening for launch.** Render farm autoscale (or HyperFrames
  Lambda), rate limits, tenant spend caps, observability (per-stage job
  timings — the pipeline already records these), status page, data-retention
  jobs, pen-test checklist from §9.

**Sequencing note:** M2+M3+M5 make a demo (plan+render for the design partner);
M4 makes the pitch; M6 makes it trustworthy; M7+M8 make it a business. Don't
polish M10 before a design partner ships 20 real reels through M6.

---

## 11. Open questions for the owner (decide before M7)

1. Name + domain. ("ReelKit" is a placeholder.)
2. Legal entity/liability wording for the compliance feature — it must be
   marketed as "compliance ASSISTANCE", not legal advice; ToS language needed.
3. Music licensing beyond CC-BY (budget a library like Artlist/Epidemic at
   Agency tier?).
4. PFEC's role: internal tool, design partner with a discount, or co-marketing
   case study? (The Niyama catch is a great case study — with their consent.)
5. Watermark design for trial tier.
