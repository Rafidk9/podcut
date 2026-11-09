import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_hop import build_hop, WORK

jobs = [
    ("ADELAIDE", "MELBOURNE", "#00B3E3", os.path.join(WORK, "hop_adelaide_melbourne.mp4")),
    ("MELBOURNE", "HOBART & LAUNCESTON", "#31EB7C", os.path.join(WORK, "hop_melbourne_tasmania.mp4")),
    ("HOBART & LAUNCESTON", "BRISBANE", "#FFC500", os.path.join(WORK, "hop_tasmania_brisbane.mp4")),
    ("", "PERTH", "#FFC500", os.path.join(WORK, "hop_open_perth.mp4")),
]

for from_label, to_label, color, out in jobs:
    print("=== building", from_label, "->", to_label, "===")
    build_hop(from_label, to_label, color, out)
