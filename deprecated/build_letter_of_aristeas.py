"""
Build script: converts R.H. Charles' 1913 translation of the Letter of
Aristeas into data/charles/letter_of_aristeas.json.

Source: attalus.org's transcription -- https://www.attalus.org/translate/aristeas1.html
and aristeas2.html (sections 1-182 and 183-322). The page's own header
states "This translation is by R.H.Charles (1913)" -- the same public-domain
1913 Oxford work (The Apocrypha and Pseudepigrapha of the Old Testament)
this project's other Charles texts come from.

The source marks each of the work's 322 traditional sections with an
explicit `<A CLASS="ref" NAME="N">[N]</A>` anchor inline in continuous
prose -- unlike the Testaments/Assumption of Moses (where inline numbers
are bare, ambiguous digits), these are unambiguous tagged markers, so this
is split at full section granularity.

The Letter of Aristeas has no chapter divisions, only 322 sequential
sections. Following this project's convention for single-division works
(see scripture_lookup.py's Articles of Faith handling), it is stored as a
single chapter "1" with each section as a "verse".

Downloads its own source -- run from anywhere:
    python deprecated/build_letter_of_aristeas.py
"""
import html as html_mod
import json
import re
import urllib.request
from pathlib import Path

URLS = [
    "https://www.attalus.org/translate/aristeas1.html",
    "https://www.attalus.org/translate/aristeas2.html",
]
OUT_DIR = Path(__file__).parent.parent / "data" / "charles"
OUT_PATH = OUT_DIR / "letter_of_aristeas.json"

MARKER_RE = re.compile(r'<A CLASS="ref" NAME="(\d+)">\[\d+\]</A>')
GREEK_LINK_RE = re.compile(r'<A CLASS="Latin"[^>]*>\s*G\s*</A>')


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def main():
    sections = {}
    for url in URLS:
        raw = _fetch(url)
        start = raw.index("<HR>")
        content = raw[start:]
        content = GREEK_LINK_RE.sub("", content)

        markers = list(MARKER_RE.finditer(content))
        for i, m in enumerate(markers):
            num = m.group(1)
            seg_start = m.end()
            seg_end = markers[i + 1].start() if i + 1 < len(markers) else len(content)
            text = content[seg_start:seg_end]
            text = re.sub(r"<[^>]+>", "", text)
            text = html_mod.unescape(text)
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                sections[num] = text

    expected = {str(i) for i in range(1, 323)}
    missing = expected - set(sections)
    if missing:
        raise SystemExit(f"Missing sections: {sorted(missing, key=int)} -- source page structure may have changed.")

    payload = {
        "source": (
            "Letter of Aristeas, trans. R.H. Charles (The Apocrypha and "
            "Pseudepigrapha of the Old Testament, vol. II, Oxford, 1913, "
            "public domain)"
        ),
        "books": {"Letter of Aristeas": {"1": sections}},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH} -- {len(sections)} sections")


if __name__ == "__main__":
    main()
