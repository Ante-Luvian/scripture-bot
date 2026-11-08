"""Lee M. Hollander's Old Norse Poems (1936), the eddic and skaldic poems outside the Poetic Edda, from
archive.sacred-texts.com/neu/onp/ (pages cached in scripts/.cache/sacred_onp): data/norse/old_norse_poems.json.

Each poem is a book, each of Hollander's numbered stanzas a chapter. Hollander heads each speech with its speaker
("ÓTHIN", "GESTUMBLINDI said:"); in a poem with more than one speaker, each speech in a stanza is a verse of its own,
begun with the speaker's name ("Óthin: “What dreams be these...”") where Hollander heads that speech, so !odin can
take Odin's speeches alone (bot_commands/oracles.py ODIN_HOLLANDER; the Riddles of King Heithrek: verse 1 Odin's
riddle, as Gestumblindi; verse 2 the king's answer).

    python scripts/build_old_norse_poems.py
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "sacred_onp"
OUT = ROOT / "data" / "norse" / "old_norse_poems.json"
UA = "Mozilla/5.0 (ScriptureBot corpus builder, personal Discord bot)"
SOURCE = "trans. Lee M. Hollander, Old Norse Poems (1936)"

# page -> the book's name (Hollander's own Old Norse titles, unaccented as Bellows's are in the bot)
POEMS = {
    "onp03": "Biarkamol", "onp04": "The Lay of Ingiald", "onp05": "Vikarsbalkr", "onp06": "Hialmar's Death Song",
    "onp07": "Hervararkvitha", "onp08": "Hlothskvitha", "onp09": "The Lay of Innstein",
    "onp10": "Hildibrand's Death Song", "onp11": "Haraldskvaethi", "onp12": "Eiriksmol", "onp13": "Hakonarmol",
    "onp14": "Darratharlioth", "onp15": "Buslubaen", "onp17": "Heithreksgatur",
    "onp18": "Solarlioth",
}
# (left out: onp16, Tryggthamol, a truce formula from the Icelandic law set out as prose, not a poem)
# Hákonarmál names its speakers in the verse ("said fierce Skogul"); Hollander's few headings there run on past the
# speech they head (his "SKOGUL" stands over Bragi's words), so that poem gets no speaker labels.
UNLABELLED = {"Hakonarmol"}


def fetch(page):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{page}.htm"
    if not path.exists():
        url = f"https://archive.sacred-texts.com/neu/onp/{page}.htm"
        path.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}),
                                                timeout=60).read())
        time.sleep(1)
    return path.read_text(encoding="utf-8", errors="replace")


def clean(cell):
    cell = re.sub(r"<A NAME=\"fr_\d+\"></A><A HREF=\"#note_\d+\"><FONT SIZE=1>\d+</FONT></A>", "", cell, flags=re.I)
    cell = re.sub(r"<!-+page \d+-+>|<A NAME=\"page_\d+\">.*?</A>", "", cell, flags=re.I | re.S)
    cell = re.sub(r"<BR\s*/?>", "\n", cell, flags=re.I)
    cell = html.unescape(re.sub(r"<[^>]+>", "", cell)).replace("\xa0", " ")
    lines = [re.sub(r"[ \t\r]+", " ", l).rstrip() for l in cell.split("\n")]
    lines = [l.lstrip(" ") for l in lines]                              # (keeps Hollander's em-space indents)
    # (his "* * *", a gap in the manuscript, as Bellows prints one: Discord would read the stars as markup)
    lines = [".  .  .  .  .  .  .  ." if re.fullmatch(r"[\s*]+", l) and "*" in l else l for l in lines]
    return "\n".join(l for l in lines if l.strip())


def speaker_name(label):
    """ "GESTUMBLINDI said:" -> "Gestumblindi"; "ÓTHIN" -> "Óthin"."""
    if not re.search(r"[^\W\d_]", label):
        return ""                                     # ("* * *": a gap, no speaker)
    if label.strip().startswith("("):
        return label.strip()
    label = re.sub(r"\s*(said|spake|spoke|quoth|sang)?\s*:?\s*~?\s*$", "", label.strip(), flags=re.I)
    return " ".join(w.capitalize() if w.isupper() else w for w in label.split())


def parse(page):
    """[(number or None, speaker or None, text)] for each row of the poem's tables, in order."""
    body = page[:page.find("Footnotes")] if "Footnotes" in page else page
    rows = []
    for table in re.findall(r"<TABLE.*?</TABLE>", body, re.S | re.I):
        for tr in re.findall(r"<TR>(.*?)</TR>", table, re.S | re.I):
            cells = re.findall(r"<TD([^>]*)>(.*?)</TD>", tr, re.S | re.I)
            if len(cells) == 1 and "colspan" in cells[0][0].lower():
                rows.append((None, speaker_name(clean(cells[0][1])), None))
            elif len(cells) == 2:
                num = clean(cells[0][1]).strip()
                rows.append((num if re.fullmatch(r"\d+", num) else None, None, clean(cells[1][1])))
    return rows


def build():
    out = {}
    for page, book in POEMS.items():
        rows = parse(fetch(page))
        named = {s for _, s, _ in rows if s and not s.startswith("(")}
        stanzas, current, last, direction = {}, None, None, None
        for num, who, text in rows:
            if who and who.startswith("("):            # a stage direction: a line of the next speech
                direction = who
                continue
            if who:
                current = who
                continue
            if who == "":                             # ("* * *", a gap in the manuscript)
                continue
            if num:
                last = num
            if last is None or not re.search(r"[^\W\d_]", text or ""):        # (or "* * *", a gap)
                continue
            # (the last riddle names its speakers in a line of prose, not a heading: "Then Gestumblindi said:",
            # "The king answered:")
            lead = re.match(r"(?:Then )?(Gestumblindi|The king) (?:said|answered):\n", text)
            if lead:
                current = {"The king": "Heithrek"}.get(lead.group(1), lead.group(1))
                text = text[lead.end():]
            verses = stanzas.setdefault(last, {})
            label = f"{current}: " if current and len(named) > 1 and book not in UNLABELLED else ""
            if direction:
                text, direction = f"{direction}\n{text}", None
            verses[str(len(verses) + 1)] = label + text
            current = None          # (a heading names the speech under it only: the poems run narration and
                                    #  speech together, and a name carried on would put words in the wrong mouth)
        out[book] = stanzas
        print(f"{book}: {len(stanzas)} stanzas, speakers {sorted(named)}")
    OUT.write_text(json.dumps({"source": SOURCE, "books": out}, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build()
