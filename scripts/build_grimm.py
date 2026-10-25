"""
The Brothers Grimm's Household Tales (Kinder- und Hausmärchen), in Margaret Hunt's translation (1884), from
Project Gutenberg (#5314) -> data/ballads/grimm.json: book "Grimm's Household Tales", a chapter a tale (1-200,
then the ten Children's Legends as 201-210, as the German editions number them), a verse a paragraph, each tale's
first led by its title in italics. The rhymes in the tales keep their lines.

(sacred-texts, the first choice for texts, has the same translation, but blocked this machine after the
Child ballads' 305 pages were fetched.)

    python scripts/build_grimm.py
"""
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "grimm" / "5314.html"
URL = "https://www.gutenberg.org/cache/epub/5314/pg5314-images.html"
OUT = ROOT / "data" / "ballads" / "grimm.json"
BOOK = "Grimm's Household Tales"


def page() -> str:
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL, headers={"User-Agent": "ScriptureBot corpus builder (personal Discord bot)"})
        CACHE.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    return CACHE.read_text(encoding="utf-8")


def clean(s: str) -> str:
    s = re.sub(r"\s+", " ", s)                          # (the file's own line wrapping)
    s = re.sub(r"(?i)<br\s*/?>\s*", "\n", s)            # (a rhyme's lines)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    lines = [x.strip() for x in s.split("\n")]
    return "\n".join(x for x in lines if x)


def main():
    t = page()
    t = t.split("THE FULL PROJECT GUTENBERG")[0]
    heads = list(re.finditer(r'(?is)<h3>\s*<a id="(chap\d+|legend\d+)"></a>\s*(.*?)</h3>', t))
    if not heads:                                       # (the ids differ for the legends: read any anchored h3)
        heads = list(re.finditer(r'(?is)<h3>\s*<a id="([^"]+)"></a>\s*(.*?)</h3>', t))
    tales = {}
    for h, nxt in zip(heads, heads[1:] + [None]):
        name = clean(h.group(2))
        m = re.match(r"(Legend\s+)?(\d+)\s+(.*)", name)
        if not m:
            continue
        n = int(m.group(2)) + (200 if m.group(1) else 0)
        title = m.group(3).strip()
        body = t[h.end():nxt.start() if nxt else len(t)]
        paras = [clean(p) for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", body)]
        paras = [p for p in paras if p]
        if not paras:
            raise SystemExit(f"tale {n} ({title}) has no text")
        paras[0] = f"*{title}*\n{paras[0]}"
        if str(n) in tales:
            raise SystemExit(f"tale {n} twice")
        tales[str(n)] = {str(i + 1): p for i, p in enumerate(paras)}
    missing = [n for n in range(1, 211) if str(n) not in tales]
    if missing:
        raise SystemExit(f"missing tales: {missing}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": "trans. Margaret Hunt (1884)",
                               "books": {BOOK: dict(sorted(tales.items(), key=lambda kv: int(kv[0])))}},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    words = sum(len(p.split()) for tale in tales.values() for p in tale.values())
    print(f"{len(tales)} tales, {words:,} words -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
