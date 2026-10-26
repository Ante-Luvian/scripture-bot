"""
Shakespeare's plays and poems -> data/shakespeare/shakespeare.json, from the Folger Shakespeare (ed. Barbara Mowat
and Paul Werstine), the Folger Shakespeare Library's TEI downloads (folger.edu/explore/shakespeares-works/download):

  the 38 plays: a chapter a scene, "act.scene" ("3.1"); the Prologue (or Induction) "0" (the Shrew's two
  scenes "0.1", "0.2"), a chorus before an act "act.0" ("2.0"), the Epilogue "6" (after the fifth act). A
  passage is a run of speeches keyed by its first line in Folger's own line numbers, so "Hamlet 3.1:64" or
  "Hamlet 3.1.64" is the passage holding line 64 ("line_chunked"). Speakers in bold, stage directions in
  italics, verse a line a line, prose run together; the end of a long line printed under it joined back on.
  the Sonnets: a chapter a sonnet ("Shakespeare's Sonnets 18"); Venus and Adonis, Lucrece and the Phoenix and
  Turtle: one chapter each, cited by line ("Venus and Adonis 1"), the dedication (and Lucrece's Argument) at
  line 0.

Left out: Folger's variant readings (<app>), page furniture, the cast lists, the Latin epigraph of Venus and
Adonis, and the publisher's preface to Troilus and Cressida (not Shakespeare's).

    python scripts/build_shakespeare.py
"""
import io
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "shakespeare"
OUT = ROOT / "data" / "shakespeare"
URL = "https://flgr.sh/txtfssAllxml"
UA = {"User-Agent": "ScriptureBot corpus builder (personal Discord bot)"}
SOURCE = "Folger edition"                 # (the owner: no more credit than that)

# Folger's file -> the book's name here (a title another work already has takes the author's name, as
# "Sophocles: Electra" does: Suetonius's Julius Caesar; Plutarch's Pericles keeps "Pericles")
TITLES = {
    "AWW": "All's Well That Ends Well", "Ant": "Antony and Cleopatra", "AYL": "As You Like It",
    "Err": "The Comedy of Errors", "Cor": "Coriolanus", "Cym": "Cymbeline", "Ham": "Hamlet",
    "1H4": "Henry IV, Part 1", "2H4": "Henry IV, Part 2", "H5": "Henry V", "1H6": "Henry VI, Part 1",
    "2H6": "Henry VI, Part 2", "3H6": "Henry VI, Part 3", "H8": "Henry VIII", "JC": "Shakespeare: Julius Caesar",
    "Jn": "King John", "Lr": "King Lear", "LLL": "Love's Labor's Lost", "Mac": "Macbeth",
    "MM": "Measure for Measure", "MV": "The Merchant of Venice", "Wiv": "The Merry Wives of Windsor",
    "MND": "A Midsummer Night's Dream", "Ado": "Much Ado About Nothing", "Oth": "Othello",
    "Per": "Pericles, Prince of Tyre", "R2": "Richard II", "R3": "Richard III", "Rom": "Romeo and Juliet",
    "Shr": "The Taming of the Shrew", "Tmp": "The Tempest", "Tim": "Timon of Athens", "Tit": "Titus Andronicus",
    "Tro": "Troilus and Cressida", "TN": "Twelfth Night", "TGV": "The Two Gentlemen of Verona",
    "TNK": "The Two Noble Kinsmen", "WT": "The Winter's Tale",
    "Son": "Shakespeare's Sonnets", "Ven": "Venus and Adonis", "Luc": "Lucrece", "PhT": "The Phoenix and Turtle",
}
POEMS = {"Son", "Ven", "Luc", "PhT"}
SKIP = {"app", "fw", "ptr", "pb", "lb", "interp", "interpGrp", "anchor", "head", "epigraph", "note"}
PASSAGE, LONG = 30, 40          # a passage of speeches is about 30 lines; a speech over 40 is cut


def files() -> dict:
    """Folger's abbreviation -> its XML, downloaded (a zip of zips) once."""
    xml_dir = CACHE / "xml"
    if not any(xml_dir.glob("*.xml")):
        xml_dir.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL, headers=UA)
        outer = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(req, timeout=300).read()))
        for name in outer.namelist():
            if name.endswith(".zip") and "__MACOSX" not in name and "/._" not in name:
                inner = zipfile.ZipFile(io.BytesIO(outer.read(name)))
                for x in inner.namelist():
                    if x.endswith(".xml") and "__MACOSX" not in x and "/._" not in x.replace("\\", "/"):
                        (xml_dir / Path(x).name).write_bytes(inner.read(x))
    return {p.stem: p for p in xml_dir.glob("*.xml")}


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def words(el) -> str:
    """The text of an element's words, spaces and punctuation, its variant readings and page furniture left out."""
    out = []

    def walk(e):
        t = local(e.tag)
        if t == "lb":                             # (a printed line break: a space)
            out.append(" ")
        if t in SKIP:
            return
        if t in ("w", "c", "pc") and e.text:
            out.append(e.text)
        for k in e:
            walk(k)
    walk(el)
    return spaced("".join(out))


def spaced(s: str) -> str:
    """Runs of space as one, and a space after a comma Folger left without (King John 3.4: "France,Louis")."""
    return re.sub(r"([,;:])(?=[A-Z][a-z])", r"\1 ", re.sub(r"\s+", " ", s)).strip()


def chapter_of(div_type: str, n: str, act: str) -> str:
    """A div's chapter here: "3.1", "0" (prologue, induction), "0.1" (the Shrew's induction), "2.0" (a chorus
    before act 2), "6" (the Epilogue)."""
    if div_type == "scene":
        return f"{'0' if act == 'IND' else act}.{n}"
    if div_type in ("prologue", "induction"):
        return "0"
    if div_type == "chorus":
        return f"{act}.0"
    if div_type == "epilogue":                   # (after the fifth act, so a number like the rest)
        return "6"
    raise ValueError(f"unexpected div {div_type} {n}")



def heading(chap: str, play_has_induction: bool) -> str:
    if chap == "0":
        return "Induction" if play_has_induction else "Prologue"
    if chap == "6":
        return "Epilogue"
    a, s = chap.split(".")
    if a == "0":
        return f"Induction, Scene {s}"
    if s == "0":
        return f"Act {a}, Chorus"
    return f"Act {a}, Scene {s}"


def play(path: Path) -> dict:
    """{chapter: {first line: passage}} for one play."""
    root = ET.parse(path).getroot()
    body = next(e for e in root.iter() if local(e.tag) == "body")
    has_induction = any(local(e.tag).startswith("div") and e.get("type") == "induction" for e in body.iter())
    # events, in order: (chapter, kind, ...): ("speaker", name) ("stage", text) ("line", number, text, prose)
    events = []
    turned = set()              # (chapter, line): the end of a long line, printed under it -- joined back on

    def walk(e, chap, act):
        t = local(e.tag)
        if t in SKIP:
            return
        if t in ("div1", "div2"):
            kind, n = e.get("type"), e.get("n", "")
            if kind == "preface":                   # (Troilus: the publisher's epistle, not Shakespeare's)
                return
            if kind == "act" and t == "div1":
                act = n
            elif kind == "induction" and t == "div1" and any(local(k.tag) == "div2" for k in e):
                act = "IND"                          # (the Shrew: an induction in two scenes)
            elif kind == "act":                     # (a stray act div2: treat as its scenes' container)
                act = n
            else:
                chap = chapter_of(kind, n, act)
                events.append((chap, "start"))
            for k in e:
                walk(k, chap, act)
            return
        if t in ("stage", "label"):                # (a label: "Song.", "His oration to his soldiers.")
            text = words(e)
            if text and chap:
                events.append((chap, "stage", text))
            return
        if t == "speaker":
            events.append((chap, "speaker", words(e)))
            return
        if t == "sp":
            events.append((chap, "sp"))
            for k in e:
                walk(k, chap, act)
            events.append((chap, "spend"))
            return
        if t == "milestone" and e.get("unit") == "ftln":
            m = re.search(r"(\d+)$", e.get("n", ""))
            events.append((chap, "line", int(m.group(1)) if m else None, "prose" in (e.get("ana") or "")))
            if "turnunder" in (e.get("rend") or "") and m:
                turned.add((chap, int(m.group(1))))
            return
        if t in ("w", "c", "pc"):
            if e.text:
                m = re.search(r"(\d+)$", (e.get("n") or "").split(" ")[0])
                # (only a word starts a line: a comma in As You Like It 1.1.106 is numbered 1.1.9)
                events.append((chap, "text", e.text, int(m.group(1)) if m and t == "w" else None,
                               t == "pc" and e.text in "(“‘["))
            return
        for k in e:
            walk(k, chap, act)

    walk(body, None, None)
    # events -> per chapter, a list of speeches: {"speaker", "items": [("line", n, text, prose) | ("stage", text)]}
    chapters = {}
    cur, prose, opening = None, False, ""
    for ev in events:
        chap = ev[0]
        if chap is None:
            continue
        speeches = chapters.setdefault(chap, [])
        if ev[1] in ("start", "spend"):
            cur = None
        elif ev[1] == "sp":
            cur = {"speaker": None, "items": []}
            speeches.append(cur)
        elif ev[1] == "speaker":
            cur["speaker"] = ev[2]
        elif ev[1] == "stage":
            # a direction between speeches stands alone; inside one, it stays there
            if cur is None:
                speeches.append({"speaker": None, "items": [("stage", ev[2])]})
            else:
                cur["items"].append(("stage", ev[2]))
        elif ev[1] == "line":
            prose = ev[3]
        elif ev[1] == "text":
            # an opening bracket or quotation mark goes with the word after it (it may be the next line's)
            if ev[4]:
                opening += ev[2]
                continue
            if opening and ev[3] is not None:
                ev, opening = (chap, "text", opening + ev[2], ev[3], False), ""
            # each word carries its line's number (a song's words have no line marker before them)
            if cur is None:
                cur = {"speaker": None, "items": []}
                speeches.append(cur)
            line = cur["items"][-1] if cur["items"] and cur["items"][-1][0] == "line" else None
            if line is not None and (chap, ev[3]) in turned and line[1] != ev[3]:
                line[2] += " "
                ev = (chap, "text", ev[2], line[1])
            if line is None or (ev[3] is not None and line[1] != ev[3]):
                line = ["line", ev[3], "", prose]
                cur["items"].append(line)
            line[2] += ev[2]
    out = {}
    for chap, speeches in chapters.items():
        out[chap] = passages(chap, speeches, heading(chap, has_induction), path.stem)
        # each line by its number, with who speaks it and whether it's prose ([speaker, text, 1 if prose, the
        # speech's number in the scene] each; two for a line two people share)
        for k, sp in enumerate(speeches):
            for it in sp["items"]:
                text = spaced(it[2]) if it[0] == "line" else ""
                if text and it[1] is not None:
                    LINES.setdefault(TITLES[path.stem], {}).setdefault(chap, {}).setdefault(
                        str(it[1]), []).append([sp["speaker"] or "", text, int(bool(it[3])), k])
    return out


# !shakespeare's dice (bot_commands/oracles.py): every line of the plays -> data/shakespeare/lines.json,
# {play: {scene: {line: [[speaker, text, prose, speech], ...]}}}
LINES = {}
# the plays in the First Folio's order (1623), then the two it left out, Pericles as the Third Folio added it
# (1664) and the Two Noble Kinsmen
FOLIO = ["Tmp", "TGV", "Wiv", "MM", "Err", "Ado", "LLL", "MND", "MV", "AYL", "Shr", "AWW", "TN", "WT",
         "Jn", "R2", "1H4", "2H4", "H5", "1H6", "2H6", "3H6", "R3", "H8",
         "Tro", "Cor", "Tit", "Rom", "Tim", "JC", "Mac", "Ham", "Lr", "Oth", "Ant", "Cym",
         "Per", "TNK"]


def speech_text(sp: dict, items: list) -> str:
    """A speech (or a piece of a long one) as text: the speaker in bold, verse a line a line, prose run on."""
    rows = []
    prose = []

    def flush():
        if prose:
            rows.append(" ".join(prose))
            prose.clear()
    for it in items:
        if it[0] == "stage":
            flush()
            rows.append(f"*{it[1]}*")
        else:
            text = spaced(it[2])
            if not text:
                continue
            if it[3]:
                prose.append(text)
            else:
                flush()
                rows.append(text)
    flush()
    if sp["speaker"]:
        name = f"**{sp['speaker']}**"
        if rows and re.fullmatch(r"\*,[^*]*\*", rows[0]):      # ("KING, aside": the direction goes with the name)
            how = rows.pop(0)[2:-1].strip()
            name += f", *{how}*" if how else ""                 # (Richard III 4.4 has two bare commas)
        rows = [f"{name} {rows[0]}"] + rows[1:] if rows else [name]   # (on the first line: a shorter page)
    return "\n".join(rows)


def numbers(items: list) -> list:
    return [it[1] for it in items if it[0] == "line" and it[1] is not None]


def passages(chap: str, speeches: list, title: str, play_id: str) -> dict:
    """Speeches -> {first line: passage}: runs of speeches of about PASSAGE lines, a speech over LONG lines cut
    into pieces of about PASSAGE (at a line); stage directions with no line go with the passage they open (or the
    one before, at a scene's end)."""
    pieces = []                                   # (speech, items) pieces, each with its line numbers
    for sp in speeches:
        items = sp["items"]
        if len(numbers(items)) > LONG:
            n = len(numbers(items))
            size = -(-n // -(-n // PASSAGE))
            chunk, count = [], 0
            for it in items:
                chunk.append(it)
                if it[0] == "line":
                    count += 1
                    if count == size:
                        pieces.append((sp, chunk))
                        chunk, count = [], 0
            if chunk:
                pieces.append((sp, chunk))
        else:
            pieces.append((sp, items))
    out, run, run_lines = {}, [], 0

    def flush():
        nonlocal run, run_lines
        if not run:
            return
        nums = [n for _, items in run for n in numbers(items)]
        # (a long speech's later pieces don't repeat the speaker, unless one opens the passage)
        text = "\n\n".join(speech_text(sp if i == 0 or sp is not run[i - 1][0] else {"speaker": None}, items)
                           for i, (sp, items) in enumerate(run))
        if not nums:                              # (a direction after the last line: with the passage before)
            if out:
                last = list(out)[-1]
                out[last] += "\n\n" + text
            else:
                out["0"] = text
        else:
            key = str(min(nums))
            if key in out:
                raise ValueError(f"{play_id} {chap}: two passages at line {key}: {nums} after {list(out)}")
            out[key] = text
        run, run_lines = [], 0

    for sp, items in pieces:
        n = len(numbers(items))
        if run and run_lines and run_lines + n > PASSAGE:
            flush()
        run.append((sp, items))
        run_lines += n
    flush()
    if out:
        first = min(out, key=int)
        out[first] = f"*{title}*\n" + out[first]
    return dict(sorted(out.items(), key=lambda kv: int(kv[0])))


def poem(path: Path) -> dict:
    """{chapter: {first line: passage}}: the Sonnets a chapter a sonnet (one passage); the other poems one chapter,
    in stanzas, a passage of about PASSAGE lines, the dedication (and Lucrece's Argument) at line 0."""
    root = ET.parse(path).getroot()
    body = next(e for e in root.iter() if local(e.tag) == "body")
    lines = {}                                    # (part, line) -> text; part "" for a one-part poem
    order = []
    front = []                                    # the dedication, the Argument: prose paragraphs
    heads, headed = [], {}                        # a label waiting for its line; line -> its label

    def walk(e, in_front):
        t = local(e.tag)
        if t in SKIP:
            return
        if local(e.tag) == "div1" and e.get("type") in ("dedication", "argument"):
            in_front = True
        if in_front and t in ("ab", "salute", "signed", "closer", "p", "head"):
            text = words(e)
            if text:
                front.append(text)
            return
        if t == "label":                          # (the Phoenix's "Threnos": a heading before its line)
            heads.append(words(e))
            return
        if t in ("w", "c", "pc") and e.text and not in_front:
            n = (e.get("n") or "").split()[0] if e.get("n") else ""
            # (not "trailer", FINIS; nor "[138].1", the Passionate Pilgrim's other text of Sonnets 138 and 144)
            if not re.fullmatch(r"(\d+\.)?\d+", n) or n == "0":
                return
            key = tuple(n.split(".")) if "." in n else ("", n)
            if key not in lines:
                lines[key] = ""
                order.append(key)
                if heads:
                    headed[key] = heads.pop()
            lines[key] += e.text
            return
        for k in e:
            walk(k, in_front)
    walk(body, False)
    # (Folger doesn't mark the stanzas: Venus's are six lines, Lucrece's seven, the Phoenix's four and then
    # the Threnos's three, from line 53)
    size = {"Ven": 6, "Luc": 7}.get(path.stem)
    stanza_breaks = ({str(n) for n in range(1, 4000, size)} if size else
                     {str(n) for n in list(range(1, 53, 4)) + list(range(53, 70, 3))})
    out = {}
    for part, num in order:
        text = re.sub(r"\s+", " ", lines[(part, num)]).strip()
        if (part, num) in headed:
            text = f"*{headed[(part, num)]}*\n{text}"
        out.setdefault(part, []).append((int(num), text))
    book = {}
    if "" not in out:                             # the Sonnets
        for part, rows in out.items():
            book[part] = {"1": "\n".join(x for _, x in rows)}
        return book
    rows = out[""]
    chap = {}
    if front:
        chap["0"] = "\n\n".join(f"*{x}*" if i == 0 and len(front) > 1 else x for i, x in enumerate(front))
    run = []
    for num, x in rows:
        if run and sum(1 for _, t in run if t) >= PASSAGE - 6 and str(num) in stanza_breaks:
            chap[str(run[0][0])] = "\n".join(t for _, t in run)
            run = []
        if run and str(num) in stanza_breaks:
            run.append((num, ""))
        run.append((num, x))
    if run:
        chap[str(run[0][0])] = "\n".join(t for _, t in run)
    chap = {k: re.sub(r"\n{2,}", "\n\n", v).strip("\n") for k, v in chap.items()}
    return {"1": chap}


def main():
    src = files()
    books = {}
    for key, title in TITLES.items():
        if key not in src:
            raise SystemExit(f"missing {key}.xml")
        books[title] = poem(src[key]) if key in POEMS else play(src[key])
        print(f"{title}: {len(books[title])} chapters, {sum(len(c) for c in books[title].values())} passages")
    OUT.mkdir(parents=True, exist_ok=True)
    # (each scene's last line, so the lookup finds a line in a scene's last passage)
    last_lines = {play: {scene: max(map(int, lines)) for scene, lines in scenes.items()}
                  for play, scenes in LINES.items()}
    payload = {"source": SOURCE, "line_chunked": True, "last_lines": last_lines, "books": books}
    (OUT / "shakespeare.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    assert sorted(FOLIO) == sorted(k for k in TITLES if k not in POEMS)
    order = [TITLES[k] for k in FOLIO]
    (OUT / "lines.json").write_text(json.dumps({"source": SOURCE, "order": order,
                                                "lines": {t: LINES[t] for t in order}},
                                               ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"lines.json: {sum(len(s) for p in LINES.values() for s in p.values()):,} lines")


if __name__ == "__main__":
    main()
