"""
Works the library listed but couldn't show: fills them in from the sources the rest came from.

  python scripts/build_library_gaps.py

- Irenaeus, Against Heresies (ANF 1, CCEL), by book, chapter and section, as it's cited
  (Adv. Haer. 3.3.1 = "Against Heresies 3.3:1")         -> patristics/irenaeus_of_lyons.json
- Athanasius's letters (NPNF II 4, CCEL): the Festal Letters by their numbers, and his
  personal letters                                         -> patristics/athanasius.json
- Basil's letters (NPNF II 8, CCEL), by their traditional numbers -> patristics/basil_the_great.json
- Augustine: the empty Retractions and On Free Will go (no English text to be had)
- Plato: the Axiochus (Burges, 1854) and Eryxias (Jowett), from Wikisource -> classical/plato_spuria.json
- Aristotle: On Youth, Old Age, Life and Death (Ross, MIT) and On the Generation of Animals
  (Platt, Wikisource)                                       -> classical/aristotle_more.json
- Aristotle from MIT, whole: the first import kept only the first web page of works MIT splits
  over several (Physics, Topics, On the Heavens... stopped after Book I). Each is rebuilt from
  MIT's one-file text; the short ones it has no such file for were whole already.
                                                            -> classical/aristotle_mit.json

Pages are cached in scripts/sources/ (see build_reformation.py, whose helpers this uses).
Afterwards: python scripts/clean_corpora.py, then python -m pytest -m corpus.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_reformation import ccel, clean, expect, fetch, thml_divs, tidy, ws_elements  # noqa: E402
from build_reformation import thml_flat as _thml_flat  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def roman(s: str) -> int:
    s = s.upper().strip(". ")
    total = 0
    for a, b in zip(s, s[1:] + " "):
        total += -ROMAN[a] if ROMAN.get(b, 0) > ROMAN[a] else ROMAN[a]
    return total


def thml_flat(fragment: str) -> list:
    """build_reformation.thml_flat, without the editors' notes first: CCEL nests a note's own
    <p> inside the paragraph it annotates, which cut the paragraph off at the note and let the
    note's text in ("Letter II. Placed circa 358, on Basil's retiring...")."""
    return _thml_flat(re.sub(r"(?is)<note\b.*?</note>", "", fragment))


def verses(paras: list) -> dict:
    return {str(i): p for i, p in enumerate((clean(p) for p in paras if clean(p)), 1)}


def sections(paras: list) -> dict:
    """Paragraphs grouped by the section numbers they begin with ("2. And..."), as the
    Fathers are cited; text before the first number joins section 1."""
    out, current = {}, 1
    for p in paras:
        body = re.sub(r"^\*[^*\n]*\*\n", "", p)               # (a heading in italics leading it)
        m = re.match(r"(\d+)\.\s", body)
        if m and int(m.group(1)) == current + 1 and "1" in out:
            current += 1
        key = str(current)
        out[key] = f"{out[key]}\n{p}" if key in out else p
    return {k: clean(v) for k, v in out.items() if clean(v)}


def update(rel: str, books: dict, remove=(), indent: int = 2) -> None:
    path = DATA / rel
    payload = json.loads(path.read_text(encoding="utf-8"))
    for name in remove:
        payload["books"].pop(name, None)
    payload["books"].update(books)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=indent), encoding="utf-8")
    for name, chapters in books.items():
        print(f"{rel}: {name}: {len(chapters)} chapters, {sum(len(v) for v in chapters.values())} passages")


def write(rel: str, source: str, books: dict, book_sources: dict) -> None:
    path = DATA / rel
    payload = {"source": source, "book_sources": book_sources, "books": books}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    for name, chapters in books.items():
        print(f"{rel}: {name}: {len(chapters)} chapters, {sum(len(v) for v in chapters.values())} passages")


# ── the Fathers, from CCEL ──────────────────────────────────────────────────

def against_heresies() -> dict:
    irenaeus = next(f for t, f in thml_divs(ccel("schaff/anf01"), 1) if t.startswith("IREN"))
    chapters = {}
    for title, book in thml_divs(irenaeus, 2):
        m = re.match(r"Against Heresies: Book ([IVX]+)", title)
        if not m:
            continue
        b = roman(m.group(1))
        for ctitle, frag in thml_divs(book, 3):
            cm = re.match(r"Chapter ([IVXLC]+)\.?", ctitle)
            n = roman(cm.group(1)) if cm else 0                    # 0: the book's preface
            paras = thml_flat(frag)
            if paras:
                paras[0] = f"*{tidy(ctitle)}*\n{paras[0]}" if not paras[0].startswith("*") else paras[0]
                chapters[f"{b}.{n}"] = sections(paras)
    expect(len(chapters) > 150, f"Against Heresies: {len(chapters)} chapters")
    return {"Against Heresies": chapters}


def athanasius_letters() -> dict:
    letters = next(f for t, f in thml_divs(ccel("schaff/npnf204"), 1) if t.startswith("Letters of Athanasius"))
    festal_part = next(f for t, f in thml_divs(letters, 2) if t.startswith("The Festal Letters"))
    parts = dict(thml_divs(festal_part, 3))
    festal, personal = {}, {}
    for title, frag in thml_divs(parts["Festal Letters."], 4):
        m = re.search(r"Letter ([IVXL]+)\b", re.sub(r"<[^>]+>", " ", frag[:1500]))
        n = roman(m.group(1)) if m else (max(map(int, festal)) + 1 if festal else 1)
        paras = thml_flat(frag)
        if paras and str(n) not in festal:
            festal[str(n)] = verses([f"*{tidy(title)}*\n{paras[0]}"] + paras[1:])
    for i, (title, frag) in enumerate(thml_divs(parts["Personal Letters."], 4), 1):
        paras = thml_flat(frag)
        if paras:
            personal[str(len(personal) + 1)] = verses([f"*{tidy(title)}*\n{paras[0]}"] + paras[1:])
    expect(len(festal) > 25 and len(personal) > 15, f"Athanasius: {len(festal)} festal, {len(personal)} personal")
    return {"Festal Letters of Athanasius": festal, "Letters of Athanasius": personal}


def basil_letters() -> dict:
    part = next(f for t, f in thml_divs(ccel("schaff/npnf208"), 1) if t.startswith("The Letters"))
    letters = {}
    for m in re.finditer(r'(?is)<div2\b([^>]*)>(.*?)</div2>', part):
        attrs, frag = m.group(1), m.group(2)
        if 'type="Letter"' not in attrs:
            continue
        plain = re.sub(r"<note\b.*?</note>|<[^>]+>", " ", frag, flags=re.S)       # (notes can be long)
        head = re.search(r"Letters?\s+([IVXLC]+)\s*\.", plain[:600])
        if head is None or re.search(r"Letters [IVXLC]+[,.\-]", attrs):        # (a note on five lost letters)
            continue
        n = roman(head.group(1))
        title = re.search(r'title="([^"]*)"', attrs)
        paras = [p for p in thml_flat(frag) if not re.fullmatch(r"Letters? [IVXLC]+\.", p.strip("* "))]
        if paras and str(n) not in letters:
            heading = tidy(title.group(1)) if title else ""
            if heading and heading.rstrip(".") not in paras[0][:200]:
                paras[0] = f"*{heading}*\n{paras[0]}"
            letters[str(n)] = verses(paras)
    expect(len(letters) > 330, f"Basil: {len(letters)} letters")
    return {"Letters of Basil": letters}


# ── Plato and Aristotle ─────────────────────────────────────────────────────

def numbered_dialogue(title: str) -> dict:
    """A Burges dialogue: a chapter for each of his numbered sections ("3. Soc. When..."), under
    his numbers (which skip where a section starts mid-paragraph: there's no 8 in the Axiochus)."""
    out, current = {}, 0
    for kind, text in ws_elements(title):
        m = re.match(r"(\d+)\.\s", text)
        if m and current < int(m.group(1)) <= current + 3:
            current = int(m.group(1))
            out[str(current)] = {"1": clean(text[m.end():])}
        elif current and kind == "p":
            v = out[str(current)]
            v[str(len(v) + 1)] = clean(text)
    expect(len(out) > 10, f"{title}: {len(out)} sections")
    return out


def paragraph_dialogue(title: str) -> dict:
    """A dialogue without section numbers: a chapter for each paragraph (speech)."""
    paras = [t for k, t in ws_elements(title) if k == "p"]
    out = {str(i): {"1": clean(p)} for i, p in enumerate((p for p in paras if clean(p)), 1)}
    expect(len(out) > 50, f"{title}: {len(out)} paragraphs")
    return out


def youth_and_old_age() -> dict:
    text = fetch("mit_youth_old.mb.txt", "https://classics.mit.edu/Aristotle/youth_old.mb.txt")
    text = text[text.index("SECTION 1"):text.rindex("THE END")] if "THE END" in text else text[text.index("SECTION 1"):]
    chapters = {}
    for m in re.finditer(r"(?ms)^Part (\d+)[ \t]*(.*?)(?=^Part \d+|\Z)", text):
        body = re.sub(r"(?m)^-{20,}\s*$|^SECTION \d+\s*$", "", m.group(2))
        paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", body)]
        chapters[m.group(1)] = verses(paras)
    expect(len(chapters) == 27, f"Youth and Old Age: {len(chapters)} parts")
    return chapters


def generation_of_animals() -> dict:
    chapters = {}
    for b, numeral in enumerate(["I", "II", "III", "IV", "V"], 1):
        part, paras = None, []
        for kind, text in ws_elements(f"On the Generation of Animals/Book {numeral}") + [("h", "Part 0")]:
            m = re.fullmatch(r"(?:Part )?(\d+)", text)           # Book I says "Part 3", the rest just "3"
            if m:
                if part and paras:
                    chapters[f"{b}.{part}"] = verses(paras)
                part, paras = m.group(1), []
            elif part and kind == "p":
                paras.append(text)
    expect(len(chapters) == 60, f"Generation of Animals: {len(chapters)} parts")
    return chapters


MIT_ARISTOTLE = {
    "Nicomachean Ethics": "nicomachaen", "Physics": "physics", "On the Soul": "soul", "Categories": "categories",
    "On Interpretation": "interpretation", "Prior Analytics": "prior", "Posterior Analytics": "posterior",
    "Topics": "topics", "On Sophistical Refutations": "sophist_refut", "On the Heavens": "heavens",
    "Meteorology": "meteorology", "On the Parts of Animals": "parts_animals", "On Sense and the Sensible": "sense",
    "Athenian Constitution": "athenian_const", "On Generation and Corruption": "gener_corr",
    "History of Animals": "history_anim", "On Memory and Reminiscence": "memory", "On Dreams": "dreams",
    "On Sleep and Sleeplessness": "sleep", "On Prophesying by Dreams": "prophesying",
    "On Longevity and Shortness of Life": "longev_short", "On the Motion of Animals": "motion_animals",
    "On the Gait of Animals": "gait_anim",
}


def mit_work(slug: str):
    """{chapter: {paragraph: text}} from MIT's one-file text: "BOOK II" + "Part 3" -> "2.3" (just
    "3" in a work without books); None when MIT has no such file (a one-page work)."""
    import urllib.error
    import urllib.request
    url = f"https://classics.mit.edu/Aristotle/{slug}.mb.txt"
    try:                                     # (fetch() retries for minutes; a missing file is just missing)
        urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
    text = fetch(f"mit_{slug}.mb.txt", url)
    body = text[text.index("-" * 40):]
    body = body[:body.rindex("THE END")] if "THE END" in body else body
    chapters, book = {}, 0
    for m in re.finditer(r"(?m)^[ \t]*(BOOK ([IVXL]+)|Part (\d+))[ \t]*(.*)$", body):
        if m.group(2):
            book = roman(m.group(2))
            continue
        end = re.compile(r"(?m)^[ \t]*(?:BOOK [IVXL]+|Part \d+)[ \t]*").search(body, m.end())
        chunk = (m.group(4) + "\n" + body[m.end():end.start() if end else len(body)]).strip()
        chunk = re.sub(r"(?m)^-{20,}\s*$|^SECTION \d+\s*$", "", chunk)
        paras = [re.sub(r"\s+", " ", para).strip() for para in re.split(r"\n\s*\n", chunk)]
        key = f"{book}.{m.group(3)}" if book else m.group(3)
        if key not in chapters:
            chapters[key] = verses(paras)
    return chapters


def mit_aristotle() -> dict:
    current = json.loads((DATA / "classical/aristotle_mit.json").read_text(encoding="utf-8"))["books"]
    out = {}
    for name, slug in MIT_ARISTOTLE.items():
        whole = mit_work(slug)
        old = sum(len(v) for v in current.get(name, {}).values())
        if whole and sum(len(v) for v in whole.values()) >= old * 0.9:
            out[name] = whole
            print(f"   {name}: {len(current.get(name, {}))} -> {len(whole)} chapters")
        else:
            print(f"   {name}: kept ({len(current.get(name, {}))} chapters; MIT one-file text: "
                  f"{'none' if whole is None else len(whole)})")
    return out


if __name__ == "__main__":
    update("classical/aristotle_mit.json", mit_aristotle())
    update("patristics/irenaeus_of_lyons.json", against_heresies())
    update("patristics/athanasius.json", athanasius_letters())
    update("patristics/basil_the_great.json", basil_letters())
    update("patristics/augustine.json", {}, remove=("Retractions", "On Free Will"))
    write("classical/plato_spuria.json", "Dialogues once ascribed to Plato.",
          {"Axiochus": numbered_dialogue("Axiochus (Burges)"), "Eryxias": paragraph_dialogue("Eryxias (Jowett)")},
          {"Axiochus": "Axiochus, once ascribed to Plato, trans. George Burges (1854)",
           "Eryxias": "Eryxias, once ascribed to Plato, trans. Benjamin Jowett"})
    write("classical/aristotle_more.json", "Aristotle.",
          {"On Youth, Old Age, Life and Death": youth_and_old_age(),
           "On the Generation of Animals": generation_of_animals()},
          {"On Youth, Old Age, Life and Death": "Aristotle, On Youth and Old Age, On Life and Death, On Breathing, "
                                                "trans. G. R. T. Ross. MIT Internet Classics Archive",
           "On the Generation of Animals": "Aristotle, trans. Arthur Platt (1910)"})
