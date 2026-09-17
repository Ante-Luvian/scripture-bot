"""
Build script: converts R.H. Charles' translation of The Ascension of Isaiah
into data/charles/ascension_of_isaiah.json.

Source text: https://www.earlychristianwritings.com/text/ascension.html
(same site and same page pattern as text/patriarchs-charles.html, which
this project's testaments_of_twelve_patriarchs.json already comes from).
The site's own index page (ascension.html) labels this text "English
Translation (R. H. Charles)" -- Charles' 1900 translation (The Ascension of
Isaiah, London: Adam & Charles Black), public domain.

Unlike the Testaments and the Assumption of Moses, this source text is
already segmented into numbered verses per chapter (each chapter's first
paragraph is verse 1; subsequent paragraphs begin "N. ..."), so this is
stored at full chapter/verse granularity rather than as whole-chapter
blocks.

Downloads its own source -- run from anywhere:
    python deprecated/build_ascension_of_isaiah.py
"""
import html as html_mod
import json
import re
import urllib.request
from pathlib import Path

SOURCE_URL = "https://www.earlychristianwritings.com/text/ascension.html"
OUT_DIR = Path(__file__).parent.parent / "data" / "charles"
OUT_PATH = OUT_DIR / "ascension_of_isaiah.json"


def _clean(fragment):
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = html_mod.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "ScriptureBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8", errors="replace")

    start = raw.index("<p>CHAPTER 1</p>")
    end = raw.index('<hr width="50%">', start)
    content = raw[start:end]

    chapter_re = re.compile(r"<p>CHAPTER (\d+)</p>", re.IGNORECASE)
    markers = list(chapter_re.finditer(content))
    if len(markers) != 11:
        raise SystemExit(f"Expected 11 chapters, found {len(markers)} -- source page structure may have changed.")

    para_re = re.compile(r"<p>(.*?)</p>", re.DOTALL | re.IGNORECASE)
    chapters = {}
    for i, m in enumerate(markers):
        chap_num = m.group(1)
        seg_start = m.end()
        seg_end = markers[i + 1].start() if i + 1 < len(markers) else len(content)
        segment = content[seg_start:seg_end]

        verses = {}
        vnum = 1
        for pm in para_re.finditer(segment):
            text = _clean(pm.group(1))
            if not text:
                continue
            vm = re.match(r"^(\d+)\.\s*(.*)", text)
            if vm:
                verses[vm.group(1)] = vm.group(2)
            else:
                verses[str(vnum)] = text
                vnum += 1
        chapters[chap_num] = verses

    payload = {
        "source": (
            "The Ascension of Isaiah, trans. R.H. Charles (London: Adam & "
            "Charles Black, 1900, public domain)"
        ),
        "books": {"Ascension of Isaiah": chapters},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(len(v) for v in chapters.values())
    print(f"Wrote {OUT_PATH} -- {len(chapters)} chapters, {total} verses")
    for n in sorted(chapters, key=int):
        print(f"  ch.{n}: {len(chapters[n])} verses")


if __name__ == "__main__":
    main()
