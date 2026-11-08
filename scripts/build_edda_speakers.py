"""
The Poetic Edda (Bellows, 1923; data/norse/poetic_edda.json): who speaks each stanza of the dialogue poems, and two
repairs, from Bellows's text on archive.sacred-texts.com (neu/poe/), whose pages keep his speaker headings ("Othin
spake:") that the bot's text lost. Pages cached in scripts/.cache/sacred_poe/.

  - data/norse/edda_speakers.json: {poem: {stanza: speaker}} for every poem with headings, a stanza given to a
    speaker only when his heading stands directly before it (a stanza with none, narration, has none). For !odin
    (bot_commands/oracles.py), which draws only Othin's own words: his stanzas here (as Othin, and as "Harbarth"
    and "the ferryman" in Harbarthsljoth), Grimnismol whole (his monologue as Grimnir), and Hovamol.
  - Harbarthsljoth had only stanzas 1-16 of its 60: 17-60 added from the page (1-16 kept: the page has a typo,
    "if across the sound" for "If").
  - Long lines printed over two lines in the bot's text ("...on the farther shore of the / sound?") joined: a line
    beginning with a small letter is the rest of the line before (every line of Bellows's begins with a capital).
    20 of them, in 8 poems.

    python scripts/build_edda_speakers.py
"""
import html
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDDA = ROOT / "data" / "norse" / "poetic_edda.json"
OUT = ROOT / "data" / "norse" / "edda_speakers.json"
CACHE = ROOT / "scripts" / ".cache" / "sacred_poe"
BASE = "https://archive.sacred-texts.com/neu/poe/"
UA = {"User-Agent": "Mozilla/5.0 (ScriptureBot corpus builder, personal Discord bot)"}
FIRST_PAGE = 3                                       # (poe03.htm is Voluspo; the poems follow in the bot's order)


def page(n: int) -> str:
    path = CACHE / f"poe{n:02d}.htm"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(urllib.request.urlopen(urllib.request.Request(f"{BASE}poe{n:02d}.htm", headers=UA),
                                                timeout=60).read())
        time.sleep(1)
    return path.read_text(encoding="latin-1")


def _curly(s: str) -> str:
    s = re.sub(r'(^|[\s(\[—-])"', "\\1“", s)
    s = s.replace('"', "”")
    s = re.sub(r"(^|[\s(\[—-])'", "\\1‘", s)
    return s.replace("'", "’")


def _text(raw: str) -> str:
    t = raw[:raw.find("Next:")] if "Next:" in raw else raw                         # (the page's footer)
    t = re.sub(r'(?is)<font size="-1" color="green">.*?</font>', " ", t)             # (Bellows's notes)
    t = re.sub(r"(?is)<p>\s*<a name=[^>]*>.*?</a>\s*</p>", " ", t)                  # (page numbers)
    t = re.sub(r"(?i)<br\s*/?>", "\n", t)
    t = re.sub(r"(?i)</p>", "\n\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"(?m)^\s*(?:So|S0)\.", "50.", t)                                  # (the page's "So." for 50.)


def stanzas(raw: str) -> dict:
    """{number: text}: a stanza runs across page breaks, to the next number or the next speaker's heading."""
    text = re.sub(r"(?m)^\s*[A-Z][\w\- ']{1,30} spake:\s*$", "\x00", _text(raw))
    out, cur, open_ = {}, None, False
    for line in text.split("\n"):
        s = line.strip()
        m = re.match(r"^(\d{1,3})[.,] (.*)$", s)                                     # (the page's "1," and "38,")
        if m and (cur is None or int(m.group(1)) == int(cur) + 1):
            cur, open_ = m.group(1), True
            out[cur] = [m.group(2).strip()]
        elif "\x00" in s:
            open_ = False
        elif s and open_ and not re.match(r"^p\. \d+$", s):
            out[cur].append(s)
    return {k: _curly("\n".join(v)) for k, v in out.items()}


def speakers(raw: str) -> dict:
    """{number: speaker} where a "X spake:" heading stands directly before the stanza's number."""
    text = re.sub(r"\s+", " ", _text(raw))
    out = {}
    for m in re.finditer(r"(?:([A-Z][\w\- ']{1,30}?) spake:\s*)?(?<![\d.])(\d{1,3})[.,] (?=[\"“'A-Z.])", text):
        if m.group(1):
            # (a section's title in capitals can run into the name: "GROUGALDR GROA'S SPELL Svipdag")
            name = re.sub(r"^(?:[A-Z’']{2,}\s+)+", "", m.group(1).strip())
            out.setdefault(m.group(2), name)
    return out


def unwrap(text: str) -> str:
    return re.sub(r"\n(?=[a-z])", " ", text)


def main() -> None:
    raw_edda = EDDA.read_text(encoding="utf-8")
    edda = json.loads(raw_edda)
    books = edda["books"]
    poems = list(books)
    table = {}
    for i, poem in enumerate(poems):
        raw = page(FIRST_PAGE + i)
        sp = speakers(raw)
        if sp:
            table[poem] = dict(sorted(sp.items(), key=lambda kv: int(kv[0])))
        if poem == "Harbarthsljoth":
            got = stanzas(raw)
            if len(got) != 60:
                raise SystemExit(f"unexpected: Harbarthsljoth parsed {len(got)} stanzas")
            for n in range(len(books[poem]) + 1, 61):
                books[poem][str(n)] = {"1": got[str(n)]}
    joined = 0
    for poem, chapters in books.items():
        for verses in chapters.values():
            new = unwrap(verses["1"])
            joined += new != verses["1"]
            verses["1"] = new
    indent = 2 if raw_edda.startswith('{\n  "') else 1
    EDDA.write_text(json.dumps(edda, ensure_ascii=False, indent=indent), encoding="utf-8")
    OUT.write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  Harbarthsljoth: {len(books['Harbarthsljoth'])} stanzas; {joined} stanzas had a wrapped line joined")
    for poem, sp in table.items():
        who = {}
        for s in sp.values():
            who[s] = who.get(s, 0) + 1
        print(f"  {poem}: {who}")


if __name__ == "__main__":
    main()
