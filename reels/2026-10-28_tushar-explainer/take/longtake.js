/* longtake.js -- PFEC's motion library for continuous-take films.
 *
 * Written from scratch for PodCut (2026-10-21). Every helper is a pure
 * function of time: a composition's render(t) may be called for any t, in any
 * order, any number of times, and must draw the same frame. No Date.now(), no
 * Math.random(), no state carried between calls (use LT.noise for wobble).
 *
 * A composition registers itself with LT.comp({...}); see templates/comp.html.
 * Elements that matter for continuity carry data-lt="<id>" so tools/longtake/
 * check.py can see what is on screen at each beat boundary.
 */
(function () {
  "use strict";
  const LT = {};

  // ---------- numbers ----------
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, k) => a + (b - a) * k;
  const prog = (t, a, b) => (b === a ? (t >= b ? 1 : 0) : clamp((t - a) / (b - a)));
  LT.clamp = clamp; LT.lerp = lerp; LT.prog = prog;
  LT.mix = (a, b, k) => Array.isArray(a) ? a.map((v, i) => lerp(v, b[i], k)) : lerp(a, b, k);

  // ---------- easing (k in 0..1 -> 0..1, may overshoot for back/elastic) ----------
  const E = {
    linear: k => k,
    in: k => k * k * k,
    out: k => 1 - Math.pow(1 - k, 3),
    inOut: k => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2),
    outQuint: k => 1 - Math.pow(1 - k, 5),
    inOutQuint: k => (k < 0.5 ? 16 * Math.pow(k, 5) : 1 - Math.pow(-2 * k + 2, 5) / 2),
    outExpo: k => (k >= 1 ? 1 : 1 - Math.pow(2, -10 * k)),
    inExpo: k => (k <= 0 ? 0 : Math.pow(2, 10 * k - 10)),
    inOutExpo: k => (k <= 0 ? 0 : k >= 1 ? 1 : k < 0.5 ? Math.pow(2, 20 * k - 10) / 2 : (2 - Math.pow(2, -20 * k + 10)) / 2),
    outBack: k => { const c = 1.7; return 1 + (c + 1) * Math.pow(k - 1, 3) + c * Math.pow(k - 1, 2); },
    sine: k => 0.5 - Math.cos(Math.PI * k) / 2,
  };
  LT.ease = E;
  const easeFn = e => (typeof e === "function" ? e : E[e || "inOut"] || E.inOut);

  // ---------- springs ----------
  // Step response of a damped harmonic oscillator released at time 0:
  // 0 at s=0, settles to 1. freq in Hz (how fast), damp = damping ratio
  // (<1 overshoots, 1 = critical, >1 sluggish). Closed form, so seekable.
  function spring(s, freq = 2.2, damp = 0.65) {
    if (s <= 0) return 0;
    const w = 2 * Math.PI * freq;
    if (damp < 1) {
      const wd = w * Math.sqrt(1 - damp * damp);
      return 1 - Math.exp(-damp * w * s) * (Math.cos(wd * s) + (damp * w / wd) * Math.sin(wd * s));
    }
    if (damp === 1) return 1 - Math.exp(-w * s) * (1 + w * s);
    const r = Math.sqrt(damp * damp - 1), a = -w * (damp - r), b = -w * (damp + r);
    return 1 - (b * Math.exp(a * s) - a * Math.exp(b * s)) / (b - a);
  }
  LT.spring = spring;
  // Time (s) after which a spring stays within `tol` of its target.
  LT.springSettle = (freq = 2.2, damp = 0.65, tol = 0.005) =>
    Math.log(1 / tol) / (Math.min(damp, 1) * 2 * Math.PI * freq);
  // Spring as an easing over a fixed window [t0, t0+dur] (dur ~ settle time).
  LT.springEase = (freq = 2.2, damp = 0.65) => {
    const settle = LT.springSettle(freq, damp);
    return k => spring(k * settle, freq, damp);
  };

  // ---------- keyframes ----------
  // LT.key(t, [[t0, v0], [t1, v1, ease], ...]) -> value at t. v may be a number
  // or an array (positions, colours as [r,g,b]). ease applies to the segment
  // ending at that key. Holds before the first and after the last key.
  LT.key = function (t, keys) {
    if (t <= keys[0][0]) return keys[0][1];
    for (let i = 1; i < keys.length; i++) {
      const [t1, v1, e] = keys[i];
      if (t <= t1) {
        const [t0, v0] = keys[i - 1];
        return LT.mix(v0, v1, easeFn(e)(prog(t, t0, t1)));
      }
    }
    return keys[keys.length - 1][1];
  };

  // ---------- colour ----------
  LT.hex = h => { const n = parseInt(h.replace("#", ""), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; };
  LT.rgb = (c, a = 1) => `rgba(${Math.round(c[0])},${Math.round(c[1])},${Math.round(c[2])},${a})`;
  LT.mixHex = (a, b, k, alpha = 1) => LT.rgb(LT.mix(LT.hex(a), LT.hex(b), clamp(k)), alpha);
  LT.BRAND = { navy: "#100796", deep: "#0a0560", gold: "#FFC500", cyan: "#00B3E3",
               green: "#31EB7C", red: "#E84B37", white: "#FFFFFF", ink: "#07043a" };

  // ---------- deterministic noise ----------
  function hash(n) { n = Math.sin(n * 127.1 + 311.7) * 43758.5453123; return n - Math.floor(n); }
  // Smooth 1-D value noise in [-1, 1]; same (x, seed) -> same value, always.
  LT.noise = function (x, seed = 0) {
    const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f);
    return lerp(hash(i + seed * 57.3), hash(i + 1 + seed * 57.3), u) * 2 - 1;
  };
  // Two octaves -> organic drift.
  LT.drift = (t, speed = 0.35, seed = 0) =>
    LT.noise(t * speed, seed) * 0.7 + LT.noise(t * speed * 2.3, seed + 9) * 0.3;

  // ---------- camera ----------
  // shots: [{t, x, y, zoom, rot, ease}] -- the camera looks at (x, y) in stage
  // px with `zoom`. Between shots it travels with that shot's ease (a spring
  // via LT.springEase reads as an operator catching up). Options:
  //   hand: px of handheld drift (0 = locked off), handSeed
  //   hits: [{t, amp, dur}] impact shakes (decaying, deterministic)
  //   holdStill: [[a, b], ...] windows where drift is faded out (rests)
  LT.camera = function (t, shots, opt = {}) {
    const k = (f, d) => LT.key(t, shots.map((s, i) => [s.t, s[f] ?? d, i ? s.ease : undefined]));
    let x = k("x", 0), y = k("y", 0), zoom = k("zoom", 1), rot = k("rot", 0);
    const hand = opt.hand || 0;
    if (hand) {
      let damp = 1;
      for (const [a, b] of opt.holdStill || []) damp = Math.min(damp, 1 - LT.key(t, [[a - 0.25, 0], [a, 1, "sine"], [b, 1], [b + 0.25, 0, "sine"]]));
      const s = opt.handSeed || 1;
      x += LT.drift(t, 0.3, s) * hand * damp;
      y += LT.drift(t, 0.27, s + 3) * hand * damp;
      rot += LT.drift(t, 0.21, s + 7) * hand * 0.004 * damp;
    }
    for (const h of opt.hits || []) {
      const s = t - h.t, dur = h.dur || 0.45;
      if (s < 0 || s > dur) continue;
      const env = Math.exp(-6 * s / dur) * (1 - s / dur), amp = (h.amp || 18) * env;
      x += LT.noise(s * 38, 11) * amp; y += LT.noise(s * 41, 23) * amp; rot += LT.noise(s * 29, 31) * amp * 0.002;
    }
    return { x, y, zoom, rot };
  };
  // Apply a camera to the world element (which holds every on-stage layer).
  LT.applyCamera = function (el, cam, W, H) {
    el.style.transformOrigin = "0 0";
    el.style.transform = `translate(${W / 2}px,${H / 2}px) rotate(${cam.rot}rad) scale(${cam.zoom}) translate(${-cam.x}px,${-cam.y}px)`;
  };
  // Zoom at which a box of width w (stage px) fills `frac` of the frame width.
  LT.zoomToFit = (w, W, frac = 0.9) => (W * frac) / w;

  // ---------- shapes ----------
  // A rect {x, y, w, h, r, fill, alpha} (x, y = centre) morphing between
  // states: the same element becomes the next thing instead of being swapped.
  LT.morph = function (t, states) {
    // states: [[t, {x,y,w,h,r,fill,alpha}], [t, {...}, ease], ...]
    const out = {};
    for (const f of ["x", "y", "w", "h", "r", "alpha", "rot"]) {
      const ks = states.filter(s => s[1][f] !== undefined).map(s => [s[0], s[1][f], s[2]]);
      if (ks.length) out[f] = LT.key(t, ks);
    }
    const cs = states.filter(s => s[1].fill).map(s => [s[0], LT.hex(s[1].fill), s[2]]);
    if (cs.length) out.fill = LT.rgb(LT.key(t, cs));
    return out;
  };
  // Write a state onto an absolutely-positioned element (centre-anchored).
  LT.set = function (el, s) {
    const st = el.style;
    if (s.w !== undefined) st.width = s.w + "px";
    if (s.h !== undefined) st.height = s.h + "px";
    const x = s.x ?? 0, y = s.y ?? 0, sc = s.scale ?? 1, sx = s.sx ?? 1, sy = s.sy ?? 1;
    st.left = "0px"; st.top = "0px";
    st.transform = `translate(${x}px,${y}px) translate(-50%,-50%) rotate(${s.rot || 0}rad) scale(${sc * sx},${sc * sy})`;
    if (s.r !== undefined) st.borderRadius = s.r + "px";
    if (s.fill !== undefined) st.background = s.fill;
    if (s.color !== undefined) st.color = s.color;
    if (s.alpha !== undefined) st.opacity = clamp(s.alpha);
    if (s.blur !== undefined) st.filter = s.blur > 0.05 ? `blur(${s.blur}px)` : "none";
    if (s.clip !== undefined) st.clipPath = s.clip;
    st.visibility = (s.alpha !== undefined && s.alpha <= 0.001) || sc === 0 ? "hidden" : "visible";
  };
  LT.el = id => document.querySelector(`[data-lt="${id}"]`);

  // ---------- entrances / text ----------
  // Squash-and-settle pop for an element arriving (returns {scale, sx, sy, alpha}).
  LT.pop = function (t, t0, opt = {}) {
    const s = t - t0;
    if (s <= 0) return { scale: 0, alpha: 0 };
    const sc = spring(s, opt.freq || 2.6, opt.damp || 0.5);
    const sq = 1 + 0.18 * Math.exp(-7 * s) * Math.sin(s * 22);
    return { scale: sc, sx: sq, sy: 2 - sq, alpha: clamp(s / 0.06) };
  };
  // Mask reveal: inset clip opening from one side. dir: up|down|left|right.
  LT.reveal = function (t, t0, dur = 0.5, dir = "up", ease = "outQuint") {
    const k = easeFn(ease)(prog(t, t0, t0 + dur)), r = (1 - k) * 100;
    const m = { up: `inset(${r}% 0 0 0)`, down: `inset(0 0 ${r}% 0)`, left: `inset(0 ${r}% 0 0)`, right: `inset(0 0 0 ${r}%)` };
    return m[dir];
  };
  // Split an element's text into spans once (call at build time, not in render).
  // Line breaks (<br>) are kept; only text nodes are split.
  LT.split = function (el, mode = "words") {
    const spans = [], nodes = [...el.childNodes];
    el.textContent = "";
    for (const n of nodes) {
      if (n.nodeType !== 3) { el.appendChild(n); continue; }
      const parts = mode === "chars" ? [...n.textContent] : n.textContent.split(/(\s+)/);
      for (const p of parts) {
        if (!p) continue;
        const s = document.createElement("span");
        s.textContent = p; s.style.display = "inline-block"; s.style.whiteSpace = "pre";
        el.appendChild(s); spans.push(s);
      }
    }
    return spans;
  };
  // Staggered rise for split spans (words/chars): each lifts `dist` px and fades in.
  LT.rise = function (t, spans, t0, opt = {}) {
    const stagger = opt.stagger ?? 0.06, dur = opt.dur ?? 0.55, dist = opt.dist ?? 60;
    spans.forEach((s, i) => {
      const k = easeFn(opt.ease || "outQuint")(prog(t, t0 + i * stagger, t0 + i * stagger + dur));
      s.style.transform = `translateY(${(1 - k) * dist}px)`; s.style.opacity = k;
    });
  };
  // Typewriter: show the first n characters of `text` at `cps` chars/sec.
  LT.typed = (t, text, t0, cps = 22) => text.slice(0, Math.max(0, Math.floor((t - t0) * cps)));
  // Count-up between two numbers over [t0, t1] (for real figures only).
  LT.count = (t, t0, t1, a, b, ease = "outExpo") => Math.round(lerp(a, b, easeFn(ease)(prog(t, t0, t1))));

  // ---------- composition contract ----------
  // LT.comp({ width, height, dur, render(t), beats, cues })
  //   beats: [{ t, name, handoff: "<data-lt id>" | null, cut: bool }]
  //     A beat boundary is where one idea becomes the next. `handoff` names the
  //     element that survives across it (check.py verifies it is on screen on
  //     both sides). Set cut:true only for a deliberate hard cut.
  //   cues: [{ t, file, vol }] one-shot SFX (resolved by render.py against the
  //     comp folder, then podcut/assets/sfx/).
  LT.comp = function (c) {
    const W = c.width || 1080, H = c.height || 1920;
    const P = new URLSearchParams(location.search), rendering = P.has("render");
    const stage = document.getElementById("stage");
    stage.style.width = W + "px"; stage.style.height = H + "px";
    window.__dur = c.dur;
    window.__size = [W, H];
    window.__beats = (c.beats || []).map(b => ({ t: b.t, name: b.name || "", handoff: b.handoff ?? null, cut: !!b.cut }));
    window.__cues = c.cues || [];
    window.__seek = t => { c.render(clamp(t, 0, c.dur)); return true; };
    window.__ready = false;
    const fit = () => {
      if (rendering) return;
      const s = Math.min(innerWidth / W, (innerHeight - 44) / H);
      stage.style.transform = `scale(${s})`; stage.style.transformOrigin = "0 0";
      document.body.style.width = W * s + "px";
    };
    document.fonts.ready.then(() => {
      window.__seek(0); window.__ready = true;
      if (rendering) return;
      // Preview: play loop + scrubber (space toggles, drag to seek).
      document.body.classList.add("preview");
      const bar = document.createElement("input");
      Object.assign(bar, { type: "range", min: 0, max: c.dur, step: 0.001, value: 0 });
      bar.id = "lt-scrub"; document.body.appendChild(bar);
      let playing = true, t0 = performance.now(), at = 0;
      bar.oninput = () => { playing = false; at = +bar.value; window.__seek(at); };
      addEventListener("keydown", e => { if (e.code === "Space") { playing = !playing; t0 = performance.now() - at * 1000; e.preventDefault(); } });
      const loop = () => {
        if (playing) { at = ((performance.now() - t0) / 1000) % c.dur; window.__seek(at); bar.value = at; }
        requestAnimationFrame(loop);
      };
      fit(); addEventListener("resize", fit); loop();
    });
  };

  if (typeof window !== "undefined") window.LT = LT;
  if (typeof module !== "undefined") module.exports = LT;
})();
