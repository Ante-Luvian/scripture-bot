"""
Builds data/illustrations/<set>.json: the old illustrated editions' pictures, each tied to the passage it
illustrates, for the 🖌️ button under !verse, !fable, !tale and !shakespeare (bot_commands/illustrations.py).
The pictures themselves go in data/illustrations/<set>/ (not in git: this script rebuilds them), at most 1000 px
wide.

  la_fontaine          Gustave Doré's La Fontaine (Cassell, 1886): the edition the bot's Thornbury text comes from
                       (Gutenberg #50316). The full-page plates, each placed by where it stands in the book and
                       its caption checked against the fable's title, and the headpiece over each fable.
  aesop_rackham,       Arthur Rackham's (1912, #11339), Walter Crane's Baby's Own Aesop (1887, #25433) and Milo
  aesop_crane,         Winter's Aesop for Children (1919, #19994), matched to Townsend's fables (AESOP_SAME)
  aesop_winter
  grimm_crane,         Walter Crane's Household Stories (1882, #19068) and Rackham's Grimm (1909: Snowdrop, #37381,
  grimm_rackham        and Hansel & Grethel from Commons), matched to Hunt's tales (GRIMM_SAME)
  malory_beardsley     Aubrey Beardsley's Morte Darthur (Dent, 1893-94), from Commons, by Caxton's chapters
  faerie_queene_crane  Walter Crane's Faerie Queene (1894-97), from Commons, by canto
  shakespeare_boydell  the Boydell Shakespeare Gallery (1789-1805), from Commons, by Folger's scenes

Gutenberg's books are cached in scripts/.cache/illustrations/; Commons' pictures are shown from Commons.

    python scripts/build_illustrations.py [set ...]
"""
import difflib
import html
import io
import json
import re
import sys
import time
import unicodedata
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "illustrations"
OUT = ROOT / "data" / "illustrations"
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
WIDTH = 1000


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"unexpected: {message}")


def roman(s: str) -> int:
    total = 0
    for a, b in zip(s, s[1:] + " "):
        total += -ROMAN[a] if ROMAN.get(b, 0) > ROMAN[a] else ROMAN[a]
    return total


def fold(text: str) -> str:
    """Lower case, no accents, letters and spaces only: for comparing titles."""
    text = unicodedata.normalize("NFKD", html.unescape(text)).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"['’]", "", text.replace("&", " and "))
    return " ".join(re.findall(r"[a-z]+", text))


SMALL = {"the", "a", "an", "and", "of", "his", "her", "its", "their"}


def words(text: str) -> set:
    """A title's significant words."""
    return set(fold(text).split()) - SMALL


def plain(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def gutenberg(n: int) -> "tuple[str, Path]":
    """The illustrated HTML of Gutenberg book n (up to its licence) and the folder its images are in."""
    folder = CACHE / str(n)
    if not folder.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        zpath = CACHE / f"pg{n}-h.zip"
        if not zpath.exists():
            url = f"https://www.gutenberg.org/cache/epub/{n}/pg{n}-h.zip"
            zpath.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300).read())
            time.sleep(2)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(folder)
    page = next(folder.rglob(f"pg{n}-images.html"))
    text = page.read_text(encoding="utf-8")
    text = text[text.find("*** START"):]
    return text.split("*** END OF THE PROJECT GUTENBERG")[0], page.parent


def corpus_book(path: str, book: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))["books"][book]


def chapter_titles(path: str, book: str) -> dict:
    """{chapter: title} for a book whose chapters each open with their title in italics (the fables, the tales)."""
    out = {}
    for ch, verses in corpus_book(path, book).items():
        m = re.match(r"\*([^*\n]+)\*", verses["1"])
        if m:
            out[ch] = m.group(1)
    return out


def similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, fold(a), fold(b)).ratio()


def save_picture(src: Path, out: Path) -> None:
    """The picture at most WIDTH wide, as JPEG (PNG line drawings stay PNG)."""
    from PIL import Image
    if out.exists():
        return
    img = Image.open(src)
    if img.mode in ("P", "LA", "RGBA"):
        img = img.convert("RGBA")
        back = Image.new("RGB", img.size, (255, 255, 255))
        back.paste(img, mask=img.split()[-1])
        img = back
    elif img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    if img.width > WIDTH:
        img = img.resize((WIDTH, round(img.height * WIDTH / img.width)), Image.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".png":
        img.save(out, optimize=True)
    else:
        img.save(out, quality=88)


# each set's two letters in the buttons' ids ("lf12": La Fontaine's 13th picture): never change one
CODES = {"la_fontaine": "lf", "aesop_rackham": "ar", "aesop_crane": "ac", "aesop_winter": "aw", "grimm_crane": "gc",
         "grimm_rackham": "gr", "malory_beardsley": "mb", "faerie_queene_crane": "fq", "shakespeare_boydell": "sb"}


def save_set(name: str, meta: dict, pictures: list) -> None:
    seen = set()
    for p in list(pictures):                            # (a picture the book prints twice: once)
        where = p.get("file") or p["image"]
        if where in seen:
            print(f"  · {where.rsplit('/', 1)[-1]} twice: kept once ({p['title']})")
            pictures.remove(p)
        seen.add(where)
    for i, p in enumerate(pictures, 1):
        p.setdefault("n", str(i))
    (OUT / f"{name}.json").write_text(json.dumps({"code": CODES[name], **meta, "pictures": pictures},
                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    books = {}
    for p in pictures:
        books[p["book"]] = books.get(p["book"], 0) + 1
    print(f"  {name}: {len(pictures)} pictures ({', '.join(f'{b} {n}' for b, n in books.items())})")


# ── Doré's La Fontaine ─────────────────────────────────────────────────────

def la_fontaine() -> None:
    t, images = gutenberg(50316)
    book = "Fables of La Fontaine"
    titles = chapter_titles("data/ballads/la_fontaine.json", book)
    # where each fable begins: "FABLE XXII." (as build_fables.py reads them)
    heads = [(m.start(), str(roman(m.group(1))))
             for m in re.finditer(r'(?is)<p class="fable">\s*(?:<a[^>]*>\s*(?:</a>)?)?\s*FABLE\s+([IVXLCDM]+)\.?', t)]
    expect(len(heads) == len(titles), f"{len(heads)} fables in the book, {len(titles)} in the corpus")

    def around(pos: int) -> "tuple[str | None, str | None]":
        """(the fable a position is inside, the next to begin)."""
        before = [n for start, n in heads if start < pos]
        after = [n for start, n in heads if start > pos]
        return (before[-1] if before else None), (after[0] if after else None)

    pictures, dest = [], OUT / "la_fontaine"
    for m in re.finditer(r'(?is)<img[^>]*src="images/(laf_(plate|head)_(\d+)[a-z]?)\.jpg"[^>]*>', t):
        stem, kind = m.group(1), m.group(2)
        inside, following = around(m.start())
        if kind == "head":
            # a headpiece stands over the fable that follows it
            # (or, once, just below its "FABLE CXLIV.")
            gap = next(start for start, n in heads if n == following) - m.end() if following else 10 ** 6
            since = m.start() - next(start for start, n in heads if n == inside) if inside else 10 ** 6
            if gap > 400 and since > 200:
                print(f"  · {stem}: not over a fable (front matter, an essay, a dedication), left out")
                continue
            chapter, caption = (following if gap <= 400 else inside), ""
        else:
            cap = re.match(r'(?is)\s*<p class="cap">(.*?)</p>', t[m.end():])
            caption = plain(cap.group(1)) if cap else ""
            caption = re.sub(r"\s*\(\d\)\.?$", "", caption)                 # ("... JUNO (2).": a second plate)
            # (a caption may shorten the title: "The Dog and His Master's Dinner")
            scored = [(1.0 if words(caption) <= words(titles[c]) else similar(caption, titles[c]), c)
                      for c in (inside, following) if c]
            if not scored or max(scored)[0] < 0.75:
                print(f"  · plate {stem} '{caption}': not one of the fables here "
                      f"({', '.join(f'{titles[c]} {s:.2f}' for s, c in scored)}), left out")
                continue
            chapter = max(scored)[1]
        out = dest / f"{stem}.jpg"
        save_picture(images / "images" / f"{stem}.jpg", out)
        pictures.append({"n": stem.replace("laf_", "").replace("_", ""), "kind": kind, "title": titles[chapter],
                         "book": book, "chapter": chapter, "start": None, "end": None,
                         "file": out.relative_to(ROOT).as_posix(),
                         "page": "https://www.gutenberg.org/ebooks/50316"})
    save_set("la_fontaine", {"artist": "Gustave Doré", "work": "The Fables of La Fontaine (1886)",
                             "credit": "Project Gutenberg"}, pictures)


# ── Aesop: Rackham, Crane, Milo Winter ─────────────────────────────────────
# Each edition tells the fables in its own words and under its own titles, so a picture is tied to the fable it
# stands over in its book, and that fable to Townsend's by the words the two texts share *and* by the title.
# Where those disagree, the two texts were read side by side and the answer is below: Townsend's number, or None
# where Townsend hasn't the fable, or tells it so differently that the picture wouldn't fit his text (Crane's
# "The Ass & the Sick Lion" is Townsend's Sick Lion with an ass for the fox; Winter's travellers find a purse,
# Townsend's an axe).

AESOP_SAME = {
    # Rackham (Vernon Jones's titles)
    "the moon and her mother": None, "the mistress and her servants": 77, "the fox and the stork": 245,
    "the fox and the lion": 207, "the image seller": 213, "the lioness and the vixen": 23, "the goat and the vine": 78,
    "the hound and the hare": 182, "the crow and the swan": 32, "the farmer and the viper": 24, "the sick stag": 61,
    "the astronomer": 63, "the kid and the wolf": None, "the hound and the fox": None, "the frogs and the well": 141,
    "the goatherd and the goat": 42, "the crow and the snake": 309, "the wolf and his shadow": 246,
    "the farmer and his dogs": 119,
    # Crane (his limericks' titles)
    "the cock and the pearl": 7, "king log and king stork": 48, "the frightened lion": None, "the mouse and the lion": 1,
    "the lazy housemaids": 77, "the snake and the file": 296, "horse and man": 200, "the fox and the mosquitoes": 179,
    "the miser and his gold": 45, "the man that pleased none": 144, "the oak and the reeds": 129,
    "the trees and the woodman": 172, "the man and the snake": None, "the fox and the mask": 221,
    "the ass in the lions skin": 252, "the lion and the statve": 25, "the boaster": 43, "the vain jackdaw": 66,
    "the peacocks complaint": 210, "the two jars": 83, "brother and sister": 232, "the blind doe": 108,
    "hot and cold": 257, "neither beast nor bird": 247, "the stag in the ox stall": 100, "the lion in love": 44,
    "the hen and the fox": None, "porcupine snake and company": None, "the bundle of sticks": 5,
    "the farmers treasure": 70, "the cock the ass and the lion": 111, "fortvne and the boy": 151,
    "the ungrateful wolf": 4, "the herdsmans vows": 19, "the ass and the sick lion": None,
    # Winter
    "the tortoise and the ducks": None, "the frogs and the ox": 69, "belling the cat": 107, "the plane tree": 284,
    "the travelers and the purse": None, "the owl and the grasshopper": 222, "the two goats": None,
    "the lion and the gnat": 195, "the wolf and the lion": 131, "the stag and his reflection": 263,
    "the lion and the ass": None, "the vain jackdaw and his borrowed feathers": 66, "the wolf and the ass": 218,
    "the monkey and the cat": None, "the bear and the bees": None, "the heron": None, "the wolf and the goat": 226,
    "the cat the cock and the young mouse": None, "the wolf and the shepherd": 211,
    "the fighting bulls and the frog": None, "the astrologer": 63, "three bullocks and a lion": 225,
    "the frog and the mouse": 91, "the old lion and the fox": 37, "the wolf and the house dog": 116,
    "the cat and the fox": None, "the fox and the pheasants": None, "two travelers and a bear": 38,
    "the stag the sheep and the wolf": 185, "the animals and the plague": None, "the shepherd and the lion": None,
    "the dog and his reflection": 16, "the bees and wasps and the hornet": None, "the cat and the old rat": 145,
    "the wolf the kid and the goat": None, "the lion the ass and the fox": 159, "the lions share": None,
    "the hare and his ears": None,
}
# the same title for two fables in one edition: (edition, title) -> Townsend's
AESOP_EDITION_SAME = {(11339, "the kid and the wolf"): 198, (19994, "the kid and the wolf"): 67}
NOT_FABLES = {"introduction", "preface", "contents", "a list of the fables", "in colour", "in black and white"}
STOP = set("the a an and of to in on at by for with or his her its their he she it they was were is be been had have "
           "has that this which who whom but not as so from into upon out up one said would could should will shall "
           "him them then there what when all no".split())


def _bag(text: str) -> dict:
    out = {}
    for w in fold(text).split():
        if w not in STOP and len(w) > 2:
            out[w[:5]] = out.get(w[:5], 0) + 1
    return out


def _cos(a: dict, b: dict) -> float:
    dot = sum(n * b.get(w, 0) for w, n in a.items())
    norm = (sum(n * n for n in a.values()) * sum(n * n for n in b.values())) ** 0.5
    return dot / norm if norm else 0.0


def _picture_fable(t: str, heads: list, pos: int):
    """The heading of the fable a picture belongs to: the one just after it, if nothing but other pictures and
    page numbers come between (Crane's pictures head their page), else the one it stands under."""
    after = [h for h in heads if h.start() > pos]
    if after:
        between = t[pos:after[0].start()]
        between = re.sub(r'(?is)<p class="(?:center|caption|pagenum|border)[^"]*"[^>]*>.*?</p>|<p><span class="pagenum">'
                         r'.*?</p>|<p>\s*<a id[^>]*></a>\s*</p>|<img[^>]*>', "", between)
        if len(between) < 900 and not re.search(r"(?is)<p[ >]", between):
            return after[0]
    before = [h for h in heads if h.start() < pos]
    return before[-1] if before else None


def aesop_edition(n: int, name: str, artist: str, work: str) -> None:
    t, images = gutenberg(n)
    book = "Aesop's Fables"
    fables = corpus_book("data/classical/aesop.json", book)
    titles = chapter_titles("data/classical/aesop.json", book)
    bags = {k: _bag(" ".join(v.values())) for k, v in fables.items()}
    heads = list(re.finditer(r"(?is)<h[23][^>]*>(.*?)</h[23]>", t))
    pictures, dest, verdicts = [], OUT / name, {}
    for m in re.finditer(r'(?is)(?:<a[^>]*href="(images/[^"]+\.(?:jpg|png))"[^>]*>\s*)?<img[^>]*?src="(images/[^"]+)"', t):
        src = m.group(1) or m.group(2)
        alt = re.search(r'alt="([^"]*)"', m.group(0))
        page = re.search(r"(?i)page\s+(\d+)", alt.group(1) if alt else "")
        named = [h for h in heads if alt and fold(plain(h.group(1))) == fold(alt.group(1))]
        if page:                                         # (Winter's frontispiece: "Fable, Page 58")
            anchor = t.find(f'id="Page_{page.group(1)}"')
            h = next((h for h in heads if h.start() > anchor), None) if anchor > 0 else None
        elif len(named) == 1:                            # (a picture named for its fable: Rackham's often stand
            h = named[0]                                 #  a page away from it)
        else:
            h = _picture_fable(t, heads, m.start())
        if h is None:
            continue
        title = plain(h.group(1))
        key = fold(title)
        if key in NOT_FABLES:
            continue
        if key not in verdicts:
            i = heads.index(h)
            body = plain(t[h.end():heads[i + 1].start() if i + 1 < len(heads) else len(t)])
            by_text = max(bags, key=lambda k: _cos(_bag(title + " " + body), bags[k]))
            by_title = max(titles, key=lambda k: similar(title, titles[k]))
            if (n, key) in AESOP_EDITION_SAME:
                verdicts[key] = str(AESOP_EDITION_SAME[(n, key)])
            elif key in AESOP_SAME:
                verdicts[key] = str(AESOP_SAME[key]) if AESOP_SAME[key] else None
            elif by_text == by_title and _cos(_bag(title + " " + body), bags[by_text]) > 0.3:
                verdicts[key] = by_text
            else:
                print(f"  · '{title}': not settled (by its text {titles[by_text]}, by its title {titles[by_title]}), "
                      "left out")
                verdicts[key] = None
        chapter = verdicts[key]
        if chapter is None:
            continue
        path = images / src
        if not path.exists() or path.stat().st_size < 3000:      # (a missing file, a printer's ornament)
            continue
        out = dest / (Path(src).stem + (".png" if path.suffix == ".png" else ".jpg"))
        save_picture(path, out)
        if any(p["file"] == out.relative_to(ROOT).as_posix() for p in pictures):
            continue
        pictures.append({"title": titles[chapter], "book": book, "chapter": chapter, "start": None, "end": None,
                         "file": out.relative_to(ROOT).as_posix(), "page": f"https://www.gutenberg.org/ebooks/{n}"})
    left_out = sorted(k for k, v in verdicts.items() if v is None)
    print(f"  ({len(left_out)} pictured fables not in Townsend's: {', '.join(left_out)})")
    save_set(name, {"artist": artist, "work": work, "credit": "Project Gutenberg"}, pictures)


def aesop_rackham() -> None:
    aesop_edition(11339, "aesop_rackham", "Arthur Rackham", "Aesop's Fables (1912)")


def aesop_crane() -> None:
    aesop_edition(25433, "aesop_crane", "Walter Crane", "The Baby's Own Aesop (1887)")


def aesop_winter() -> None:
    aesop_edition(19994, "aesop_winter", "Milo Winter", "The Aesop for Children (1919)")


# ── Grimm: Walter Crane, Arthur Rackham ────────────────────────────────────
# Lucy Crane's and Edgar Lucas's titles against Margaret Hunt's (the bot's), whose numbers are the Grimms' own:
# matched as Aesop's are, by the words the texts share and by the title, the rest read side by side (below).

GRIMM_SAME = {
    # Crane
    "the rabbits bride": 66, "six soldiers of fortune": 71, "the frog prince": 1, "the vagabonds": 10,
    "aschenputtel": 21, "prudent hans": 32, "the table the ass and the stick": 36, "how mrs fox married again": 38,
    "tom thumbs travels": 45, "the sleeping beauty": 50,
    # Rackham (Lucas)
    "snowdrop": 53, "ashenputtel": 21, "the elves and the shoemaker": 39, "the lady and the lion": 88,
    "the marriage of mrs reynard": 38, "second tale": 38, "the salad": 122, "the youth who could not shudder": 4,
    "iron hans": 136,
}


def grimm_tales() -> "tuple[dict, dict, dict]":
    book = corpus_book("data/ballads/grimm.json", "Grimm's Household Tales")
    titles = chapter_titles("data/ballads/grimm.json", "Grimm's Household Tales")
    return book, titles, {k: _bag(" ".join(v.values())) for k, v in book.items()}


def grimm_match(title: str, body: str, titles: dict, bags: dict, report: list) -> "str | None":
    key = fold(title)
    if key in GRIMM_SAME:
        return str(GRIMM_SAME[key]) if GRIMM_SAME[key] else None
    bag = _bag(title + " " + body)
    ranked = sorted(bags, key=lambda k: -_cos(bag, bags[k]))
    by_title = max(titles, key=lambda k: similar(title, titles[k]))
    if ranked[0] == by_title and _cos(bag, bags[ranked[0]]) > 0.3:
        return ranked[0]
    report.append((title, body[:300], [ranked[0], by_title, ranked[1]]))
    return None


def grimm_pictures(n: int, heads: list, pictures: list, name: str) -> list:
    """Pictures for a Gutenberg Grimm: `heads` [(where a tale begins, its title)], `pictures` [(where, file,
    caption)]; each picture goes with the tale it stands in (or heads, when only pictures come before the tale)."""
    t, images = gutenberg(n)
    book, titles, bags = grimm_tales()
    tales, report = {}, []
    for (pos, title), nxt in zip(heads, heads[1:] + [(len(t), "")]):
        body = plain(t[pos:nxt[0]])
        if len(body) > 300:
            tales[pos] = grimm_match(title, body, titles, bags, report)
    for title, _, _ in report:
        print(f"  · '{title}': not settled, left out")
    out, dest = [], OUT / name
    for pos, src, caption in pictures:
        after = [p for p, _ in heads if p > pos]
        between = t[pos:after[0]] if after else "x"
        if after and not re.search(r"(?is)<p[ >][^<]*[a-z]", re.sub(r"(?is)<img[^>]*>|<span class=\"pagenum\">.*?</span>", "", between)):
            start = after[0]
        else:
            start = max((p for p, _ in heads if p < pos), default=None)
        chapter = tales.get(start)
        if chapter is None:
            continue
        path = images / src
        target = dest / (Path(src).stem + (".png" if path.suffix == ".png" else ".jpg"))
        save_picture(path, target)
        out.append({"title": titles[chapter], "caption": caption, "book": "Grimm's Household Tales", "chapter": chapter,
                    "start": None, "end": None, "file": target.relative_to(ROOT).as_posix(),
                    "page": f"https://www.gutenberg.org/ebooks/{n}"})
    return out


def grimm_crane() -> None:
    """Walter Crane's Household Stories (Lucy Crane's translation, 1882; Gutenberg #19068): the picture over each
    tale and the one closing it (not his lettered title panels or initials)."""
    t, _ = gutenberg(19068)
    heads = [(m.start(), plain(m.group(1)))
             for m in re.finditer(r'(?is)<img[^>]*alt="([^"]*)"[^>]*src="images/illus-\d+-title', t)]
    pictures = [(m.start(), m.group(1), "") for m in re.finditer(r'(?is)<img[^>]*src="(images/illus-\d+\.jpg)"', t)]
    save_set("grimm_crane", {"artist": "Walter Crane", "work": "Household Stories from the Brothers Grimm (1882)",
                             "credit": "Project Gutenberg"}, grimm_pictures(19068, heads, pictures, "grimm_crane"))


# The rest of Rackham's 1909 Grimm, reissued as Hansel & Grethel & Other Tales (1920): on Commons, sorted by tale
# into sub-categories (Hunt's numbers for them below). The pictures Commons hasn't sorted are left out, as are
# Chanticleer and Partlet's, which may belong to either of the two tales Lucas joins under that name (10 and 41).
RACKHAM_COMMONS = "Category:Hansel & Grethel & Other Tales (Rackham, 1920)"
RACKHAM_TALES = {"Hansel and Grethal": 15, "Jorinda and Joringel": 69, "The Bremen Town Musicians": 27,
                 "The Straw, the Coal, and the Bean": 18, "The Dog and the Sparrow": 58,
                 "The Twelve Dancing Princesses": 133, "The Fisherman and His Wife": 19, "The Raven": 93,
                 "Rapunzel": 12, "The Golden Bird": 57, "Mother Hulda": 24, "Red Riding Hood": 26,
                 "Sweetheart Roland": 56}


def grimm_rackham() -> None:
    """Arthur Rackham's Grimm (Edgar Lucas's translation, 1909): Snowdrop & Other Tales (1920, Gutenberg #37381),
    its colour plates (captioned with the line each shows) and drawings; and Hansel & Grethel & Other Tales from
    Commons."""
    t, _ = gutenberg(37381)
    heads = [(m.start(), plain(m.group(1))) for m in re.finditer(r"(?is)<h2[^>]*>(.*?)</h2>", t)]
    pictures = []
    for m in re.finditer(r'(?is)<img[^>]*alt="([^"]*)"[^>]*src="(images/(pl|ill)\d+\.(?:jpg|png))"', t):
        cap = re.match(r'(?is)[^>]*>\s*</div>\s*<p class="caption">(.*?)</p>', t[m.end():])
        caption = plain(cap.group(1)) if cap else (plain(m.group(1)) if m.group(3) == "pl" else "")
        pictures.append((m.start(), m.group(2), caption))
    out = grimm_pictures(37381, heads, pictures, "grimm_rackham")
    import build_dore as commons
    titles = chapter_titles("data/ballads/grimm.json", "Grimm's Household Tales")
    files = {}
    for sub in commons.members(RACKHAM_COMMONS, "subcat"):
        tale = sub.split("/")[-1]
        if tale in RACKHAM_TALES:
            for f in commons.members(sub):
                files.setdefault(f, RACKHAM_TALES[tale])
    info = commons.file_info(sorted(files))
    for f, chapter in sorted(files.items(), key=lambda kv: kv[0]):
        if f not in info or not f.lower().endswith((".jpg", ".png")):
            continue
        desc = info[f]["desc"]
        out.append({"title": titles[str(chapter)], "book": "Grimm's Household Tales", "chapter": str(chapter),
                    "caption": "" if desc.startswith(("Image or page", "Identifier")) else desc,
                    "start": None, "end": None, "image": info[f]["image"].split("?")[0], "page": info[f]["page"]})
    out.sort(key=lambda p: int(p["chapter"]))
    save_set("grimm_rackham", {"artist": "Arthur Rackham", "work": "The Fairy Tales of the Brothers Grimm (1909)",
                               "credit": "Project Gutenberg, Wikimedia Commons"}, out)


# ── Beardsley's Malory ─────────────────────────────────────────────────────
# Aubrey Beardsley's full-page drawings for Dent's Le Morte Darthur (1893-94), as Commons has them: each tied to
# the chapter of Caxton's text that tells what it shows, checked against the bot's Caxton (Beardsley's titles
# are Caxton's chapter headings, near enough: "How Sir Tristram drank of the love drink" is 8.24's "how Sir
# Tristram and Isoud drank the love drink"). Left out: his borders, initials and vignettes, the title pages, and
# the drawings whose subject Commons doesn't say ("Beaumains", "201").
BEARDSLEY = {
    "Merlin taketh the child Arthur into his keeping.jpg": "1.3",                   # "of his nurture"
    "The Lady of the Lake telleth Arthur of the sword Excalibur.jpg": "1.25",
    "Merlin and Nimue.gif": "4.1",                                                  # Merlin "assotted" on Nimue
    "Arthur and the strange mantle.gif": "4.16",                                    # "saved King Arthur from mantle"
    "Lancelot and Hellawes.jpg": "6.15",                                            # (Hellawes is named only here)
    "How Sir Tristram Drank of the Love Drink - by Aubrey Beardsley.jpg": "8.24",
    "How la Beale Isoud wrote to Sir Tristram.jpg": "9.10",                         # "sent letters to Sir Tristram"
    "How King Marke found Sir Tristram.jpg": "9.20",                                # "How King Mark found Sir Tristram"
    "How Morgan le Fay Cave a Shield to Sir Tristram.jpg": "9.40",                  # "received a shield of Morgan"
    "Mark & Dinadan & Palomides.jpg": "10.14",
    "La Beale Isould at Joyous Gard.jpg": "10.52",
    "How Sir Launcelot was known by Dame Elaine.jpg": "12.4",
    "How a devil in Woman's likeness would have tempted Sir Bors.jpg": "16.12",
    "The Holy Grail is Achieved - Aubrey Beardsley.jpg": "17.22",                   # (the frontispiece)
    "How Queen Guenever rode on Maying.jpg": "19.1",
    "Bedivere.jpg": "21.5",                                                         # Excalibur cast into the water
    "Queen Guenever nun at Almsbury.jpg": "21.7",                                   # "made her a nun in Almesbury"
}
BEARDSLEY_TITLES = {"Bedivere.jpg": "How Sir Bedivere Cast the Sword Excalibur into the Water",
                    "The Holy Grail is Achieved - Aubrey Beardsley.jpg": "The Achieving of the Sangreal",
                    "Queen Guenever nun at Almsbury.jpg": "How Queen Guenever made her a Nun",
                    "How Morgan le Fay Cave a Shield to Sir Tristram.jpg": "How Morgan le Fay gave a Shield to Sir Tristram"}


def malory_beardsley() -> None:
    import build_dore as commons
    rubrics = chapter_titles("data/arthurian/malory.json", "Le Morte d'Arthur")
    info = commons.file_info([f"File:{f}" for f in BEARDSLEY])
    out = []
    for f, chapter in BEARDSLEY.items():
        expect(f"File:{f}" in info, f"{f} is no longer on Commons")
        out.append({"title": BEARDSLEY_TITLES.get(f, re.sub(r"\s*-\s*by Aubrey Beardsley|\.\w+$", "", f)),
                    "caption": rubrics[chapter], "book": "Le Morte d'Arthur", "chapter": chapter, "start": None,
                    "end": None, "image": info[f"File:{f}"]["image"].split("?")[0], "page": info[f"File:{f}"]["page"]})
    save_set("malory_beardsley", {"artist": "Aubrey Beardsley", "work": "Le Morte Darthur (Dent, 1893–94)",
                                  "credit": "Wikimedia Commons"}, out)


# ── Crane's Faerie Queene ──────────────────────────────────────────────────
# Walter Crane's designs for Wise's edition (George Allen, 1894-97), as Commons has them: the few it names, and
# those of the Internet Archive's copy whose neighbouring text (the canto's argument, or its first stanza, which
# the Archive prints with each picture) finds the canto in the bot's Spenser. The rest Commons has without a word
# to place them by, and are left out.
# (Commons' names for them, and the canto each shows: its description says where it faces, or names the scene)
CRANE_FQ = {"Holiness defeats Error (Crane 1895-1897).jpg": ("1.1", "Holiness defeats Error"),
            "Walter Crane, Belphoebe.jpg": ("2.3", "Belphoebe"),
            "Britomart viewing Artegal (Crane, 1895-1897).jpg": ("3.2", "Britomart viewing Artegal"),
            "Britomart and Marinell.png": ("3.4", "Britomart and Marinell"),
            "Florimell saved by Proteus (Crane, 1895-1897).jpg": ("3.8", "Florimell saved by Proteus")}


def _uv(text: str) -> str:
    """Spenser's words run together, u/v and i/j alike, for finding his lines in the Archive's rough text
    ("mindAnd", a lost drop capital)."""
    return fold(text).replace("v", "u").replace("j", "i").replace(" ", "")


def canto_argument(fq: dict, chapter: str) -> str:
    """The canto's argument, the italic quatrain under its heading."""
    lines = re.findall(r"^\*([^*\n]+)\*$", fq[chapter]["1"], re.M)
    return " ".join(lines[1:])


def faerie_queene_crane() -> None:
    import build_dore as commons
    fq = corpus_book("data/english/faerie_queene.json", "The Faerie Queene")
    stanzas = [(ch, n, _uv(v)) for ch, vs in fq.items() for n, v in vs.items()]
    files = commons.members("Category:Spenser's Faerie Queene (1895)")
    info = commons.file_info(files)
    out = []
    for f in files:
        name = f[len("File:"):]
        if name in CRANE_FQ:
            chapter, title = CRANE_FQ[name]
        else:
            desc = info.get(f, {}).get("desc", "")
            after = re.search(r"Text Appearing After Image:\s*(.*?)(?:Note About Images|$)", desc)
            before = re.search(r"Text Appearing Before Image:\s*(.*?)Text Appearing After", desc)
            chapter = None
            for text, first_only in ((after.group(1) if after else "", False), (before.group(1) if before else "", True)):
                probe = _uv(text)[1:40]                     # (from the second letter: a drop capital is lost)
                if len(probe) < 25:
                    continue
                hits = [(ch, n) for ch, n, v in stanzas if probe in v]
                if len(hits) == 1 and (not first_only or hits[0][1] == "1"):
                    chapter = hits[0][0]
                    break
            if chapter is None:
                continue
            title = f"Book {chapter.split('.')[0]}, Canto {chapter.split('.')[1]}"
        out.append({"title": title, "caption": canto_argument(fq, chapter), "book": "The Faerie Queene",
                    "chapter": chapter, "start": None, "end": None,
                    "image": info[f]["image"].split("?")[0], "page": info[f]["page"]})
    out.sort(key=lambda p: tuple(map(int, p["chapter"].split("."))))
    print(f"  ({len(files) - len(out)} of Commons' {len(files)} left out: nothing to place them by)")
    save_set("faerie_queene_crane", {"artist": "Walter Crane", "work": "The Faerie Queene (George Allen, 1894–97)",
                                     "credit": "Wikimedia Commons"}, out)


# ── The Boydell Shakespeare ────────────────────────────────────────────────
# The pictures painted for John Boydell's Shakespeare Gallery (1789-1805) and the prints engraved from them, as
# Commons has them: one for each scene and subject (the Metropolitan Museum's prints of the large folio first).
# Boydell numbered the scenes as the editions of his day did, which isn't always as Folger does (his Winter's
# Tale 4.3, the sheep-shearing, is Folger's 4.4), so each picture's scene is checked against the bot's Folger:
# the words given here (people in it, words they say) must all be in it, else the play's one scene that has them
# all is taken, and the build says so. A quoted line puts the picture at that line.
# (file, play, Boydell's scene, title, words to find, a line it quotes)
BOYDELL = [
    ('"Off, off, you lendings–Come unbutton here" (Shakespeare, King Lear, Act 3, Scene 4) MET DR155.jpg',
     "King Lear", "3.4", "“Off, off, you lendings—come, unbutton here”", ["lendings"], "Off, off, you lendings"),
    ("'Much Ado About Nothing', Act IV, Scene 2, the Examination of Conrade and Borachio (from the Boydell series) "
     "Robert Smirke (1753–1845) Royal Shakespeare Theatre.jpg",
     "Much Ado About Nothing", "4.2", "The Examination of Conrade and Borachio", ["CONRADE", "BORACHIO", "DOGBERRY"], None),
    ("A Scene from Troilus and Cressida - Angelica Kauffmann.jpg",
     "Troilus and Cressida", "5.2", "Troilus sees Cressida with Diomed", ["DIOMEDES", "CRESSIDA", "TROILUS"], None),
    ("Abbot of leicester and wolsey westall.jpg",
     "Henry VIII", "4.2", "Wolsey received by the Abbot of Leicester", ["Leicester", "abbot"], None),
    ("Angelo's House–Escalus, a Justice, Elbow, Froth, Clown, Officers, etc. (Shakespeare, Measure for Measure, Act 2, "
     "Scene 1) MET DP109517.jpg",
     "Measure for Measure", "2.1", "Escalus, Elbow, Froth and the Clown", ["ESCALUS", "ELBOW", "FROTH"], None),
    ("Anne Page, Slender and Shallow (Shakespeare, Merry Wives of Windsor, Act 1, Scene 1) MET DP859579.jpg",
     "The Merry Wives of Windsor", "1.1", "Anne Page, Slender and Shallow", ["SLENDER", "SHALLOW", "ANNE"], None),
    ("Antigonus in the Storm (Act III, scene iii, from Shakespeare's \"The Winter's Tale\")).png",
     "The Winter's Tale", "3.3", "Antigonus in the storm", ["ANTIGONUS", "storm"], None),
    ("As You Like It, Act 5, Scene 4 (Shakespeare) MET DP859576.jpg",
     "As You Like It", "5.4", "Rosalind restored to her father", ["HYMEN", "ROSALIND"], None),
    ("Before the Duke's Palace–Rosalind, Celia, Orlando, the Duke & Attendants (Shakespeare, As You Like It, Act 1, "
     "Scene 2) MET DP859571.jpg",
     "As You Like It", "1.2", "Rosalind, Celia, Orlando and the Duke: the wrestling", ["ORLANDO", "CHARLES", "wrestle"], None),
    ("Brutus and the Ghost of Caesar 1802.jpg",
     "Shakespeare: Julius Caesar", "4.3", "Brutus and the Ghost of Caesar", ["GHOST", "BRUTUS"], None),
    ("Cassandra Raving (Shakespeare, Troilus and Cressida, Act 2, Scene 2) MET DP859559.jpg",
     "Troilus and Cressida", "2.2", "Cassandra raving", ["CASSANDRA"], None),
    ("Westall-ImogenInBed.jpg", "Cymbeline", "2.2", "Imogen in bed: Iachimo comes out of the trunk",
     ["IACHIMO", "trunk"], None),
    ("Doll Tearsheet, Falstaff, Henry and Poins (Shakespeare, King Henry IV, Part 2, Act 2, Scene 4) MET DP859578.jpg",
     "Henry IV, Part 2", "2.4", "Doll Tearsheet, Falstaff, Prince Henry and Poins", ["DOLL", "FALSTAFF", "POINS"], None),
    ("Falstaff in the Buck Basket (Shakespeare, Merry Wives of Windsor, Act 3, Scene 3) MET DP859563.jpg",
     "The Merry Wives of Windsor", "3.3", "Falstaff in the buck-basket", ["buck-basket", "FALSTAFF"], None),
    ("Falstaff rebuked (Smirke, c. 1795).jpg",
     "Henry IV, Part 2", "5.5", "Falstaff rebuked", ["I know thee not"], "I know thee not, old man"),
    ("Falstaff Rising Slowly (Shakespeare, First Part of King Henry IV, Act 5, Scene 4) MET DP870199.jpg",
     "Henry IV, Part 1", "5.4", "Falstaff rising slowly", ["FALSTAFF", "counterfeit"], None),
    ("Falstaff, Prince Henry and Poins at the Boar's Head Tavern (Shakespeare, King Henry the Fourth, Part 1, Act 2, "
     "Scene 4) MET DP859560.jpg",
     "Henry IV, Part 1", "2.4", "Falstaff, Prince Henry and Poins at the Boar's Head", ["FALSTAFF", "POINS", "HOSTESS"], None),
    ("Hamlet, Horatio, Marcellus and the Ghost (Shakespeare, Hamlet, Act 1, Scene 4) MET DP109516.jpg",
     "Hamlet", "1.4", "Hamlet, Horatio, Marcellus and the Ghost", ["HORATIO", "MARCELLUS", "Ghost"], None),
    ("Florizel, Perdita, etc. in the Shepherd's Cot (Shakespeare, Winter's Tale, Act 4, Scene 3) MET DP859561.jpg",
     "The Winter's Tale", "4.3", "Florizel, Perdita and the rest at the shepherd's cottage", ["FLORIZEL", "PERDITA", "POLIXENES"], None),
    ("Francis Wheatley (1747-1801) - 'The Comedy of Errors', Act I, Scene 1, the Rescue of Aemilia from the Shipwreck "
     "(from the Boydell series) - STRPG-A, 1993.116 - Royal Shakespeare Theatre.jpg",
     "The Comedy of Errors", "1.1", "The rescue of Aemilia from the shipwreck", ["EGEON", "mast"], None),
    ("FuseliMacbethBoydell.jpg", "Macbeth", "1.3", "Macbeth, Banquo and the Witches", ["WITCH", "BANQUO", "MACBETH"], None),
    ("George Henry Harlow (1787-1819) - 'King John', Act IV, Scene 1, Hubert and Arthur (from the Boydell series) - "
     "STRPG-A, 1993.56 - Royal Shakespeare Theatre.jpg",
     "King John", "4.1", "Hubert and Arthur", ["HUBERT", "ARTHUR", "irons"], None),
    ("George Romney - William Shakespeare - The Tempest Act I, Scene 1.jpg",
     "The Tempest", "1.1", "The shipwreck, Prospero and Miranda on the shore", ["If by your art"], None),
    ("The Enchanted Island, Before the Cell of Prospero - Prospero and Miranda (Shakespeare, The Tempest, Act 1, Scene 1) "
     "MET DP109509.jpg",
     "The Tempest", "1.1", "The enchanted island, before Prospero's cell: Prospero, Miranda, Caliban and Ariel",
     ["MIRANDA", "CALIBAN", "ARIEL", "Abhorrèd slave"], None),
    ("Olivia's proposal (Hamilton, c.1796).jpg", "Twelfth Night", "4.3", "Olivia's proposal", ["OLIVIA", "SEBASTIAN", "chantry"], None),
    ("Helena and Count Bertram before the King of France (Wheatley, 1793).jpg",
     "All's Well That Ends Well", "2.3", "Helena and Count Bertram before the King of France", ["HELEN", "BERTRAM", "KING"], None),
    ("Henry Fuseli (1741-1825) - 'Henry V', Act II, Scene 2, Henry V Discovering the Conspirators (from the Boydell "
     "series) - STRPG-A, 1993.50 - Royal Shakespeare Theatre.jpg",
     "Henry V", "2.2", "Henry V discovering the conspirators", ["SCROOP", "GREY", "CAMBRIDGE"], None),
    ("Hero Fainting in Church (Shakespeare, Much Ado About Nothing, Act 4, Scene 1) MET DP859565.jpg",
     "Much Ado About Nothing", "4.1", "Hero fainting in the church", ["HERO", "CLAUDIO", "FRIAR"], None),
    ("Hero, Ursula and Beatrice (Shakespeare, Much Ado About Nothing, Act 3, Scene 1) MET DP859567.jpg",
     "Much Ado About Nothing", "3.1", "Hero, Ursula and Beatrice in the garden", ["HERO", "URSULA", "BEATRICE"], None),
    ("Howard-TimonAct1.jpg", "Timon of Athens", "1.2", "Timon's prodigality", ["TIMON", "APEMANTUS", "Cupid"], None),
    ("Howard-TimonAct4.jpg", "Timon of Athens", "4.1", "Timon renounces society", ["TIMON", "wall"], None),
    ("Imogen (Shakespeare, Cymbeline, Act 3, Scene 6) MET DP859581.jpg",
     "Cymbeline", "3.6", "Imogen, disguised, at Belarius' cave", ["BELARIUS", "cave"], None),
    ("John Graham A bedchamber Desdemona in Bed asleep - Othello Act V scene 2.jpg",
     "Othello", "5.2", "A bedchamber: Desdemona in bed asleep", ["DESDEMONA", "OTHELLO", "light"], None),
    ("John Opie - Winter's Tale, Act II. Scene III.jpg",
     "The Winter's Tale", "2.3", "Leontes, Paulina and the infant Perdita", ["PAULINA", "ANTIGONUS", "LEONTES"], None),
    ("Joshua Reynolds (1723-1792) (studio of) - 'Henry VI', Part II, Act III, Scene 3, the Death of Cardinal Beaufort "
     "(from the Boydell series) - STRPG-A, 1993.89 - Royal Shakespeare Theatre.jpg",
     "Henry VI, Part 2", "3.3", "The death of Cardinal Beaufort", ["CARDINAL", "WARWICK"], None),
    ("King Lear Casting Out His Daughter Cordelia (Shakespeare, King Lear, Act 1, Scene 1) MET DP109513.jpg",
     "King Lear", "1.1", "King Lear casting out his daughter Cordelia", ["CORDELIA", "LEAR", "FRANCE"], None),
    ("King Lear Weeping Over the Body of Cordelia (Shakespeare, King Lear, Act 5, Scene 3) MET DP859562.jpg",
     "King Lear", "5.3", "King Lear weeping over the body of Cordelia", ["Howl"], "Howl, howl, howl"),
    ("Rome, Titus's Garden–Lucius Pursued by Lavinia (Shakespeare, Titus Andronicus, Act 4, Scene 1) MET DP859577.jpg",
     "Titus Andronicus", "4.1", "Titus's garden: young Lucius pursued by Lavinia", ["YOUNG LUCIUS", "Ovid"], None),
    ("Kirk-TitusAct4ProtectSon.jpg", "Titus Andronicus", "4.2", "Aaron protects his infant son",
     ["AARON", "NURSE", "CHIRON"], None),
    ("Woodforde-TitusAct2.jpg", "Titus Andronicus", "2.3", "Tamora, Lavinia, Demetrius and Chiron",
     ["TAMORA", "LAVINIA", "DEMETRIUS"], None),
    ("Kirk-TroilusCressidaAct1.jpg", "Troilus and Cressida", "1.2", "Cressida, with Pandarus, viewing the Trojan chiefs",
     ["PANDARUS", "CRESSIDA", "Hector"], None),
    ("Kirk-TroilusCressidaAct5.jpg", "Troilus and Cressida", "5.3", "Hector dissuaded from battle",
     ["ANDROMACHE", "HECTOR", "CASSANDRA"], None),
    ("Lady Macbeth (Shakespeare, Macbeth, Act 1, Scene 5) MET DP859570.jpg",
     "Macbeth", "1.5", "Lady Macbeth reading the letter", ["LADY MACBETH", "letter"], None),
    ("Macbeth consulting the Vision of the Armed Head.jpg",
     "Macbeth", "4.1", "Macbeth consulting the vision of the armed head", ["FIRST APPARITION", "MACBETH"], None),
    ("Miller-RomeoJulietAct1.jpg", "Romeo and Juliet", "1.5", "Romeo's first meeting with Juliet", ["ROMEO", "JULIET", "CAPULET"], None),
    ("Smirke-JulietNurse.jpg", "Romeo and Juliet", "2.5", "Juliet entreating her nurse", ["JULIET", "NURSE"], None),
    ("Rigaud-RomeoJuliet.jpg", "Romeo and Juliet", "3.5", "Romeo takes leave of Juliet", ["lark", "nightingale"], None),
    ("Opie-JulietsDeath.jpg", "Romeo and Juliet", "4.5", "Juliet's supposed death", ["NURSE", "Lady", "dead"], None),
    ("Northcote-JulietAwakes.jpg", "Romeo and Juliet", "5.3", "Juliet awakes, and finds Romeo dead", ["FRIAR LAWRENCE", "JULIET", "dagger"], None),
    ("Mrs. Ford and Mrs Page (Shakespeare, Merry Wives of Windsor, Act 2, Scene 1) MET DP859583.jpg",
     "The Merry Wives of Windsor", "2.1", "Mistress Ford and Mistress Page with Falstaff's letters", ["MISTRESS PAGE", "MISTRESS FORD", "letter"], None),
    ("Northcote-Princes-Act3.jpg", "Richard III", "3.1", "The meeting of Gloucester and the princes", ["PRINCE", "YORK", "Tower"], None),
    ("Northcote-MurderPrinces.jpg", "Richard III", "4.3", "The murder of the princes in the Tower", ["TYRREL", "smother"], None),
    ("Olivia's House - Olivia, Maria and Malvolio (Shakespeare, Twelfth Night, Act 3, Scene 4) MET DP109510.jpg",
     "Twelfth Night", "3.4", "Olivia, Maria and Malvolio cross-gartered", ["MALVOLIO", "OLIVIA", "cross-gartered"], None),
    ("Picking of the Red and White Roses (Shakespeare, King Henry the Sixth, Part 1, Act 2, Scene 4) MET DP859575.jpg",
     "Henry VI, Part 1", "2.4", "The picking of the red and white roses", ["SOMERSET", "PLANTAGENET", "rose"], None),
    ("Pisano and Imogen (Shakespeare, Cymbeline, Act 3, Scene 4) MET DP859564.jpg",
     "Cymbeline", "3.4", "Pisanio and Imogen", ["PISANIO", "IMOGEN"], None),
    ("Porter-CoriolanusAct1.jpg", "Coriolanus", "1.3", "Volumnia, Virgilia and Valeria", ["VOLUMNIA", "VIRGILIA", "VALERIA"], None),
    ("Porter-CoriolanusAct4.jpg", "Coriolanus", "4.5", "Coriolanus at the house of Aufidius", ["AUFIDIUS", "CORIOLANUS"], None),
    ("Prince Henry, Hotspur and Falstaff (Shakespeare, King Henry IV, Part 1, Act 5, Scene 4) MET DP859566.jpg",
     "Henry IV, Part 1", "5.4", "Prince Henry, Hotspur and Falstaff", ["HOTSPUR", "FALSTAFF", "PRINCE"], None),
    ("Queen Catherine, Cardinal Wolsey and Cardinal Campeius (Shakespeare, King Henry VIII, Act 3, Scene 1) MET DP859568.jpg",
     "Henry VIII", "3.1", "Queen Katherine, Cardinal Wolsey and Cardinal Campeius", ["CAMPEIUS", "WOLSEY", "KATHERINE"], None),
    ("Robert Smirke (1753-1845) - 'Henry IV', Part I, Act II, Scene 1, the Inn Yard with Gadshill and the Carriers "
     "(supplement to the Boydell series) - STRPG-A, 1993.97 - Royal Shakespeare Theatre.jpg",
     "Henry IV, Part 1", "2.1", "The inn yard at Rochester: Gadshill and the carriers", ["GADSHILL", "CARRIER"], None),
    ("Shylock rebuffing Antonio (Westall, 1795).jpg", "The Merchant of Venice", "3.3", "Shylock rebuffing Antonio",
     ["SHYLOCK", "ANTONIO", "jailer"], None),
    ("Shylock's House–Shylock, Jessica and Launcelot (Shakespeare, Merchant of Venice, Act 2, Scene 5) MET DP859580.jpg",
     "The Merchant of Venice", "2.5", "Shylock, Jessica and Lancelet", ["SHYLOCK", "JESSICA"], None),
    ("Stothard-HenryAnne.jpg", "Henry VIII", "1.4", "Henry's first sight of Anne Boleyn", ["ANNE", "WOLSEY", "KING"], None),
    ("The Awakening of King Lear (Smirke, c. 1792).jpg", "King Lear", "4.7", "The awakening of King Lear",
     ["CORDELIA", "LEAR", "DOCTOR"], None),
    ("The Duke of York discovering his son Aumerle's treachery (Hamilton, late 1790s).jpg",
     "Richard II", "5.2", "The Duke of York discovering his son Aumerle's treachery", ["AUMERLE", "YORK", "seal"], None),
    ("The Entry of Richard and Bolingbroke into London (from William Shakespeare's 'Richard II', Act V, Scene 2) "
     "James Northcote (1746–1831) Royal Albert Memorial Museum.jpg",
     "Richard II", "5.2", "The entry of Richard and Bolingbroke into London", ["Bolingbroke", "steed"], None),
    ("The Palace at Westminster- King Henry and the Prince of Wales (Shakespeare, King Henry IV, Part 2, Act 4, Scene 4) "
     "MET DP859574.jpg",
     "Henry IV, Part 2", "4.4", "King Henry and the Prince of Wales: the crown", ["PRINCE", "KING", "crown", "pillow"], None),
    ("The Princess, Rosaline, etc. (Shakespeare, Love's Labour Lost, Act 4, Scene 1) MET DP859573.jpg",
     "Love's Labor's Lost", "4.1", "The Princess, Rosaline and the forester", ["PRINCESS", "FORESTER", "ROSALINE"], None),
    ("The Seven Ages, Fifth Age- The Justice (Shakespeare, As You Like It, Act 2, Scene 7) MET DP109508.jpg",
     "As You Like It", "2.7", "The seven ages: the fifth age, the justice", ["seven ages"], "And then the justice"),
    ("Thomas Stothard (1755-1834) - 'Othello', Act II, Scene 1, the Return of Othello (from the Boydell series) - "
     "STRPG-A, 1993.109 - Royal Shakespeare Theatre.jpg",
     "Othello", "2.1", "The return of Othello to Cyprus", ["OTHELLO", "DESDEMONA", "Cyprus"], None),
    ("Tresham-AntonyCleopatra.jpg", "Antony and Cleopatra", "4.4", "Antony prepares for battle", ["ANTONY", "CLEOPATRA", "armor"], None),
    ("Tresham-DeathCleopatra.jpg", "Antony and Cleopatra", "5.2", "Cleopatra's death", ["CHARMIAN", "asp"], None),
    ("Westall-IachimoWager.jpg", "Cymbeline", "2.4", "Iachimo claims his wager", ["IACHIMO", "POSTHUMUS", "mole"], None),
    ("Westall-Katherine.jpg", "Henry VIII", "4.2", "Queen Katherine's last illness", ["KATHERINE", "GRIFFITH", "PATIENCE"], None),
    ("Westall-WolseyResigns.jpg", "Henry VIII", "3.2", "Wolsey resigns the seals", ["WOLSEY", "seal"], None),
]


def _scene_texts(play: str) -> dict:
    lines = json.loads((ROOT / "data" / "shakespeare" / "lines.json").read_text(encoding="utf-8"))["lines"][play]
    out = {}
    for scene, rows in lines.items():
        out[scene] = {int(n): " ".join(f"{p[0]} {p[1]}" for p in parts) for n, parts in rows.items()}
    return out


def shakespeare_boydell() -> None:
    import build_dore as commons
    members = commons.members("Category:Boydell Shakespeare Gallery")
    names = {}
    for row in BOYDELL:                                  # (the long names, by how they begin)
        hits = ([m for m in members if m[len("File:"):] == row[0]]
                or [m for m in members if m[len("File:"):].startswith(row[0].rsplit(".", 1)[0][:80])])
        expect(len(hits) == 1, f"{row[0]}: {len(hits)} files on Commons")
        names[row[0]] = hits[0]
    info = commons.file_info(list(names.values()))
    out, problems = [], []
    for f, play, scene, title, words_, quote in BOYDELL:
        f = names[f][len("File:"):]
        expect(f"File:{f}" in info, f"{f} is no longer on Commons")
        scenes = _scene_texts(play)

        def has(s):
            text = " ".join(scenes[s].values())
            return all(w in text if w.isupper() else w.lower() in text.lower() for w in words_)
        if scene not in scenes or not has(scene):
            found = [s for s in scenes if has(s)]
            if len(found) != 1:
                problems.append(f"{play} {scene} '{title}': the words are in {found or 'no scene'}")
                continue
            print(f"  · {play}: Boydell's {scene} is Folger's {found[0]} ({title})")
            scene = found[0]
        start = None
        if quote:
            hits = [n for n, t in scenes[scene].items() if fold(quote) in fold(t)]
            if len(hits) != 1:
                problems.append(f"{play} {scene}: '{quote}' found {len(hits)} times")
                continue
            start = hits[0]
        out.append({"title": title, "book": play, "chapter": scene, "start": start, "end": start,
                    "image": info[f"File:{f}"]["image"].split("?")[0], "page": info[f"File:{f}"]["page"]})
    expect(not problems, "\n".join(problems))
    order = json.loads((ROOT / "data" / "shakespeare" / "lines.json").read_text(encoding="utf-8"))["order"]
    out.sort(key=lambda p: (order.index(p["book"]), tuple(map(int, p["chapter"].split(".")))))
    save_set("shakespeare_boydell", {"artist": "The Boydell Shakespeare Gallery", "label": "Boydell",
                                     "work": "paintings and prints, 1789–1805", "credit": "Wikimedia Commons"}, out)


BUILDS = {"la_fontaine": la_fontaine, "aesop_rackham": aesop_rackham, "aesop_crane": aesop_crane,
          "aesop_winter": aesop_winter, "grimm_crane": grimm_crane, "grimm_rackham": grimm_rackham,
          "malory_beardsley": malory_beardsley, "faerie_queene_crane": faerie_queene_crane,
          "shakespeare_boydell": shakespeare_boydell}


def main(names: list) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in names or BUILDS:
        print(name)
        BUILDS[name]()


if __name__ == "__main__":
    main(sys.argv[1:])
