"""
Build script: converts English machine-draft translations of several
biblical (not sectarian) Dead Sea Scroll manuscripts from the Open Dead
Sea project into data/qumran/*.json, keyed by real Bible chapter:verse so
they line up directly against the existing KJV corpus for comparison.

Source: https://opendeadsea.org/ (data mirrored at
https://github.com/apocalypse-press/opendeadsea-mss), same project and
same CC BY-NC 4.0 terms already used for this bot's sectarian Qumran
texts (see build_open_dead_sea.py) -- this is the biblical-manuscript
half of the same dataset, not a new source.

IMPORTANT -- same caveat as the sectarian build: these are machine
drafts, not finished scholarly translations, per Open Dead Sea's own
README ("Do not treat the machine drafts as finished scholarly
translations"). Every line was produced by an LLM (Cohere Command A)
grounded against the Hebrew transcription, queued for human review that
hasn't completed yet.

SELECTION -- verified directly, not assumed: most fragmentary biblical
scrolls in this dataset are keyed by physical fragment number (e.g.
"4Q51 f2:1"), not real Bible chapter:verse, because scholars haven't
placed every fragment in a continuous chapter/verse sequence. A scroll
keyed that way can't be looked up by "Isaiah 53:5" at all -- there's no
correspondence. Checked every biblical manuscript's actual line-ref
format directly against manuscripts.json's line_count ranking; only
these five are both substantial and cleanly keyed by real chapter:verse
end to end:
  1QIsaa (Great Isaiah Scroll) -- 1601/1601 lines clean, the largest and
    most complete biblical DSS manuscript by far.
  4Q22 (4QpaleoExodm, Exodus)  -- 684/684 lines clean.
  4Q41 (Deuteronomy)           -- 67/68 lines clean.
  4Q86 (Psalms)                -- 45/45 lines clean.
  4Q114 (Daniel)               -- 37/37 lines clean.
Other large witnesses (4QSama/4Q51, 4QNumb/4Q27, most Deuteronomy/Isaiah/
Psalms duplicates) were excluded because their lines are fragment-keyed,
not chapter:verse-keyed -- including them under invented chapter numbers
would misrepresent them, the same principle already applied to the
sectarian scrolls' unplaced fragments.

One scroll per book (not merging overlapping witnesses), matching the
existing sectarian-scroll build's rule.

Downloads its own source -- run from anywhere:
    python deprecated/build_open_dead_sea_biblical.py
"""
import json
import re
import time
import urllib.request
from pathlib import Path

BASE = "https://opendeadsea.org/data/translations"
OUT_DIR = Path(__file__).parent.parent / "data" / "qumran"

SOURCE_NOTE = "unreviewed machine-draft translation, Open Dead Sea (opendeadsea.org, CC BY-NC 4.0)"

# (siglum, canonical Bible book, display book name)
SCROLLS = [
    ("1Qisaa", "Isaiah",      "Isaiah (1QIsaa)"),
    ("4Q22",   "Exodus",      "Exodus (4Q22)"),
    ("4Q41",   "Deuteronomy", "Deuteronomy (4Q41)"),
    ("4Q86",   "Psalms",      "Psalms (4Q86)"),
    ("4Q114",  "Daniel",      "Daniel (4Q114)"),
]

_CLEAN_REF = re.compile(r"^\S+ (\d+):(\d+)$")


def _fetch(siglum):
    req = urllib.request.Request(
        f"{BASE}/{siglum}.json",
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def build_scroll(siglum, display_name):
    data = _fetch(siglum)
    lines = data["lines"]

    chapters = {}
    skipped = 0
    for ref, entry in lines.items():
        m = _CLEAN_REF.match(ref)
        if not m:
            skipped += 1
            continue
        chapter, verse = m.group(1), m.group(2)
        text = (entry.get("en") or "").strip()
        if not text:
            skipped += 1
            continue
        chapters.setdefault(chapter, {})[verse] = text

    total_verses = sum(len(v) for v in chapters.values())
    print(f"{display_name} ({siglum}): {len(chapters)} chapters, {total_verses} verses, {skipped} fragment-keyed/empty lines skipped")

    payload = {
        "source": f"{display_name}, Qumran -- {SOURCE_NOTE}",
        "books": {display_name: chapters},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{siglum.lower().replace(' ', '_')}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    for siglum, _book, display_name in SCROLLS:
        build_scroll(siglum, display_name)
        time.sleep(1)


if __name__ == "__main__":
    main()
