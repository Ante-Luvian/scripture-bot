"""
Pico della Mirandola's Oration on the Dignity of Man (1486), as transcribed at bactra.org (1994; the page names no
translator), into data/esoteric/pico.json as "Oration on the Dignity of Man": a paragraph a chapter, as the
Arbatel's aphorisms are, so "!verse oration on the dignity of man 1" is the opening.

    python scripts/build_pico.py
"""
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from corpus_clean import clean_corpus  # noqa: E402

CACHE = ROOT / "scripts" / ".cache" / "pico" / "oration.html"
OUT = ROOT / "data" / "esoteric" / "pico.json"
URL = "https://bactra.org/Mirandola/"


def main() -> None:
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL, headers={"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot)"})
        CACHE.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    t = CACHE.read_bytes().decode("utf-8", "replace")
    t = re.sub(r"(?is)<head.*?</head>|<script.*?</script>|<h\d[^>]*>.*?</h\d>", " ", t)
    t = re.sub(r"(?is)<address.*?</address>|<hr.*", " ", t)          # (the page's credits, after the text)
    t = re.sub(r"(?i)<(i|em)>(.*?)</\1>", lambda m: f"*{m.group(2).strip()}*" if m.group(2).strip() else " ", t)
    paras = []
    for p in re.split(r"(?i)<p\b[^>]*>|<br\s*/?>\s*<br\s*/?>", t):
        s = html.unescape(re.sub(r"<[^>]+>", " ", p)).replace("\xa0", " ")
        s = s.replace("``", "“").replace("''", "”").replace(" --- ", " — ").replace("---", "—")
        s = re.sub(r"\s+", " ", s).strip()
        s = re.sub(r"\s+([,.;:])", r"\1", s)
        s = re.sub(r"^(?:Oration on the Dignity of Man\s*)+(?:Giovanni Pico della Mirandola\s*)?", "", s).strip()
        if s and not re.fullmatch(r"[*\s]+", s):
            paras.append(s)
    if not paras or not paras[0].startswith("Most esteemed Fathers"):
        raise SystemExit(f"unexpected start: {paras[:1]}")
    book = {str(i + 1): {"1": p} for i, p in enumerate(paras)}
    src = "Pico della Mirandola (1486), in English translation"     # (bactra.org names no translator)
    payload = {"source": src, "books": {"Oration on the Dignity of Man": book},
               "book_sources": {"Oration on the Dignity of Man": src}}
    clean_corpus(payload, "esoteric/pico.json")
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  Oration on the Dignity of Man: {len(book)} paragraphs, {sum(len(p.split()) for p in paras):,} words")
    print("  last:", paras[-1][-160:])


if __name__ == "__main__":
    main()
