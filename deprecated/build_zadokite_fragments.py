"""
Build script: converts R.H. Charles' 1913 translation of the Fragments of a
Zadokite Work (the Damascus Document) into
data/charles/zadokite_fragments.json.

Source: https://www.pseudepigrapha.com/pseudepigrapha/zadokite.html, headed
"Translated by R. H. Charles, in R. H. Charles, ed., The Apocrypha and
Pseudepigrapha of the Old Testament in English, vol. 2: Pseudepigrapha
(Oxford: Clarendon Press, 1913): pp. 799-834" -- the same public-domain
1913 Oxford work this project's other Charles texts come from.

Chapters are marked with a dedicated `<FONT size=5>N</FONT>` tag (unlike
the roman-numeral-in-prose markers used elsewhere in this corpus), so
chapter boundaries here are unambiguous. As with the Testaments and
Assumption of Moses, each chapter is stored as one whole text block rather
than split into individual verses: most verses are cleanly numbered, but
several run across multiple unnumbered poetic/legal-clause lines, and
the risk of a continuation line being misread as a new verse (silently
shifting every later verse number in that chapter) outweighs the benefit
of finer-grained lookup.

Known source defect (verified in the raw bytes, not introduced by this
script): the page's own served bytes contain 136 literal U+FFFD
REPLACEMENT CHARACTERs scattered through the text -- likely punctuation
(dashes or ellipses marking lacunae in the fragmentary manuscript) lost in
some earlier lossy re-encoding on the site's end. These are left as-is
(not guessed at or silently dropped) since the original character cannot
be recovered from this source.

Downloads its own source -- run from anywhere:
    python deprecated/build_zadokite_fragments.py
"""
import html as html_mod
import json
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

SOURCE_URL = "https://www.pseudepigrapha.com/pseudepigrapha/zadokite.html"
OUT_DIR = Path(__file__).parent.parent / "data" / "charles"
OUT_PATH = OUT_DIR / "zadokite_fragments.json"

MARKER_RE = re.compile(r"<FONT size=5>\s*(\d+)\s*</FONT>")


def _clean(fragment):
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = html_mod.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "ScriptureBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8", errors="replace")

    start = raw.index("<FONT size=5>1</FONT>")
    end = raw.index("<HR align=left>")
    content = raw[start:end]

    matches = [(m.start(), m.end(), int(m.group(1))) for m in MARKER_RE.finditer(content)]
    if not matches:
        raise SystemExit("No chapter markers found -- source page structure may have changed.")

    chapters_raw = defaultdict(list)
    for i, (_, seg_start, num) in enumerate(matches):
        seg_end = matches[i + 1][0] if i + 1 < len(matches) else len(content)
        chapters_raw[num].append(content[seg_start:seg_end])

    chapters = {str(k): _clean(" ".join(v)) for k, v in chapters_raw.items()}
    expected = {str(i) for i in range(1, 21)}
    missing = expected - set(chapters)
    if missing:
        raise SystemExit(f"Missing chapters: {sorted(missing, key=int)} -- source page structure may have changed.")

    payload = {
        "source": (
            "Fragments of a Zadokite Work (the Damascus Document), trans. "
            "R.H. Charles (The Apocrypha and Pseudepigrapha of the Old "
            "Testament, vol. II, Oxford, 1913, public domain), pp. 799-834. "
            "The source page's served text contains 136 literal U+FFFD "
            "replacement characters (likely lost dashes/ellipses marking "
            "manuscript lacunae) that could not be recovered and are left "
            "as-is rather than guessed at."
        ),
        "books": {"Fragments of a Zadokite Work": chapters},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH} -- {len(chapters)} chapters")


if __name__ == "__main__":
    main()
