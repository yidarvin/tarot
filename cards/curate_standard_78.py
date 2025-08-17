#!/usr/bin/env python3
import os
import re
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMAGES = ROOT / "images"
OUT = ROOT / "standard"
OUT.mkdir(exist_ok=True)

# Expected majors with their canonical RWS naming pattern used on Commons
MAJORS = [
    (0, "Fool"), (1, "Magician"), (2, "High_Priestess"), (3, "Empress"), (4, "Emperor"),
    (5, "Hierophant"), (6, "Lovers"), (7, "Chariot"), (8, "Strength"), (9, "Hermit"),
    (10, "Wheel_of_Fortune"), (11, "Justice"), (12, "Hanged_Man"), (13, "Death"),
    (14, "Temperance"), (15, "Devil"), (16, "Tower"), (17, "Star"), (18, "Moon"),
    (19, "Sun"), (20, "Judgement"), (21, "World"),
]

SUITS = ["Cups", "Pents", "Swords", "Wands"]
RANKS = [f"{i:02d}" for i in range(1, 15)]  # 01..14

# Build expected filename patterns to look for inside IMAGES
expected_files = []
for num, name in MAJORS:
    expected_files.append((f"RWS_Tarot_{num:02d}_", re.compile(rf"^RWS_Tarot_{num:02d}_.+\.jpg$", re.I)))
for suit in SUITS:
    for rank in RANKS:
        expected_files.append((f"{suit}{rank}", re.compile(rf"^{suit}{rank}\.jpg$", re.I)))

# Known fallbacks for files that sometimes use alternative names on Commons
FALLBACKS = {
    # Missing Wands09.jpg is often named differently in the category
    "Wands09": ["Tarot_Nine_of_Wands.jpg"],
}

# Index available filenames
all_files = {p.name for p in IMAGES.glob("*.jpg")}

selected = {}
not_found = []
for key, pattern in expected_files:
    match = next((f for f in all_files if pattern.match(f)), None)
    if match:
        selected[key] = match
        continue
    # try fallbacks
    fb = FALLBACKS.get(key)
    if fb:
        for cand in fb:
            if cand in all_files:
                selected[key] = cand
                break
    if key not in selected:
        not_found.append(key)

# Copy into OUT with canonical names
mapping = []
for key, src_name in sorted(selected.items()):
    src = IMAGES / src_name
    # Canonical output name: keep original for majors, exact SuitNN for minors
    if key.startswith("RWS_Tarot_"):
        out_name = src_name
    else:
        # key is like SuitNN; ensure output name SuitNN.jpg
        out_name = f"{key}.jpg"
    dst = OUT / out_name
    if not dst.exists():
        shutil.copy2(src, dst)
    mapping.append({"key": key, "source": src_name, "output": out_name})

report = {
    "selected_count": len(selected),
    "expected_count": len(expected_files),
    "missing": not_found,
    "mapping": mapping,
}
with open(ROOT / "standard_manifest.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print(f"Selected {len(selected)} / {len(expected_files)} images.")
if not_found:
    print("Missing:")
    for k in not_found:
        print(" -", k)
