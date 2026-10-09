"""One-off: pull Anton + Exo 2 woff2 into assets/fonts/ so renders don't depend on the network."""
import os
import re
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
OUT = os.path.join("assets", "fonts")
os.makedirs(OUT, exist_ok=True)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=60).read()


for family, stem in [("Anton", "anton"), ("Exo+2:wght@400", "exo2")]:
    css = get(f"https://fonts.googleapis.com/css2?family={family}&display=block").decode("utf-8")
    urls = re.findall(r"https://fonts\.gstatic\.com/[^\)]+\.woff2", css)
    # last @font-face block in Google's css2 output is the latin subset
    latin = None
    for block in css.split("@font-face"):
        if "U+0000-00FF" in block:
            m = re.search(r"https://fonts\.gstatic\.com/[^\)]+\.woff2", block)
            if m:
                latin = m.group(0)
    url = latin or (urls[-1] if urls else None)
    if not url:
        print(f"{family}: NO URL FOUND")
        continue
    data = get(url)
    path = os.path.join(OUT, f"{stem}.woff2")
    with open(path, "wb") as fh:
        fh.write(data)
    print(f"{family}: {len(data)} bytes -> {path}")
