"""Translate a book of the Glossa Ordinaria through the Claude API, in Message Batches (half price).

    python scripts/translate_glossa_api.py NN draft  [--pilot N]   # Haiku: short glosses and lemmas; Sonnet: long
    python scripts/translate_glossa_api.py NN review [--pilot N]   # Sonnet checks drafts of MID characters and up
    python scripts/translate_glossa_api.py NN merge                # -> scripts/glossa/english/NN.json, lemmas/NN.json
    python scripts/translate_glossa_api.py NN cost                 # what the runs so far have cost

NN is Gloss-e's book number (scripts/fetch_glossa.py; its Latin must be in scripts/.cache/glossa/NN.json). Each stage
submits a batch, waits for it (usually under an hour) and saves what came back in scripts/.cache/glossa_api/NN/, so a
stage can be re-run and only redoes the requests that failed. `--pilot N` does only the book's first N short glosses
(and a fifth as many long ones) into a separate pilot/ folder, to measure cost and quality before a whole book.

Why this shape (calibration on 80 glosses we had translated, 2026-11-15): Haiku 5.5 made meaning errors in 3 of 40
short glosses but 9 of 40 long ones (three of them reversing the sense); Sonnet 5.5 made 4 of 40 on the long ones.
So Haiku drafts glosses under LONG characters and Sonnet the rest, and Sonnet reviews every draft of MID characters
or more (Isaiah, the first book done this way, cost $0.92 to draft and $1.28 to review; see review() for why the
shortest go unreviewed), told to look for the errors the calibration found: negations, "easier X than Y", misparsed relative clauses, Douay quotations not
recognised. The Douay-Rheims wording of quotations is found by code, not left to the model: each gloss's Latin is
matched against the Vulgate (word 4-grams) and the Douay text of the verses it shares runs of words with goes into
the request. Merging also tidies what the models do inconsistently: straight quotes, "gentiles", a heading
repeated at the start of the gloss.

Needs ANTHROPIC_API_KEY (read from .env) and `pip install anthropic`.
"""
import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_place_names import DR_NAMES, bolls  # noqa: E402  (the bolls.life Vulgate, cached)
from build_glossa import clean as lemma_key  # noqa: E402  (how build_glossa looks a lemma up)

GLOSSA = ROOT / "scripts" / ".cache" / "glossa"
STATE = ROOT / "scripts" / ".cache" / "glossa_api"
ENGLISH = ROOT / "scripts" / "glossa" / "english"
LEMMAS = ROOT / "scripts" / "glossa" / "lemmas"

LONG = 250                                  # characters of Latin: a gloss this long or longer is Sonnet's
MID = 80                                    # ... and Haiku's from this long up get Sonnet's review
DRAFT = {"short": ("claude-haiku-5-5", "medium"), "long": ("claude-sonnet-5-5", "medium"),
         "lemma": ("claude-haiku-5-5", "low")}
REVIEW = {"mid": ("claude-sonnet-5-5", "medium"), "long": ("claude-sonnet-5-5", "medium")}
# per million tokens, before the Batch API's half: input, output, cache read, cache write
PRICES = {"claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125), "claude-sonnet-5-5": (2.00, 10.00, 0.10, 2.50)}
DRY = False
EXAMPLE_BOOKS =("40", "25", "28", "32", "03")   # our own translations, shown as examples of the style

for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if line.startswith("ANTHROPIC_API_KEY=") and not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip().strip('"')


# ── the Latin ────────────────────────────────────────────────────────────────

def clean(latin: str) -> str:
    """Without the edition's page markers ("{t. 2: Erfurt, f. 52ra; ...}"), its paragraph numbers ("146. ") or the
    leading "+" marker: the calibration's models kept them in the English."""
    latin = re.sub(r"\{[^{}]*\}", "", latin)
    latin = re.sub(r"^\s*\+\s*", "", latin)
    latin = re.sub(r"^\s*\d+\.\s+", "", latin)
    return re.sub(r"\s+", " ", latin).strip()


def book(nn: str) -> dict:
    return json.loads((GLOSSA / f"{nn}.json").read_text(encoding="utf-8"))


def glosses(nn: str) -> list:
    """Every gloss in order, with its verse: [{id, type, lemma, latin, c, v}]."""
    out = []
    for c, verses in book(nn)["chapters"].items():
        for v, gs in verses.items():
            for g in gs:
                out.append(dict(g, c=c, v=v, latin=clean(g["latin"]), lemma=lemma_key(g["lemma"] or "")))
    return out


# ── the Douay-Rheims, and the verses a gloss quotes ──────────────────────────

def plain_words(text: str) -> list:
    text = text.lower().replace("æ", "e").replace("œ", "e").replace("ae", "e").replace("oe", "e")
    text = text.replace("j", "i").replace("v", "u")
    return re.findall(r"[a-z]+", text)


class Douay:
    """The Douay-Rheims by its own (Vulgate) book names and numbering, and a finder for the verses of the Vulgate a
    piece of Latin shares runs of five or more words with."""

    def __init__(self):
        self.text = json.loads((ROOT / "data" / "drb.json").read_text(encoding="utf-8"))
        self.grams = defaultdict(set)
        for name, chapters in bolls("VULG").items():
            dr = DR_NAMES.get(name, name)
            for c, verses in chapters.items():
                for v, verse in verses.items():
                    w = plain_words(verse)
                    for i in range(len(w) - 3):
                        self.grams[" ".join(w[i:i + 4])].add((dr, c, v))
        common = [g for g, refs in self.grams.items() if len(refs) > 25]      # ("et dixit dominus ad")
        for g in common:
            del self.grams[g]

    def verse(self, name: str, c, v) -> str:
        return self.text.get(name, {}).get(str(c), {}).get(str(v), "")

    def quoted(self, latin: str, limit: int = 3) -> list:
        w = plain_words(latin)
        hits = Counter()
        for i in range(len(w) - 3):
            for ref in self.grams.get(" ".join(w[i:i + 4]), ()):
                hits[ref] += 1
        return [ref for ref, n in hits.most_common(limit) if n >= 2 and self.verse(*ref)]


# ── requests ─────────────────────────────────────────────────────────────────

RULES = """You translate the Glossa Ordinaria, the medieval Church's Bible commentary (the 1480 printing), from Latin \
into English, for a Discord bot whose readers are ordinary Christians.

The rules:
- Plain, faithful English that keeps the Glossa's terseness. Translate every word of the Latin; add nothing: no \
explanations, no headings the Latin doesn't have.
- Where the Latin opens by repeating the Bible's words (often in capitals: "PUTABAT SE etc."), translate them in \
the Douay-Rheims wording, in ordinary sentence case ("He thought he stood, etc.").
- Authorities named in the gloss's own text (HIERONYMUS, AUGUSTINUS, GREGORIUS, ISIDORUS, BEDA, RABANUS, STRABUS, \
ORIGENES, ALCUINUS, AMBROSIUS...) become "Jerome.", "Augustine." etc.; ALLEGORICE / MORALITER / MYSTICE / HISTORICE \
become "Allegorically." / "Morally." / "Mystically." / "Historically." But when the authority or sense is only the \
heading the gloss stands under ("on the words: HIERONYMUS"), don't put it in the English: the heading is shown \
separately.
- Quotations of Scripture use the Douay-Rheims wording. The Douay text of the verse each gloss is on, and of verses \
the glosses share words with, is given: use it, bent to what the Latin actually says where the Glossa quotes \
loosely. Never quote Scripture from memory in another translation's wording. Put quotations in curly double quotes.
- Biblical names in their Douay-Rheims forms (Isaias, Osee, Josue, Noe, Nabuchodonosor, Juda).
- The printing has slips and abbreviations ("super hi" for "superbi", "sepiimum" for "septimum"); read the word \
meant.
- Be exact about the sense of the sentence: keep every negation where the Latin puts it ("non ... sed": not X but Y; \
"we are not forbidden to walk the right way, but to turn to the left"), keep comparisons whole ("facilius est ... \
quam": it is easier to ... than to ...), and attach each relative clause to the noun it belongs to.
- "id est" is "that is"; "vel" between two readings is "or"; "unde" introducing a quotation is "Whence:"."""


def examples() -> str:
    """Fifteen of our own translations, a third of them long, as the pattern for style (kept few: the system prompt goes with every request, and was two-thirds of the input with thirty)."""
    picked = []
    for nn in EXAMPLE_BOOKS:
        english = json.loads((ENGLISH / f"{nn}.json").read_text(encoding="utf-8"))
        gs = [g for g in glosses(nn) if g["id"] in english]
        short = [g for g in gs if 40 < len(g["latin"]) < LONG][::97][:2]
        long = [g for g in gs if LONG <= len(g["latin"]) < 550][::61][:1]
        picked += [(g, english[g["id"]]) for g in short + long]
    return "\n\n".join(f"Latin: {g['latin']}\nEnglish: {e}" for g, e in picked)


def system_prompt(task: str) -> list:
    return [{"type": "text", "text": RULES + "\n\nExamples of the translation wanted (from earlier books):\n\n"
             + examples() + "\n\n" + task, "cache_control": {"type": "ephemeral"}}]


DRAFT_TASK = """Your task: translate each gloss you are given. Reply with every gloss's id and its English."""
REVIEW_TASK = """Your task: check translations someone else made. For each gloss you get the Latin and a draft \
English. Read the Latin first and work out its sense yourself; then compare. Report only drafts that are wrong: a \
meaning error (a dropped or misplaced negation, a comparison turned into a statement, a clause attached to the \
wrong noun, a wrong referent, a misread word), an omission or addition, or a Scripture quotation not in the given \
Douay-Rheims wording. For each, give the whole corrected English and a few words on what was wrong. Don't report \
matters of style. If every draft is right, report nothing."""
LEMMA_TASK = """Your task: translate the lemmas, the words of the Bible verse a gloss is written over. Each comes with \
the Douay-Rheims text of its verse: give the Douay-Rheims words that match the lemma's words, exactly, in the \
Douay's spelling: only those words, nothing from the rest of the verse ("Cognovit" is "knoweth", not "The ox \
knoweth"). A lemma in capitals gets its Douay words in ordinary sentence case ("IN DIEBUS OZIE": "In the days of \
Ozias"). Where the lemma is not words of the verse but a heading (HIERONYMUS, ALLEGORICE, MORALITER, \
INTERLINEARIS...), give the heading in English: "Jerome", "Allegorically", "Morally" and so on."""

SCHEMA = {
    "draft": {"type": "object", "additionalProperties": False, "required": ["glosses"], "properties": {
        "glosses": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                               "required": ["id", "english"],
                                               "properties": {"id": {"type": "string"},
                                                              "english": {"type": "string"}}}}}},
    "review": {"type": "object", "additionalProperties": False, "required": ["fixes"], "properties": {
        "fixes": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                             "required": ["id", "english", "why"],
                                             "properties": {"id": {"type": "string"}, "english": {"type": "string"},
                                                            "why": {"type": "string"}}}}}},
    "lemma": {"type": "object", "additionalProperties": False, "required": ["lemmas"], "properties": {
        "lemmas": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                              "required": ["n", "english"],
                                              "properties": {"n": {"type": "integer"},
                                                             "english": {"type": "string"}}}}}},
}


def chunks(items: list, most: int, chars: int) -> list:
    """Runs of glosses in reading order, at most `most` glosses or about `chars` characters of Latin each."""
    out, cur, size = [], [], 0
    for g in items:
        if cur and (len(cur) >= most or size + len(g["latin"]) > chars):
            out.append(cur)
            cur, size = [], 0
        cur.append(g)
        size += len(g["latin"])
    return out + ([cur] if cur else [])


def gloss_block(chunk: list, dr: Douay, name: str, drafts: dict = None) -> str:
    """The request's text: the verses with their Douay text, each gloss under its verse, and the Douay text of the
    verses the glosses share words with."""
    lines, quoted, last_verse, last_lemma = [], {}, None, None
    for g in chunk:
        if (g["c"], g["v"]) != last_verse:
            last_verse, last_lemma = (g["c"], g["v"]), None
            lines.append(f"\n=== {name} {g['c']}:{g['v']} (Douay-Rheims: {dr.verse(name, g['c'], g['v'])})")
        if g["lemma"] != last_lemma:
            last_lemma = g["lemma"]
            lines.append(f"-- on the words: {g['lemma']}")
        kind = "interlinear" if g["type"] == "interl" else "marginal"
        lines.append(f"[{g['id']}] ({kind}) {g['latin']}")
        if drafts is not None:
            lines.append(f"   DRAFT: {drafts.get(g['id'], '(missing)')}")
        for ref in dr.quoted(g["latin"]):
            if ref[:2] != (name, g["c"]) or ref[2] != g["v"]:
                quoted[ref] = dr.verse(*ref)
    if quoted:
        lines.append("\nDouay-Rheims verses these glosses share words with (use their wording where quoted):")
        lines += [f"{b} {c}:{v}: {t}" for (b, c, v), t in quoted.items()]
    return "\n".join(lines).strip()


def request(custom_id: str, model_effort: tuple, system: list, text: str, schema: dict) -> Request:
    model, effort = model_effort
    return Request(custom_id=custom_id, params=MessageCreateParamsNonStreaming(
        model=model, max_tokens=32000, system=system,
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": text}]))


# ── batches ──────────────────────────────────────────────────────────────────

def run_batch(client, folder: Path, stage: str, requests: list) -> dict:
    """Submit the requests not yet answered, wait, and save each answer as folder/stage/<custom_id>.json."""
    out = folder / stage
    out.mkdir(parents=True, exist_ok=True)
    todo = [r for r in requests if not (out / f"{r['custom_id']}.json").exists()]
    if todo and DRY:
        p = todo[0]["params"]
        print(p["system"][0]["text"][-1500:], "\n----\n", p["messages"][0]["content"][:4000], "\n----")
        for r in todo:
            p = r["params"]
            r["tokens"] = client.messages.count_tokens(model=p["model"], system=p["system"],
                                                       messages=p["messages"]).input_tokens
        print(f"{stage}: {len(todo)} requests, system {client.messages.count_tokens(model=p['model'], system=p['system'], messages=[{'role': 'user', 'content': 'x'}]).input_tokens:,} tokens; "
              f"inputs {sum(r['tokens'] for r in todo):,} tokens in all (system included each time)")
        sys.exit(0)
    if todo:
        batch = client.messages.batches.create(requests=todo)
        (folder / f"{stage}_batch.txt").write_text(batch.id)
        print(f"{stage}: batch {batch.id}, {len(todo)} requests")
        while batch.processing_status != "ended":
            time.sleep(60)
            batch = client.messages.batches.retrieve(batch.id)
            n = batch.request_counts
            print(f"  {time.strftime('%H:%M')} processing {n.processing}, done {n.succeeded}, errors {n.errored}")
        for result in client.messages.batches.results(batch.id):
            if result.result.type != "succeeded":
                print(f"  {result.custom_id}: {result.result.type} (re-run the stage to retry)")
                continue
            msg = result.result.message
            if msg.stop_reason not in ("end_turn",):
                print(f"  {result.custom_id}: stopped ({msg.stop_reason}); re-run the stage to retry")
                continue
            text = next((b.text for b in msg.content if b.type == "text"), "")
            u = msg.usage
            (out / f"{result.custom_id}.json").write_text(json.dumps({
                "model": msg.model, "answer": json.loads(text),
                "usage": {"input": u.input_tokens, "output": u.output_tokens,
                          "cache_read": u.cache_read_input_tokens or 0,
                          "cache_write": u.cache_creation_input_tokens or 0}}, ensure_ascii=False), encoding="utf-8")
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in out.glob("*.json")}


def cost(folder: Path) -> None:
    total = 0.0
    for stage in sorted(p for p in folder.iterdir() if p.is_dir()):
        by_model = defaultdict(Counter)
        for p in stage.glob("*.json"):
            r = json.loads(p.read_text(encoding="utf-8"))
            model = next(m for m in PRICES if r["model"].startswith(m))
            by_model[model].update(r["usage"])
        for model, u in by_model.items():
            pi, po, pr, pw = PRICES[model]
            dollars = (u["input"] * pi + u["output"] * po + u["cache_read"] * pr + u["cache_write"] * pw) / 1e6 / 2
            total += dollars
            print(f"{stage.name:7} {model:18} in {u['input']:>9,} out {u['output']:>9,} "
                  f"cache read {u['cache_read']:>10,} write {u['cache_write']:>8,}  ${dollars:.2f}")
    print(f"total ${total:.2f}")


# ── stages ───────────────────────────────────────────────────────────────────

def selection(nn: str, pilot: int) -> list:
    gs = glosses(nn)
    if not pilot:
        return gs
    short = [g for g in gs if len(g["latin"]) < LONG][:pilot]
    long = [g for g in gs if len(g["latin"]) >= LONG][:max(5, pilot // 5)]
    keep = {g["id"] for g in short + long}
    return [g for g in gs if g["id"] in keep]


def dr_name(nn: str) -> str:
    """The book's Douay-Rheims name, found by matching its first glossed verse's lemma against the Douay."""
    names = {"26": "Psalms", "33": "Isaias", "34": "Jeremias", "36": "Baruch", "37": "Ezechiel", "38": "Daniel",
             "52": "1 Machabees", "53": "2 Machabees", "86": "Baruch",   # (the Letter of Jeremias is Baruch 6)
             "55": "Matthew", "56": "Mark", "57": "Luke", "58": "John", "74": "Acts", "60": "Romans",
             "61": "1 Corinthians", "62": "2 Corinthians", "63": "Galatians", "64": "Ephesians", "65": "Philippians",
             "66": "Colossians", "67": "1 Thessalonians", "68": "2 Thessalonians", "69": "1 Timothy",
             "70": "2 Timothy", "71": "Titus", "72": "Philemon", "73": "Hebrews", "76": "James", "77": "1 Peter",
             "78": "2 Peter", "79": "1 John", "80": "2 John", "81": "3 John", "82": "Jude", "83": "Apocalypse"}
    if nn not in names:
        sys.exit(f"add book {nn}'s Douay-Rheims name to dr_name()")
    return names[nn]


def draft(client, nn: str, folder: Path, pilot: int) -> None:
    dr, name = Douay(), dr_name(nn)
    gs = selection(nn, pilot)
    reqs = []
    for kind, part, most, chars in (("short", [g for g in gs if len(g["latin"]) < LONG], 30, 4000),
                                    ("long", [g for g in gs if len(g["latin"]) >= LONG], 12, 6000)):
        system = system_prompt(DRAFT_TASK)
        for i, chunk in enumerate(chunks(part, most, chars)):
            reqs.append(request(f"{kind}-{i:04}", DRAFT[kind], system, gloss_block(chunk, dr, name),
                                SCHEMA["draft"]))
    lemmas = list(dict.fromkeys((g["lemma"], g["c"], g["v"]) for g in gs if g["lemma"]))
    lemma_system = system_prompt(LEMMA_TASK)
    for i in range(0, len(lemmas), 60):
        part = lemmas[i:i + 60]
        text = "\n".join(f"{i + j + 1}. {lem}\n   (verse {name} {c}:{v}, Douay-Rheims: {dr.verse(name, c, v)})"
                         for j, (lem, c, v) in enumerate(part))
        reqs.append(request(f"lemma-{i // 60:04}", DRAFT["lemma"], lemma_system, text, SCHEMA["lemma"]))
    (folder / "lemma_order.json").write_text(json.dumps([lem for lem, _, _ in lemmas], ensure_ascii=False),
                                             encoding="utf-8")
    answers = run_batch(client, folder, "draft", reqs)
    drafts = {x["id"]: x["english"] for k, a in answers.items() if not k.startswith("lemma")
              for x in a["answer"]["glosses"]}
    missing = [g for g in gs if g["id"] not in drafts]
    for round_ in range(1, 3):              # a model now and then leaves out a gloss of its chunk: ask again
        if not missing:
            break
        system = system_prompt(DRAFT_TASK)
        reqs = [request(f"fill{round_}-{i:04}", DRAFT["long"], system, gloss_block(chunk, dr, name), SCHEMA["draft"])
                for i, chunk in enumerate(chunks(missing, 8, 4000))]
        answers = run_batch(client, folder, "draft", reqs)
        drafts = {x["id"]: x["english"] for k, a in sorted(answers.items()) if not k.startswith("lemma")
                  for x in a["answer"]["glosses"]}
        missing = [g for g in gs if g["id"] not in drafts]
    missing = [g["id"] for g in missing]
    (folder / "draft.json").write_text(json.dumps(drafts, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"draft: {len(drafts)} of {len(gs)} glosses" + (f"; missing {missing[:10]}" if missing else ""))


def review(client, nn: str, folder: Path, pilot: int) -> None:
    dr, name = Douay(), dr_name(nn)
    gs = selection(nn, pilot)
    drafts = json.loads((folder / "draft.json").read_text(encoding="utf-8"))
    gs = [g for g in gs if g["id"] in drafts]
    reqs = []
    system = system_prompt(REVIEW_TASK)
    # not the shortest: at low effort, the Isaiah pilot's review of short glosses fixed one quotation in fifty and
    # missed the one meaning error; at medium effort on Isaiah's glosses of 80-250 characters (16% wrong in a sample
    # of 25) it caught three of the four errors found by hand and one more. Those under MID (5% wrong in a sample of
    # 40, mostly interlinear words and phrases) would cost more to review than the whole of the rest.
    for kind, part, most, chars in (("mid", [g for g in gs if MID <= len(g["latin"]) < LONG], 25, 9000),
                                    ("long", [g for g in gs if len(g["latin"]) >= LONG], 12, 6000)):
        for i, chunk in enumerate(chunks(part, most, chars)):
            reqs.append(request(f"{kind}-{i:04}", REVIEW[kind], system, gloss_block(chunk, dr, name, drafts),
                                SCHEMA["review"]))
    answers = run_batch(client, folder, "review", reqs)
    fixes = {x["id"]: x for a in answers.values() for x in a["answer"]["fixes"]
             if x["id"] in drafts and x["english"].strip() and x["english"].strip() != drafts[x["id"]].strip()}
    (folder / "review.json").write_text(json.dumps(fixes, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"review: {len(fixes)} of {len(gs)} drafts corrected")


def curly(text: str) -> str:
    """Our translations' typography: the models answer with straight quotes as often as curly ones."""
    text = re.sub(r"(?<=\w)'(?=\w)", "’", text)
    text = re.sub(r"\bgentile(s?)\b", r"Gentile\1", text)       # as our books and the Douay-Rheims write it
    parts = text.split('"')
    if len(parts) % 2 == 0:                 # an odd number of quote marks: leave them for a person to see
        return text
    return "".join(p + ("“" if i % 2 == 0 else "”") if i < len(parts) - 1 else p
                   for i, p in enumerate(parts))


HEADINGS = {"HIERONYMUS": "Jerome", "AUGUSTINUS": "Augustine", "GREGORIUS": "Gregory", "BEDA": "Bede",
            "RABANUS": "Rabanus", "STRABUS": "Strabo", "ISIDORUS": "Isidore", "ALCUINUS": "Alcuin", "ORIGENES": "Origen",
            "AMBROSIUS": "Ambrose", "HAIMO": "Haimo", "ALLEGORICE": "Allegorically", "MORALITER": "Morally",
            "MYSTICE": "Mystically", "HISTORICE": "Historically"}


def unheaded(g: dict, english: str) -> str:
    """Without the heading the gloss stands under, which the models now and then repeat at the start of the English
    ("Allegorically. ...") although the bot shows it separately; kept when the Latin itself begins with it."""
    label = HEADINGS.get(g["lemma"].strip(" .").upper())
    if label and english.startswith(label + ". ") and not g["latin"].upper().startswith(g["lemma"].strip(" .").upper()):
        return english[len(label) + 2:]
    return english


def merge(nn: str, folder: Path) -> None:
    gs = glosses(nn)
    drafts = json.loads((folder / "draft.json").read_text(encoding="utf-8"))
    fixes = json.loads((folder / "review.json").read_text(encoding="utf-8"))
    # the review was told to report only errors, but now and then rewords a draft it says itself is fine; those
    # rewordings aren't taken (on Isaiah, 23 of 299; ones it calls "minor" but says change the sense are kept)
    fixes = {k: x for k, x in fixes.items()
             if not re.search(r"(?i)no substantive|no real error|no error|sense (is )?(the )?(same|unchanged|retained)|^minor[.;]?$|^minor; matches|minor wording only|draft is fine in sense|no change in sense",
                              x["why"])}
    english = {g["id"]: curly(unheaded(g, fixes[g["id"]]["english"] if g["id"] in fixes else drafts[g["id"]]))
               for g in gs if g["id"] in drafts}
    missing = [g["id"] for g in gs if g["id"] not in english]
    if missing:
        sys.exit(f"{len(missing)} glosses have no translation yet (re-run draft): {missing[:10]}")
    order = json.loads((folder / "lemma_order.json").read_text(encoding="utf-8"))
    lemmas = {}
    for p in sorted((folder / "draft").glob("lemma-*.json")):
        for x in json.loads(p.read_text(encoding="utf-8"))["answer"]["lemmas"]:
            if 1 <= x["n"] <= len(order):
                lemmas.setdefault(order[x["n"] - 1], x["english"])
    (ENGLISH / f"{nn}.json").write_text(json.dumps(english, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (LEMMAS / f"{nn}.json").write_text(json.dumps(lemmas, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(english)} glosses, {len(lemmas)} of {len(order)} lemmas -> {ENGLISH / f'{nn}.json'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("book")
    ap.add_argument("stage", choices=["draft", "review", "merge", "cost"])
    ap.add_argument("--pilot", type=int, default=0)
    ap.add_argument("--dry", action="store_true", help="show the first request and count tokens; submit nothing")
    a = ap.parse_args()
    global DRY
    DRY = a.dry
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)   # progress shows while it waits
    folder = STATE / a.book / (f"pilot{a.pilot}" if a.pilot else "full")
    folder.mkdir(parents=True, exist_ok=True)
    client = anthropic.Anthropic()
    if a.stage == "draft":
        draft(client, a.book, folder, a.pilot)
    elif a.stage == "review":
        review(client, a.book, folder, a.pilot)
    elif a.stage == "merge":
        if a.pilot:
            sys.exit("a pilot isn't merged into the book")
        merge(a.book, folder)
    cost(folder)


if __name__ == "__main__":
    main()
