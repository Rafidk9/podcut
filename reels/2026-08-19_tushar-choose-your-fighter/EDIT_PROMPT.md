# Edit Prompt — "Choose Your Fighter" (Tushar, PFEC Global)

A reusable brief for cutting a vertical reel in the **Choose Your Fighter / game
character-select** meme format. Written against the actual footage in
`input/` — every timecode below is measured from the ElevenLabs word-level
transcripts in `work/*.transcript.json`, not estimated.

---

## 1. The format, in one line

A game-select screen offers four migration pathways. The viewer is invited to
pick one. **Every pick is wrong** — because the right pathway is a function of
*your* situation, not a menu item. The reel weaponises the meme's own logic
against itself: the X lands on **all four cards at once**, not on the one you
chose.

That inversion is the whole creative. Anything in the edit that undercuts it
(X-ing only the selected card, letting one option look like the "winner",
ranking the options) is wrong and should be rejected.

---

## 2. Source inventory

Four takes, iPhone 4K60 HDR (HLG / BT.2020), portrait via `rotation=-90`.
Each opens with an off-mic self-slate that must be trimmed.

| Clip | Raw dur | Framing | Slate ends | Line starts | **Keep** | Spoken line |
|---|---|---|---|---|---|---|
| `IMG_8192` | 4.40s | Close-up, gesturing, lobby | 0.639 | 1.279 | **1.05 – 3.30** | "Pick one. … Wrong." |
| `IMG_8195` | 7.01s | Seated at desk, calm, steel backdrop | 1.279 | 1.819 | **1.60 – 6.40** | "There's no best option, but there's only one that fits your situation" |
| `IMG_8196` | 3.52s | Seated, animated, both hands up | 0.939 | 0.959 | **0.90 – 3.22** | "And guessing wrong could cost you months" |
| `IMG_8197` | 6.04s | Wide, standing in corridor, full body | 1.779 | 2.399 | **2.15 – 5.65** | "Comment your pick and I'll tell you if it's actually right for you" |

**Trim gotcha — `IMG_8196`.** The transcript puts the slate's "go" ending at
0.939 and "And" starting at 0.959: a 20 ms gap that is not cuttable. A 20 ms
RMS envelope over the audio shows the real picture — the slate runs 0.60–0.74
at −33 dB, then genuine silence 0.76–0.93 at −48…−53 dB, then "And" attacks at
0.94. **Cut at 0.90**, which lands in the measured silence with ~40 ms of
lead-in. Do not trust the word boundary here; measure the envelope.

The other three gaps are 540–640 ms and cut anywhere.

**Two useful internal beats — keep them, they are not dead air:**
- `IMG_8192`: 0.92s of silence between "one." (1.740) and "Wrong" (2.659).
  This is where the cursor hesitates and locks. Trimming it kills the joke's timing.
- `IMG_8197`: 0.48s between "pick" (3.119) and "and" (3.599). Breathing room
  under the CTA pill's entrance.

---

## 3. Assembled timeline

Content timeline = after trims, before the cold open is prepended and before
the disclaimer / consultation end cards are appended. All `content.json` times
(`sfx`, `cta`, `name`, `thumbnail`) use **this** timeline;
`build_composite.py` adds the opener offset itself (line 206) — do not
pre-compensate.

| Seg | Source | Content in → out | Dur | Beat |
|---|---|---|---|---|
| — | cold open | −2.00 → 0.00 | 2.00 | **CHOOSE YOUR NEXT MOVE** — 4 cards slam in |
| 0 | `IMG_8192` | 0.00 → 2.25 | 2.25 | "Pick one." (grid) → "**Wrong.**" (his face) |
| 1 | `IMG_8195` | 2.25 → 7.05 | 4.80 | "…fits **your situation**" |
| 2 | `IMG_8196` | 7.05 → 9.37 | 2.32 | "…cost you **months**" |
| 3 | `IMG_8197` | 9.37 → 12.87 | 3.50 | CTA |

Content 12.87s · +2.00 opener · +~6.2s end cards ≈ **21s finished reel**.

Cuts at **2.25 / 7.05 / 9.37** are plain hard cuts and must each be masked by a
wipe (`extra_wipes`), each a different style — the reel is dense and
B-roll-light, so the wipes are carrying all the transition variety.

---

## 4. The fighter-select grid

The single custom asset. 2×2 card grid, rendered as its own cold open and
carried into segment 0 as a cutaway so the two read as one continuous screen.

**Header:** `CHOOSE YOUR NEXT MOVE`

**Cards** (order matters — this is ascending commitment, not ascending quality):

| # | Label | Glyph | Colour |
|---|---|---|---|
| 1 | STUDY | 🎓 | cyan `#00B3E3` |
| 2 | 485 VISA | 🛫 | gold `#FFC500` |
| 3 | SKILLED MIGRATION | 🗺️ | green `#31EB7C` |
| 4 | EMPLOYER SPONSORSHIP | 🏢 | white on navy `#100796` |

Red `#E84B37` is deliberately **not** a card colour. It is reserved for the X
slam and the "months" warning, per the house rule that red means genuine
urgency — spending it on a card would flatten the punchline.

**Motion:**
1. Header wipes in, 0.0–0.35.
2. Cards slam in 1→2→3→4, ~0.12s apart, each with a `pop`. All four seated by ~1.15s.
3. A thick gold selector bracket appears on card 1 and holds. *(end of cold open)*
4. Over "Pick one." the bracket hops card→card, accelerating — visual indecision.
5. It locks on one card with a chime in the 0.92s silence.
6. On "Wrong" — hard cut to Tushar, and a red X slams over **all four** cards
   simultaneously with a buzzer + screen shake.

**Non-negotiable:** the X covers every card. See §1.

---

## 5. Beat-by-beat treatment

**Cold open (−2.00 → 0.00)** — grid builds. Silent source; SFX must be baked
into `opener.mp4` directly, because `content.json` SFX cues cannot address
negative time on the content timeline.

**"Pick one." (0.00 → 1.55)** — grid cutaway, bracket hopping. Tushar unseen,
voice only. Splice as B-roll at boundary 0.00, `broll_dur` 1.55.

**"Wrong." (1.55 → 2.25)** — cut to his close-up deadpan. Red X + `WRONG` slam,
screen shake, buzzer. The cut back to a human face on the punchline is the joke.

**"There's no best option… your situation" (2.25 → 7.05)** — stay on camera,
no graphics competing. `YOUR SITUATION` hero slam on the closing words. The four
cards may collapse inward into a single card reading `YOUR SITUATION` as the
resolution of the grid.

**"…guessing wrong could cost you months" (7.05 → 9.37)** — red warning
treatment, `MONTHS` emphasised, punch-zoom. This is the cost beat: it should
sting.

**CTA (9.37 → 12.87)** — wide corridor shot, lots of headroom. `COMMENT YOUR
PICK 👇` pill with a success chime. Grid may return small at top as a callback.

---

## 6. Audio

- Tier-1 SFX pass is mandatory: card pops, bracket ticks, buzzer on the X,
  whooshes on each wipe, success chime under the CTA.
- **Cue count is high (~10+). Scale volumes down.** Past ~8 cues the transients
  push the two-pass loudnorm's true peak over target. Start low, then verify
  with `qa_reel.py` — do not tune by ear.
- Music: an upbeat/arcade-leaning bed, ducked under voice. Any new track needs
  its CC-BY block in `assets/music/CREDIT.txt` **before** it is referenced, and
  mirrored into `caption_txt.music_credit`.
- `voice_denoise: true` — all four takes are in a hard-surfaced lobby
  (steel, stone, glass) with audible room reflection.

---

## 7. Caption band

`IMG_8195` and `IMG_8196` frame him seated with his face high (~40%);
`IMG_8197` is a wide with his face at ~22%. Check the subject's face position in
`work/base_broll.mp4` before setting `cap_top` so no caption card lands on his
face across the whole reel, not just the segment you happened to preview.

---

## 8. Lower-third

Tushar — Registered Migration Agent, **MARN 2418420** (confirmed by the user on
a previous reel; there is no roster file in the repo). **Never invent a MARN.**
Surname is not on file — either supply it for a full lower-third, or the card
runs first-name-only as it did on `2026-07-17_tushar-roadshow-adelaide-perth`.

---

## 9. Guardrails

- Do not let any one pathway read as the recommended answer.
- No eligibility claims, no processing times, no "fastest route" framing —
  this is a comment-bait engagement reel, not migration advice.
- The four labels are categories, not products. Keep them generic.
- Reel folders are local-only and gitignored (client footage) — never commit.
