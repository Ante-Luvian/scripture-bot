"""
Build script: converts English machine-draft translations of several core
Dead Sea Scrolls sectarian texts from the Open Dead Sea project into
data/qumran/*.json.

Source: https://opendeadsea.org/ (data mirrored at
https://github.com/apocalypse-press/opendeadsea-mss), a project of Jesus
People SF and Apocalypse Press, built with a Cohere AI compute grant.
Hebrew/Aramaic wording is Martin G. Abegg, Jr.'s ETCBC/dss diplomatic
transcription (CC BY-NC 4.0, verified directly against the repo's own
LICENSE file). Open Dead Sea's own English machine-draft dataset is
separately CC BY-NC 4.0 (verified directly against
github.com/apocalypse-press/opendeadsea-mss/DATA_LICENSE.md).

IMPORTANT -- these are machine drafts, not finished scholarly translations.
Per Open Dead Sea's own README: "Do not treat the machine drafts as
finished scholarly translations." Every line here was produced by an LLM
(Cohere Command A) grounded against the Hebrew transcription and lexical
data, then queued for human community review -- as of this build, none
have completed that review yet ("status": "first-draft" on every witness).
This build carries that caveat into the "source" field of every file it
writes, and it is surfaced to users via the normal scripture-card footer
like every other translation source in this bot.

One scroll = one "document" here (Hodayot = 1QHa, Damascus Document = CD,
etc.) rather than merging in every overlapping fragmentary duplicate copy
(1Q35 and 4Q427-432 for Hodayot; 4Q266-273/5Q12/6Q15 for the Damascus
Document). Reconstructing a genuine critical composite across witnesses is
real textual-critical scholarly work (e.g. Baumgarten's DJD volume for the
Damascus Document); it is not something to approximate here. Each chosen
witness is the one already cited with a real, dense, column:line numbering
that matches how it's cited in scholarship (e.g. "CD 9:1", "1QHa 10:10").

A small number of lines per scroll belong to loose fragments the
reconstruction hasn't placed in the column sequence yet (ref format like
"1QHa fA1:1" instead of "1QHa 10:10"); those are skipped, not merged in
under a made-up chapter number.

Downloads its own source -- run from anywhere:
    python deprecated/build_open_dead_sea.py
"""
import json
import re
import time
import urllib.request
from pathlib import Path

BASE = "https://opendeadsea.org/data/translations"
OUT_DIR = Path(__file__).parent.parent / "data" / "qumran"

SOURCE_NOTE = (
    "English machine-draft translation (Cohere Command A), status: first "
    "draft, not yet human-reviewed -- Open Dead Sea, a project of Jesus "
    "People SF and Apocalypse Press, built with a Cohere AI compute grant "
    "(opendeadsea.org, CC BY-NC 4.0). Hebrew/Aramaic wording: Martin G. "
    "Abegg, Jr.'s ETCBC/dss diplomatic transcription (CC BY-NC 4.0)."
)

# (siglum, canonical book name)
SCROLLS = [
    ("1QHa", "Hodayot"),
    ("CD", "Damascus Document"),
    ("1QS", "Community Rule"),
    ("1QM", "War Scroll"),
    ("1QpHab", "Pesher Habakkuk"),
    ("1QSa", "Rule of the Congregation"),
    ("1QSb", "Rule of Blessings"),
]

_CLEAN_REF = re.compile(r"^\S+ (\d+):(\d+)$")


def _fetch(siglum):
    req = urllib.request.Request(
        f"{BASE}/{siglum}.json",
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def build_scroll(siglum, name):
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
    print(f"{name} ({siglum}): {len(chapters)} chapters, {total_verses} verses, {skipped} unplaced/empty lines skipped")

    payload = {
        "source": f"{name} ({siglum}), Qumran -- {SOURCE_NOTE}",
        "books": {name: chapters},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{siglum.lower()}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    for siglum, name in SCROLLS:
        build_scroll(siglum, name)
        time.sleep(1)


if __name__ == "__main__":
    main()
