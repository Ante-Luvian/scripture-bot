"""
Child's "English and Scottish Popular Ballads" (1882-98), all 305 ballads with their versions, from
archive.sacred-texts.com/neu/eng/child (built on Cathy Lynn Preston's Child corpus) ->
data/ballads/child.json: book "Child Ballads", a chapter a version ("12A" = Lord Randal, version A), a verse a
stanza; each version's first stanza led by its title in italics.

Sacred-texts warns its text "has some lacunae and glitches": they're checked for (scripts' report), and
corrected only from the printed book (CORRECTIONS, each with its source).

    python scripts/build_child.py            fetch (cached in scripts/.cache/child/) and build
    python scripts/build_child.py --report   also list what looks wrong
"""
import difflib
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "child"
OUT = ROOT / "data" / "ballads" / "child.json"
BASE = "https://archive.sacred-texts.com/neu/eng/child/"
UA = {"User-Agent": "ScriptureBot corpus builder (personal Discord bot)"}
BOOK = "Child Ballads"
GUT_CACHE = ROOT / "scripts" / ".cache" / "child_gut"
GUTENBERG = [44969, 47692, 62474, 63116, 71104]        # Project Gutenberg's proofread volumes 1-5 of the book
CORRECTIONS = {             # {"12A.5": (wrong, right, why)}: what both transcriptions carry over, mended
    "63D.24": (".\t* * * *", "* * * *", "the stanza label's dot, left on its gap line"),
    "73I.14": ("etc.@", "etc.", "a stray mark in the transcriptions"),
    "97A.1": ("wine;}", "wine;", "the brace the book prints joining two readings: not text"),
    # lost letters in lines too unlike Gutenberg's to be matched (read on the scans, or Gutenberg's where not found)
    "91G.17": ("A  littil", "An littil", "Gutenberg"),
    "117A.328": ("grene-wod  tre", "grene-wode tre", "Gutenberg"),
    "162A.3": ("The[n]   the Pers  owt", "The[n] the Persë owt", "scan, part 6 leaf 63"),
    "162A.42": ("myghte  tre", "myghttë tre", "scan, part 6 leaf 65"),

}
RELABELLED = []             # stanza labels for another ballad's number, found on a ballad's own page
ANYWHERE = {}               # every Gutenberg line, by the end of its letters (for versions printed elsewhere)
OCR_CACHE = ROOT / "scripts" / ".cache" / "child_ocr"
OCR = ([], {})              # the scans' OCR lines, and a word index of them (see _ocr)
LOOK = []                   # lines that differ only by OCR lookalikes: to be read on the scan
# Where the two copies differ only by letters OCR confuses, each line was read on the first edition's scan
# (archive.org englishscottishpNNchil). Gutenberg's reading where the page has it; any other line in LOOK keeps
# sacred-texts' reading, which the page had (14E.18 "sall", 29.45 "louely", 101B.24 "leamd", 191B.4 "you"...).
# Two are the book's own misprints, mended: 53D.22 "yonr" (Gutenberg's "your" taken), 226B.28 "dav" (ours, "day").
# 81G.2 "if" and 157H.9 "wnat" weren't found on the scans; plain slips in ours, so Gutenberg's is taken.
LOOKED_AT = {r: None for r in "11E.1 53D.22 81G.2 88B.26 96D.14 103A.6 107A.68 110G.15 112B.6 118A.17 148A.8 "
                              "154A.72 157H.9 221J.4 243F.13 248A.3 280B.12 305B.6".split()}
LOOKED_OURS = set("5A.44 14E.18 20J.10 29.45 30.7 31.55 33B.8 39B.32 39G.51 64B.20 83C.21 88C.2 96B.21 101B.24 "
                  "103A.47 107A.33 113.7 155H.2 169C.21 187B.35 191B.4 200D.7 200E.15 205A.5 208A.6 226B.1 "
                  "226B.28 257A.9 257A.12 277E.4".split())
VOTED, KEPT = [], []        # lines where the two copies differ: Gutenberg's taken, or ours kept, by the OCR
UNMATCHED, CHANGED = [], []      # (lines not found in the Gutenberg text; lines it changed)


def fetch(n: int) -> str:
    path = CACHE / f"ch{n:03d}.htm"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        for attempt in range(4):
            try:
                req = urllib.request.Request(f"{BASE}ch{n:03d}.htm", headers=UA)
                data = urllib.request.urlopen(req, timeout=60).read()
                break
            except Exception as e:                       # (never reuse a failed page's data)
                if attempt == 3:
                    raise SystemExit(f"ch{n:03d}: {e}")
                time.sleep(3 * (attempt + 1))
        path.write_bytes(data)
        time.sleep(0.6)
    return path.read_bytes().decode("cp1252", errors="replace")


def versions(n: int) -> dict:
    """{"12A": {"title": "Lord Rendal", "stanzas": {"1": "...", ...}}} for one ballad's page."""
    page = fetch(n)
    # Read by the stanza labels themselves ("12A.5", "9A.10r" a refrain line of stanza 10, "81A." stanza 1
    # unnumbered), not by the HTML: some versions' <PRE> is never closed and swallows the next version.
    titles = {m.group(1).upper(): html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
              for m in re.finditer(r"(?is)<H[1-4][^>]*>\s*(\d+[A-Za-z]*)\s*:\s*(.*?)</H[1-4]>", page)}
    parts = re.split(r"(?i)<HR\b[^>]*>", page)
    body = "\n".join(parts[1:-1]) if len(parts) > 2 else parts[-1]      # (between the header and the footer)
    body = re.split(r"(?is)<CENTER>\s*<A HREF=\"ch\d+\.htm\">\s*Next:", body)[0]   # (the footer: not text)
    body = re.sub(r"(?is)<script.*?</script>", "\n", body)
    body = re.sub(r"(?is)<H[1-4][^>]*>.*?</H[1-4]>", "\n@@VERSION@@\n", body)   # (a new version begins)
    text = html.unescape(re.sub(r"<[^>]+>", "", body)).replace("\r", "")
    text = text.split("Sacred Texts |")[0]               # (the last page's footer)
    # sacred-texts' stand-ins for what its encoding couldn't hold
    text = re.sub(r"RR([’'\-])rr", r"\1", text)         # (small capitals' punctuation: "SHERR’rrS" is "SHE’S")
    text = re.sub(r"RR’(\w)rr", r"‘\1", text)           # ("RR’Brry God" is "‘By God")
    text = re.sub(r"RR\W*rr", "", text)
    text = re.sub(r"(?<![A-Za-z])a\+e", "‘a", text)     # ("a+end let me see" is "‘and let me see")
    text = text.replace("a+e", "æ").replace("y+o", "ȝ").replace("Y+O", "Ȝ").replace("-+-", "—")
    text = re.sub(r"(?m)^(\s*\S*?)\*\t\s*\*", r"\1* *", text)                 # ("*<tab>* * *": a gap)
    out, current = {}, None
    for line in text.split("\n"):
        if line.strip() == "@@VERSION@@":
            current = None                 # (what comes before its first stanza is a source note: not text)
            continue
        line = re.sub(r"^(\s*\d+([A-Z]+))\.0\2\.", r"\1.", line)     # ("200K.0K.1": a typo for "200K.1")
        # "12A.5", "9A.10r" (a refrain line of stanza 10), "81A." (stanza 1, unnumbered), "22.1" (one version),
        # "44.6b" (a line of the burden), "2[M.1]" (in Child's own brackets), "58R<tab>" (a one-stanza version)
        if re.match(r"\s*\d+\[?[A-Z]*\.\d+\.[a-z]\]", line):     # ("110[O.4.j]": a variant reading's note)
            current = None
            continue
        e = re.match(r"\s*(\d+[A-Z]*)\.Epi\.\.(\d+)\s*\t(.*)", line)        # ("153A.Epi..1": its epitaph, after it)
        if e and e.group(1) in out:
            stanzas = out[e.group(1)]["stanzas"]
            num = str(int(max(stanzas, key=int)) + 1) if e.group(2) == "1" or not current else current[1]
            stanzas[num] = [e.group(3).strip()]
            current = (e.group(1), num)
            continue
        s = (re.match(r"\s*(\d+)\[?([A-Z]*)\]?\.(\d*)\]?([rb]?)\]?\s*\t?(.*)", line)  # ("12[P].1", "7[H.18r]")
             or re.match(r"\s*(\d+)([A-Z]+)()()\t(.*)", line))
        if s and 1 <= int(s.group(1)) <= 305 and abs(int(s.group(1)) - n) <= 2:
            if int(s.group(1)) != n:       # (a mislabel on this ballad's own page: "288B.2" on 289's)
                RELABELLED.append(f"{s.group(1)}{s.group(2)}.{s.group(3)} on ballad {n}'s page")
            label, num, refrain, rest = f"{n}{s.group(2)}", s.group(3) or "1", s.group(4), s.group(5).strip()
            stanzas = out.setdefault(label, {"title": titles.get(label, ""), "stanzas": {}})["stanzas"]
            if refrain and num in stanzas:
                stanzas[num].append(rest)                      # a refrain line, sung in that stanza
            else:
                stanzas[num] = [rest]
            current = (label, num)
            continue
        if not current or not line.strip():
            continue
        r = re.match(r"\s*Refrain:\s*\t?(.*)", line)
        rest = r.group(1) if r else line
        # a line's first word can sit in the label column ("And<tab>seruyd"): a space, not a tab
        out[current[0]]["stanzas"][current[1]].append(re.sub(r"\s*\t\s*", " ", rest.strip()))
    return {k: {"title": v["title"], "stanzas": {s: "\n".join(x for x in lines if x)
                                                    for s, lines in v["stanzas"].items()}} for k, v in out.items()}


def _clean(s: str) -> str:
    s = re.sub(r"(?is)<a[^>]*>\s*<sup>.*?</sup>\s*</a>|<sup>\s*\[?\d+\]?\s*</sup>|<br\s*/?>", "", s)  # (footnote marks;
    # a raised letter, as in "St" (Saint) with its t raised, is text)
    s = re.sub(r'(?is)<span class="page(?:num|no)"[^>]*>.*?</span>', "", s)                 # (page numbers)
    return html.unescape(re.sub(r"<[^>]+>", "", s)).replace("\xa0", " ").strip()


def _curly(s: str) -> str:
    """Volumes 1-2 on Gutenberg use straight quotes; the rest of the book, curly."""
    s = re.sub(r"(^|[\s(\[—-])'", "\\1‘", s).replace("'", "’")
    return re.sub(r'(^|[\s(\[—-])"', "\\1“", s).replace('"', "”")


def gutenberg() -> dict:
    """{ballad n: [[line, ...] a stanza, in the book's order]} from the five Gutenberg volumes."""
    out = {}
    for vol in GUTENBERG:
        path = GUT_CACHE / f"{vol}.html"
        if not path.exists():
            GUT_CACHE.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(f"https://www.gutenberg.org/cache/epub/{vol}/pg{vol}-images.html", headers=UA)
            path.write_bytes(urllib.request.urlopen(req, timeout=120).read())
        t = path.read_text(encoding="utf-8")
        t = t.split("*** END OF THE PROJECT GUTENBERG")[0]
        heads = [(m.start(), int(m.group(1))) for m in
                 re.finditer(r"(?is)<h2[^>]*>\s*(?:<a[^>]*>\s*)?(\d{1,3})\b(?:(?!</h2>).)*</h2>", t)
                 if 1 <= int(m.group(1)) <= 305]
        for (pos, n), (end, _) in zip(heads, heads[1:] + [(len(t), 0)]):
            for st in re.split(r'(?i)<div class="(?:stanza|group)">', t[pos:end])[1:]:
                lines = []
                for m in re.finditer(r'(?is)<(span|div) class="(?:i\d+|verse[^"]*|line[^"]*)">(.*?)</\1>', st):
                    if m.group(2).lstrip().startswith('<span class="linenum"'):
                        continue                                    # (a stanza number)
                    x = _curly(_clean(m.group(2)))
                    if x and not re.fullmatch(r"\d+", x):
                        lines.append(x)
                if lines:
                    out.setdefault(n, []).append(lines)
    return out


def _norm(s: str) -> str:
    """The letters alone, lower case; ë, þ and the like kept (they're what sacred-texts lost)."""
    s = s.replace("RRth", "þ").replace("RR", "þ")          # (sacred-texts' "RRther" is the book's "Þer")
    return "".join(c for c in s.lower() if c.isalpha()).replace("þ", "th")      # (it gives þ as "th" too)


def _key(s: str) -> str:
    """A line's last ten plain letters: what both copies share even where one lost an ë."""
    return re.sub(r"[^a-z]", "", _norm(s))[-10:]


def _ratio(a: str, b: str, floor: float = 0) -> float:
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return sm.ratio() if sm.real_quick_ratio() > floor and sm.quick_ratio() > floor else 0


def _lost_start(line: str, first: bool) -> int:
    """How many letters this line may have lost from its start: up to four from a stanza's first line when what's
    left starts in lower case ("n Arthur took", "‘Then Arthur took" in the book), one from a small-capitals first
    word ("TOP, stop", "‘Stop, stop"); none otherwise (a capital there means the line begins as it should)."""
    if not first:
        return 0
    if re.match(r"\W*[a-z]", line):
        return 4
    return 1 if re.match(r"\W*[A-Z]{2,}\b", line) else 0


def _only_lost(mine: str, theirs: str, start: int) -> bool:
    """True if the book's line is this one with only what sacred-texts lost put back: letters at the start (see
    _lost_start), and single letters it dropped inside the line -- each ë, þ, ȝ..., and the first f of "ff".
    Any other difference is a different line (another version's wording, an extra word), and is not taken."""
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, mine, theirs, autojunk=False).get_opcodes():
        if op == "insert":
            if i1 == 0:
                if j2 - j1 > start:
                    return False
            elif j2 - j1 > 1 or not (theirs[j1] > "z" or theirs[j1] == "f" and "ff" in theirs[j1 - 1:j1 + 2]):
                return False
        elif op != "equal":
            return False
    return True


def _ocr() -> tuple:
    """The Internet Archive's OCR of the first edition's ten parts: never used as text, only to tell which of two
    transcriptions the printed page agrees with. Returns (lines, {word: [line index, ...]})."""
    if not OCR[0]:
        for p in range(1, 11):
            item = f"englishscottishp{p:02d}chil"
            path = OCR_CACHE / f"{item}.txt"
            if not path.exists():
                OCR_CACHE.mkdir(parents=True, exist_ok=True)
                req = urllib.request.Request(f"https://archive.org/download/{item}/{item}_djvu.txt", headers=UA)
                path.write_bytes(urllib.request.urlopen(req, timeout=120).read())
            OCR[0].extend(x for x in path.read_text(encoding="utf-8", errors="replace").split("\n") if x.strip())
        for i, x in enumerate(OCR[0]):
            for w in set(re.findall(r"[a-z]{4,}", x.lower())):
                OCR[1].setdefault(w, []).append(i)
    return OCR


# Letters OCR mistakes for one another. Gutenberg's few slips are OCR's that its proofreaders missed, so where the
# two copies differ only by these, the scans' OCR is no witness (it makes the same slip): the line is looked at.
LOOKALIKE = {frozenset(p) for p in [("l", "i"), ("u", "n"), ("rn", "m"), ("h", "b"), ("c", "e"), ("cl", "d"),
                                     ("li", "h"), ("ll", "il"), ("f", "s"), ("in", "m"), ("ni", "m"), ("il", "h"),
                                     ("ii", "u"), ("y", "v"), ("n", "h"), ("t", "f"), ("o", "c"), ("ri", "n")]}


def _lookalike(mine: str, theirs: str) -> bool:
    ops = [op for op in difflib.SequenceMatcher(None, mine, theirs, autojunk=False).get_opcodes() if op[0] != "equal"]
    return bool(ops) and all(op == "replace" and frozenset((mine[i1:i2], theirs[j1:j2])) in LOOKALIKE
                             for op, i1, i2, j1, j2 in ops)


def _book_says(mine: str, theirs: str) -> bool:
    """True if the printed page (by its OCR) reads like the Gutenberg line rather than the sacred-texts one."""
    lines, index = _ocr()
    count = {}
    for w in set(re.findall(r"[a-z]{4,}", (mine + " " + theirs).lower())):
        hits = index.get(w, [])
        if len(hits) < 400:                     # (common words say nothing)
            for i in hits:
                count[i] = count.get(i, 0) + 1
    a, b = _norm(mine), _norm(theirs)
    best_a = best_b = 0
    for i in sorted(count, key=count.get, reverse=True)[:12]:
        c = _norm(lines[i])
        ra, rb = _ratio(a, c), _ratio(b, c)
        if max(ra, rb) > max(best_a, best_b):
            best_a, best_b = ra, rb
    return best_b > best_a


def proofread(n: int, found: dict, book: list) -> None:
    """Replace each stanza's lines with the proofread Gutenberg lines they match (sacred-texts lost first letters,
    and every ë, þ and ȝ). Walks the book in order; a line is only replaced by a close match."""
    # Line by line, not stanza by stanza: the two group burdens and refrains differently. The earliest close line
    # a little ahead is taken, so a refrain sung in every stanza doesn't pull the reading on to a later one.
    lines = [x for st in book for x in st]
    normed = [_norm(x) for x in lines]
    pos, run = 0, []
    for label, v in found.items():
        for k, text in v["stanzas"].items():
            new = []
            for li, line in enumerate(text.split("\n")):
                a = _norm(line)
                if len(a) < 6:
                    new.append(line)
                    continue
                start = _lost_start(line, li == 0)
                # the earliest line it could be. A long jump may be a later version's same line, so it only moves
                # the reading on once three lines in a row agree with it (the notes between two versions, skipped).
                at = next((i for i in range(pos, min(len(lines), pos + 600))
                           if _ratio(a, normed[i], 0.85) and _only_lost(a, normed[i], start)), None)
                if at is not None:
                    if at - pos < 40:
                        pos, run = at + 1, []
                    else:
                        run = (run if run and 0 < at - run[-1] <= 3 else []) + [at]
                        if len(run) >= 3:
                            pos, run = at + 1, []
                    right = lines[at]
                else:                                   # (a version Child added later, in a volume's Additions)
                    right = next((x for x in ANYWHERE.get(_key(line), []) if _only_lost(a, _norm(x), start)), None)
                if right is None:
                    # The two copies differ by more than what was lost: the scans' OCR says which is the book's.
                    near = max(range(pos, min(len(lines), pos + 8)), key=lambda i: _ratio(a, normed[i]), default=None)
                    if near is not None and _ratio(a, normed[near]) >= 0.85:
                        if _lookalike(a, normed[near]):           # (read on the scan: see LOOKED_AT)
                            if f"{label}.{k}" in LOOKED_AT:
                                right = lines[near]
                            elif f"{label}.{k}" not in LOOKED_OURS:
                                LOOK.append((f"{label}.{k}", line, lines[near]))
                        elif _book_says(line, lines[near]):
                            right = lines[near]
                            VOTED.append(f"{label}.{k}")
                        else:
                            KEPT.append(f"{label}.{k}")
                        pos = near + 1
                        if right is None:
                            new.append(line)
                            continue
                if right is None:
                    new.append(line)
                    UNMATCHED.append(f"{label}.{k}")
                    continue
                new.append(right)
                if right != line:
                    CHANGED.append((round(_ratio(a, _norm(right)), 2), f"{label}.{k}", line, right))
            # a line the book prints as the end of the one before ("‘Atweel it is my bukes,’ quo etc.") goes
            new = [x for i, x in enumerate(new) if not (i and x != new[i - 1] and _norm(x)
                                                        and _norm(new[i - 1]).endswith(_norm(x))
                                                        and not _norm(text.split("\n")[i - 1]).endswith(_norm(x)))]
            v["stanzas"][k] = "\n".join(new)


def main():
    data, titles = {}, {}
    book = gutenberg()
    for stanzas in book.values():
        for st in stanzas:
            for x in st:
                ANYWHERE.setdefault(_key(x), []).append(x)
    for n in range(1, 306):
        found = versions(n)
        if not found:
            raise SystemExit(f"ballad {n}: no versions found")
        proofread(n, found, book.get(n, []))
        for label, v in found.items():
            key = f"{label}"
            stanzas = dict(v["stanzas"])
            for ref, (wrong, right, _) in CORRECTIONS.items():
                if ref.startswith(label + "."):
                    k = ref.split(".", 1)[1]
                    stanzas[k] = stanzas[k].replace(wrong, right)
            first = next(iter(stanzas), None)
            if first is None:
                continue
            title = v["title"] or next((x["title"] for x in found.values() if x["title"]), "")   # (no heading of its own)
            stanzas[first] = f"*{title}*\n{stanzas[first]}" if title else stanzas[first]
            data[key] = stanzas
        titles[str(n)] = next(iter(found.values()))["title"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": "Francis James Child (1882-98)", "titles": titles,
                               "books": {BOOK: data}}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(titles)} ballads, {len(data)} versions -> {OUT.relative_to(ROOT)}")
    print(f"proofread from Gutenberg: {len(CHANGED)} lines changed ({len(VOTED)} of them where the copies differ,"
          f" by the scans); {len(KEPT)} kept by the scans; {len(UNMATCHED)} lines not found in the book")
    print(f"{len(LOOK)} lines differ only by letters OCR confuses, not yet read on the scans (ours kept)")
    if "--look" in sys.argv:
        for ref, a, b in LOOK:
            print(f"  {ref}: {a!r} | {b!r}")
    if "--votes" in sys.argv:
        for r, ref, a, b in CHANGED:
            if ref in VOTED and not _only_lost(_norm(a), _norm(b), 4):
                print(f"  {ref}: {a!r} -> {b!r}")
    if "--report" in sys.argv:
        for r, ref, a, b in sorted(CHANGED)[:60]:
            print(f"  {r} {ref}: {a!r} -> {b!r}")
        print("  not found:", ", ".join(sorted(set(UNMATCHED))))
    if RELABELLED:
        print(f"relabelled ({len(RELABELLED)}):", "; ".join(RELABELLED[:40]))


if __name__ == "__main__":
    sys.exit(main())
