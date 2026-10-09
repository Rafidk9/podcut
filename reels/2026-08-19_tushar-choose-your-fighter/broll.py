"""B-roll stingers for the Tushar Chopra / "Choose Your Fighter" reel.

ONE cutaway, and it is an unusual one for this pipeline: it opens the reel
rather than hiding a connecting phrase mid-script.

The house rule (reels/README.md) is that B-roll only ever covers connecting or
filler phrases, never a moment carrying key information. This splice is the
documented exception the 2026-08-11 Tushar reel established for its match cut
-- the rule exists so graphics never OBSCURE a spoken fact, and here the
graphic IS the fact. The line being spoken over it is "Pick one. ... Wrong."
Pick one *what*? The four cards ARE the answer to that question; without them
on screen the opening line is meaningless. Cutting away to the grid presents
the information instead of hiding it.

Placement is therefore segment 0 at 0.00 for 2.20s, against a 2.25s segment.
Local times inside the splice equal content-timeline times, because the splice
starts at zero:

    "Pick"            0.229
    "one."     ends   0.690
    (0.92s of held silence -- the selector's indecision, then its lock)
    "Wrong"           1.609 - 2.029
    splice ends       2.20   -> and the wipe centred on the 2.25 cut covers the
                               1-2 frames left, so the X wipes straight into the
                               next take. He is NEVER seen saying "Wrong".

The cutaway cannot simply cover the whole segment: insert_broll splices as
broll[0:dur] + seg_video[dur:], so an exactly-equal dur would leave an empty
second half and break the concat. 2.20 against 2.25 leaves the minimum viable
remainder, and the wipe hides it. Rendered at 2.5s so the held X has real tail
behind the splice point rather than ending on the stinger's last frame.

EARLIER VERSION, kept as a record: the splice used to end at 2.10 and smash-cut
to him holding a smile. Reviewed and rejected -- see clips.json's
_keep_8192_note. The X now exits under the wipe instead.

THE ONE THING NOT TO "FIX": the X at 1.609 covers ALL FOUR cards at once, not
the card the selector locked onto. That inversion is the entire creative --
the joke is that picking from a menu is itself the wrong move, which is what
sets up his next line ("there's no best option, there's only the one that fits
your situation"). An X on the selected card alone would say "you guessed
wrong, try again", which is the opposite message and would make the rest of
the reel a non-sequitur. See EDIT_PROMPT.md section 1.

Red (#E84B37) is deliberately absent from the four card colours and is spent
only on the X, per the house rule that red means genuine urgency. The cards
take cyan / gold / green / white so no single one reads as the recommended
answer -- there is no visual ranking, and the order is ascending commitment,
not ascending quality.

Seek-safety: HyperFrames renders by seeking a paused timeline, so EVERY hop of
the selector is a fromTo with explicit from-and-to coordinates rather than a
chained relative .to(). A chained .to() would resolve its start value from
whatever state the previous render left behind, which is fine playing forward
and wrong on a seek.
"""

# Card geometry, shared by the markup and the selector's hop table below.
CARD = 420          # card edge, px
PITCH = 466         # card edge + 46px gutter
GX, GY = 97, 660    # grid box origin -- 886x886 centred horizontally in 1080

# (x, y) of each card's top-left, in the same order as the markup.
POS = [(GX, GY), (GX + PITCH, GY), (GX, GY + PITCH), (GX + PITCH, GY + PITCH)]

# Selector hop table: (time, card index). Deliberately accelerating -- the gaps
# run 0.12 -> 0.14 -> 0.13 -> 0.11 -> 0.09 -> 0.08 -> 0.07 -> 0.06, so the
# cursor reads as increasingly frantic indecision rather than a metronome, and
# arrives at its lock exactly in the middle of the held silence.
HOPS = [
    (0.72, 1), (0.86, 3), (0.99, 2), (1.10, 0),
    (1.19, 1), (1.27, 3), (1.34, 2), (1.40, 1),
]
LOCK_AT = 1.45      # selector settles, chime
X_AT = 1.609        # "Wrong" -- X slams over all four

_CARDS = [
    ("STUDY", "&#127891;", "#00B3E3"),
    ("485 VISA", "&#9992;&#65039;", "#FFC500"),
    ("SKILLED<br>MIGRATION", "&#128736;&#65039;", "#31EB7C"),
    ("EMPLOYER<br>SPONSORSHIP", "&#127970;", "#FFFFFF"),
]


def _card_html():
    out = []
    for i, (label, glyph, colour) in enumerate(_CARDS):
        x, y = POS[i]
        out.append(
            f'<div class="card" id="c{i}" style="left:{x}px;top:{y}px;'
            f'border-color:{colour};box-shadow:0 0 0 2px rgba(0,0,0,.35),'
            f'0 18px 46px rgba(0,0,0,.5),inset 0 0 62px {colour}22">'
            f'<div class="num" style="background:{colour};'
            f'color:{"#100796" if colour != "#FFFFFF" else "#100796"}">{i + 1}</div>'
            f'<div class="glyph">{glyph}</div>'
            f'<div class="lbl" style="color:{colour}">{label}</div>'
            f'</div>')
    return "\n".join(out)


def _hop_js():
    """Emit one fromTo per hop, with both endpoints stated explicitly.

    immediateRender:false is LOAD-BEARING, not tidiness. gsap.fromTo defaults
    to immediateRender:true, which paints the tween's "from" values the moment
    the tween is CREATED rather than when the playhead reaches it. With eight
    hops all targeting #sel that meant every one of them stamped its own start
    position during timeline construction and the last one created won, so the
    selector sat on card 3 from the first frame instead of card 1 -- visible in
    the very first render at t=0.62, before any hop was supposed to have run.
    Suppressing it leaves #sel at its CSS position until the first hop actually
    starts, and each hop still renders correctly on a seek because its
    endpoints are both stated explicitly.
    """
    lines = []
    prev = 0
    for t, idx in HOPS:
        fx, fy = POS[prev]
        tx, ty = POS[idx]
        lines.append(
            f'  tl.fromTo("#sel",{{x:{fx - GX},y:{fy - GY}}},'
            f'{{x:{tx - GX},y:{ty - GY},duration:.07,ease:"power2.out",'
            f'immediateRender:false}},{t});')
        prev = idx
    return "\n".join(lines)


FIGHTER_GRID = """
<style id="fg">
  html,body{background:#05051a}
  #stage{position:absolute;inset:0}
  #bg{position:absolute;inset:0;
      background:radial-gradient(120% 80% at 50% 34%,#1b1499 0%,#0b0a2e 55%,#05051a 100%)}
  /* Faint scanlines + a vignette so the frame reads as a screen, not a slide. */
  #scan{position:absolute;inset:0;opacity:.16;
        background:repeating-linear-gradient(180deg,
          rgba(255,255,255,.10) 0 2px, rgba(0,0,0,0) 2px 6px)}
  #vig{position:absolute;inset:0;
       background:radial-gradient(80% 60% at 50% 50%,rgba(0,0,0,0) 40%,rgba(0,0,0,.55) 100%)}
  .orb{position:absolute;border-radius:50%;filter:blur(80px);opacity:.26}
  #o1{width:560px;height:560px;left:-160px;top:520px;background:#00B3E3}
  #o2{width:520px;height:520px;right:-150px;bottom:300px;background:#FFC500}

  #head{position:absolute;left:0;right:0;top:400px;text-align:center;
        font-family:Poppins,sans-serif;font-weight:900;font-size:62px;color:#fff;
        letter-spacing:.03em;opacity:0;text-shadow:0 8px 28px rgba(0,0,0,.6)}
  #rule{position:absolute;left:50%;top:496px;width:0;height:9px;border-radius:5px;
        background:#FFC500;transform:translateX(-50%)}

  /* grayscale/brightness are stated explicitly rather than left at the
     default `filter:none`, so the X-slam tween at 1.609 interpolates numerically
     instead of snapping -- GSAP cannot tween FROM the keyword `none`. */
  .card{position:absolute;width:420px;height:420px;border-radius:36px;
        border:5px solid #fff;background:rgba(255,255,255,.055);
        opacity:0;overflow:hidden;filter:grayscale(0) brightness(1);
        display:flex;flex-direction:column;align-items:center;justify-content:center}
  .num{position:absolute;left:22px;top:22px;width:52px;height:52px;border-radius:14px;
       font-family:Poppins,sans-serif;font-weight:900;font-size:30px;
       display:flex;align-items:center;justify-content:center}
  .glyph{font-size:132px;line-height:1;margin-top:-14px}
  .lbl{font-family:Poppins,sans-serif;font-weight:800;font-size:38px;
       text-align:center;line-height:1.12;margin-top:26px;letter-spacing:.01em}

  /* Selector: gold bracket sitting 16px proud of a card, moved by x/y only. */
  #sel{position:absolute;left:81px;top:644px;width:452px;height:452px;
       border:9px solid #FFC500;border-radius:44px;opacity:0;
       box-shadow:0 0 34px rgba(255,197,0,.75),inset 0 0 26px rgba(255,197,0,.35)}

  /* Failure layer, all of it scoped to the grid box so it reads as "the whole
     board is wrong", not "the screen glitched". */
  #xwrap{position:absolute;left:97px;top:660px;width:886px;height:886px;opacity:0}
  #wash{position:absolute;inset:0;border-radius:40px;background:rgba(232,75,55,.30)}
  .xbar{position:absolute;left:50%;top:50%;width:1250px;height:76px;border-radius:38px;
        background:#E84B37;box-shadow:0 0 46px rgba(232,75,55,.9)}
  #xb1{transform:translate(-50%,-50%) rotate(45deg)}
  #xb2{transform:translate(-50%,-50%) rotate(-45deg)}

  #foot{position:absolute;left:50%;top:1640px;transform:translateX(-50%);
        padding:16px 44px;border:4px solid rgba(255,197,0,.85);border-radius:999px;
        font-family:Poppins,sans-serif;font-weight:800;font-size:34px;color:#FFC500;
        letter-spacing:.16em;opacity:0}
</style>

<div id="stage">
  <div id="bg"></div>
  <div class="orb" id="o1"></div>
  <div class="orb" id="o2"></div>
  <div id="scan"></div>
  <div id="vig"></div>

  <div id="head">CHOOSE YOUR NEXT MOVE</div>
  <div id="rule"></div>

__CARDS__

  <div id="sel"></div>

  <div id="xwrap">
    <div id="wash"></div>
    <div class="xbar" id="xb1"></div>
    <div class="xbar" id="xb2"></div>
  </div>

  <div id="foot">SELECT ONE</div>
</div>

<script>
(function(){
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});

  // Header snaps in almost immediately -- "Pick" lands at 0.229 and the viewer
  // has to have read the question before he asks it.
  tl.fromTo("#head",{opacity:0,y:22},{opacity:1,y:0,duration:.12,ease:"power3.out"},0.00);
  tl.to("#rule",{width:360,duration:.20,ease:"power2.out"},0.06);

  // Orbs drift the whole time so the background is never static.
  tl.to("#o1",{x:60,y:-44,duration:2.2,ease:"sine.inOut"},0);
  tl.to("#o2",{x:-52,y:36,duration:2.2,ease:"sine.inOut"},0);

  // Four cards slam in fast, 0.08s apart -- arcade roster, not a bullet list.
  // All four are seated by 0.60, comfortably before "one." ends at 0.690.
  [0,1,2,3].forEach(function(i){
    var t = 0.14 + i*0.08;
    tl.fromTo("#c"+i,{opacity:0,scale:1.35,rotation:i%2?2.5:-2.5},
      {opacity:1,scale:1,rotation:0,duration:.22,ease:"back.out(2)"},t);
  });

  tl.fromTo("#foot",{opacity:0,y:16},{opacity:1,y:0,duration:.18,ease:"power3.out"},0.50);

  // Selector appears on card 1, then hops with accelerating gaps.
  tl.fromTo("#sel",{opacity:0,scale:1.2},{opacity:1,scale:1,duration:.14,ease:"back.out(2)"},0.60);
__HOPS__

  // Lock: a single firm settle in the middle of the held silence. This is the
  // frame where the viewer commits to a guess -- which is what makes the next
  // 0.16s land.
  tl.to("#sel",{scale:1.06,duration:.08,ease:"power2.out"},LOCK);
  tl.to("#sel",{scale:1,duration:.12,ease:"power2.inOut"},LOCK+0.08);

  // "Wrong." -- X over ALL FOUR cards. Do not narrow this to the locked card;
  // see the module docstring.
  tl.to(".card",{filter:"grayscale(.85) brightness(.72)",duration:.10,ease:"power2.out"},XAT);
  tl.to("#sel",{opacity:0,duration:.08,ease:"power2.in"},XAT);
  tl.fromTo("#xwrap",{opacity:0,scale:1.55},
    {opacity:1,scale:1,duration:.16,ease:"back.out(2.2)"},XAT);
  tl.fromTo("#foot",{color:"#FFC500",borderColor:"rgba(255,197,0,.85)"},
    {color:"#E84B37",borderColor:"rgba(232,75,55,.95)",duration:.10},XAT);

  // Two-frame shake on the impact, settling immediately -- weight, not chaos.
  tl.fromTo("#stage",{x:0,y:0},{x:-16,y:9,duration:.045,ease:"none"},XAT);
  tl.to("#stage",{x:13,y:-7,duration:.045,ease:"none"},XAT+0.045);
  tl.to("#stage",{x:-7,y:4,duration:.045,ease:"none"},XAT+0.09);
  tl.to("#stage",{x:0,y:0,duration:.06,ease:"power2.out"},XAT+0.135);

  window.__timelines["main"]=tl;
})();
</script>
"""

FIGHTER_GRID = (FIGHTER_GRID
                .replace("__CARDS__", _card_html())
                .replace("__HOPS__", _hop_js())
                .replace("LOCK+0.08", f"{LOCK_AT + 0.08}")
                .replace("LOCK", str(LOCK_AT))
                .replace("XAT+0.045", f"{X_AT + 0.045}")
                .replace("XAT+0.09", f"{X_AT + 0.09}")
                .replace("XAT+0.135", f"{X_AT + 0.135}")
                .replace("XAT", str(X_AT)))

STINGERS = [
    ("fighter_grid", 2.5, FIGHTER_GRID),
]
