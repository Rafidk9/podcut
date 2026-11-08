# End cards

Appended to every reel by `reels/build_composite.py` (disclaimer first, then
consultation), 3.0 s each, 1080x1920 @ 30 fps.

| File | Source |
|---|---|
| `disclaimer-card.mp4` | original render, no editable source in the repo |
| `consultation-card.mp4` | `src/consultation-card/comp.html` (longtake), rebuilt 2026-10-21 with all **7 offices**, Parramatta last |
| `consultation-card.6-offices.bak.mp4` | the previous card (6 offices, no Parramatta), kept only for reference. Don't use it |

To change an office address or phone number, edit the `OFFICES` list in
`src/consultation-card/comp.html` (keep it in step with
`reels/build_caption_txt.py`'s `OFFICES`), then re-render from that folder:

```
../../../../engine/.venv/Scripts/python.exe ../../../../tools/longtake/render.py comp.html --out ../../consultation-card.mp4 --no-sfx
```

Reels already in `output/` keep the old card until they're rebuilt with `build_composite.py`.
