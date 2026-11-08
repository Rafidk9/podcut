// node tests/test_longtake.js -- the motion library's numbers.
const LT = require("../lib/longtake.js");
let fails = 0;
const ok = (cond, msg) => { console.log(`${cond ? "PASS" : "FAIL"}  ${msg}`); if (!cond) fails++; };
const near = (a, b, eps = 1e-6) => Math.abs(a - b) <= eps;

// easing: every curve starts at 0 and ends at 1
for (const [k, f] of Object.entries(LT.ease)) ok(near(f(0), 0, 1e-9) && near(f(1), 1, 1e-9), `ease.${k} maps 0->0, 1->1`);
ok(Math.max(...[...Array(101)].map((_, i) => LT.ease.outBack(i / 100))) > 1, "outBack overshoots");

// springs: 0 at release, settle to 1, under-damped overshoots, critical doesn't
ok(LT.spring(0) === 0 && LT.spring(-1) === 0, "spring is 0 before release");
ok(near(LT.spring(10, 2, 0.6), 1, 1e-4), "under-damped spring settles to 1");
ok(Math.max(...[...Array(200)].map((_, i) => LT.spring(i / 100, 2, 0.4))) > 1.05, "under-damped spring overshoots");
ok(Math.max(...[...Array(300)].map((_, i) => LT.spring(i / 100, 2, 1))) <= 1 + 1e-9, "critical spring never overshoots");
ok(near(LT.spring(10, 2, 1.6), 1, 1e-3), "over-damped spring settles to 1");
const se = LT.springEase(1.8, 0.72);
ok(near(se(0), 0) && Math.abs(se(1) - 1) < 0.01, "springEase spans 0 -> ~1 over its window");
const st = LT.springSettle(2, 0.7);
ok([...Array(50)].every((_, i) => Math.abs(LT.spring(st + i * 0.05, 2, 0.7) - 1) < 0.006), "springSettle: stays within tolerance after settle time");

// keyframes
const ks = [[0, 0], [1, 10, "linear"], [2, 10], [3, 0, "out"]];
ok(LT.key(-1, ks) === 0 && LT.key(0.5, ks) === 5 && LT.key(1.5, ks) === 10 && LT.key(9, ks) === 0, "key: holds, interpolates, holds after last");
const arr = LT.key(0.5, [[0, [0, 100]], [1, [10, 0], "linear"]]);
ok(arr[0] === 5 && arr[1] === 50, "key interpolates arrays");

// determinism: the same t always gives the same value
ok(LT.noise(3.7, 2) === LT.noise(3.7, 2) && LT.noise(3.7, 2) !== LT.noise(3.7, 3), "noise is deterministic and seed-dependent");
ok([...Array(500)].every((_, i) => Math.abs(LT.noise(i * 0.137, 1)) <= 1), "noise stays in [-1, 1]");
const shots = [{ t: 0, x: 0, y: 0, zoom: 1 }, { t: 2, x: 100, y: 50, zoom: 2, ease: "inOut" }];
const opt = { hand: 8, handSeed: 3, hits: [{ t: 1, amp: 20 }] };
const c1 = LT.camera(1.234, shots, opt), c2 = LT.camera(1.234, shots, opt);
ok(JSON.stringify(c1) === JSON.stringify(c2), "camera is a pure function of t");
const still = LT.camera(5, shots, { hand: 8, holdStill: [[4, 6]] });
ok(near(still.x, 100) && near(still.y, 50), "holdStill removes handheld drift inside a rest");
ok(Math.abs(LT.camera(1.05, shots, opt).x - LT.camera(1.05, shots, { hand: 8, handSeed: 3 }).x) > 0.5, "impact hit shakes the camera");
ok(near(LT.camera(1.6, shots, opt).x, LT.camera(1.6, shots, { hand: 8, handSeed: 3 }).x), "shake has decayed after its duration");

// morph / colour
const m = LT.morph(0.5, [[0, { w: 100, fill: "#000000" }], [1, { w: 300, fill: "#FFFFFF" }, "linear"]]);
ok(m.w === 200 && m.fill === "rgba(128,128,128,1)", "morph interpolates size and colour");
ok(LT.count(1, 0, 1, 0, 7) === 7 && LT.count(-1, 0, 1, 0, 7) === 0, "count lands exactly on its end values");
ok(LT.typed(0.5, "HELLO", 0, 4) === "HE" && LT.typed(-1, "HELLO", 0) === "", "typed reveals at cps");

console.log(fails ? `\n${fails} FAILED` : "\nALL PASS");
process.exit(fails ? 1 : 0);
