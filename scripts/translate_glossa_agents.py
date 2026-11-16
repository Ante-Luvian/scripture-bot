"""The Glossa translated by Claude Code agents on the owner's plan, in place of the API batches of
translate_glossa_api.py (2026-11-16: the API credit ran out). Same rules, examples and Douay material as the API
requests; the agents write the drafts, and the merge makes the same english/NN.json and lemmas/NN.json.

    python scripts/translate_glossa_agents.py NN prep     chunk files in scripts/.cache/glossa_agent/NN/
    python scripts/translate_glossa_agents.py NN status   which chunks are done, which glosses are missing
    python scripts/translate_glossa_agents.py NN merge    english/NN.json and lemmas/NN.json
    python scripts/translate_glossa_agents.py NN review-prep 006,007,...   review files for those chunks' drafts
    python scripts/translate_glossa_agents.py NN review-apply              corrections into english/NN.json

Haiku agents draft (the owner's choice, to spare his plan's usage); Sonnet agents review the drafts whose Latin is 80
characters or more, as the API pipeline did (John, 2026-11-16: 2 of 10 sampled long Haiku notes had errors unreviewed).

Each chunk_XXX.txt is one agent's job: it reads INSTRUCTIONS.md and the chunk and writes out_XXX.json ({id:
English}); each lemma_XXX.txt gets lemma_out_XXX.json ({number: English}). Agents work through a session's usage
limits, so a book can take several sessions: status shows what's left.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import translate_glossa_api as api

WORK = api.ROOT / "scripts" / ".cache" / "glossa_agent"
LATIN_PER_CHUNK, MOST_PER_CHUNK, LEMMAS_PER_CHUNK = 14000, 120, 250

TASK = """Your task: translate every gloss in the chunk file you are given, and write the result with the Write tool as \
a JSON object {"gloss id": "English", ...} to the output file named in your instructions: every id in the chunk, \
nothing else in the file. Write JSON strings properly escaped; use curly quotes (“ ” ‘ ’) inside the English, never \
straight double quotes. When you have written it, read the Latin of the longer glosses once more against your \
English for the errors listed in the rules (negations, comparisons, relative clauses, referents, dropped words, \
quotations not in the Douay wording given) and fix any you find. Reply only with the number of glosses written."""

LEMMA_TASK = api.LEMMA_TASK + """

Write the result with the Write tool as a JSON object {"1": "English", "2": "English", ...}, one entry for every \
numbered lemma in the file, to the output file named in your instructions. Reply only with the number written."""


def folder(nn: str) -> Path:
    return WORK / nn


def prep(nn: str) -> None:
    f = folder(nn)
    f.mkdir(parents=True, exist_ok=True)
    dr, name = api.Douay(), api.dr_name(nn)
    gs = api.glosses(nn)
    examples = api.examples()
    (f / "INSTRUCTIONS.md").write_text(api.RULES + "\n\nExamples of the translation wanted (from earlier books):\n\n"
                                       + examples + "\n\n" + TASK + "\n", encoding="utf-8")
    (f / "LEMMA_INSTRUCTIONS.md").write_text(api.RULES + "\n\n" + LEMMA_TASK + "\n", encoding="utf-8")
    parts = api.chunks(gs, MOST_PER_CHUNK, LATIN_PER_CHUNK)
    for i, chunk in enumerate(parts):
        (f / f"chunk_{i:03}.txt").write_text(api.gloss_block(chunk, dr, name) + "\n", encoding="utf-8")
        (f / f"chunk_{i:03}.ids.json").write_text(json.dumps([g["id"] for g in chunk]), encoding="utf-8")
    lemmas = list(dict.fromkeys((g["lemma"], g["c"], g["v"]) for g in gs if g["lemma"]))
    (f / "lemma_order.json").write_text(json.dumps([lem for lem, _, _ in lemmas], ensure_ascii=False),
                                        encoding="utf-8")
    for i in range(0, len(lemmas), LEMMAS_PER_CHUNK):
        text = "\n".join(f"{i + j + 1}. {lem}\n   (verse {name} {c}:{v}, Douay-Rheims: {dr.verse(name, c, v)})"
                         for j, (lem, c, v) in enumerate(lemmas[i:i + LEMMAS_PER_CHUNK]))
        (f / f"lemma_{i // LEMMAS_PER_CHUNK:03}.txt").write_text(text + "\n", encoding="utf-8")
    print(f"{len(gs)} glosses in {len(parts)} chunks, {len(lemmas)} lemmas in "
          f"{-(-len(lemmas) // LEMMAS_PER_CHUNK)} lemma chunks -> {f}")


REVIEW_TASK = api.REVIEW_TASK + """

Each gloss in the file shows its Latin and, under it, the DRAFT English. Write your corrections with the Write tool as \
a JSON object {"gloss id": {"english": "the whole corrected English", "why": "a few words"}, ...} to the output file \
named in your instructions: only the drafts that are wrong; {} if none are. Use curly quotes inside the English. \
Reply only with the number of corrections."""


def review_prep(nn: str, chunks_: list) -> None:
    """Review files for the drafts of the given chunks whose Latin is MID characters or more (as the API's review:
    shorter ones were rarely wrong): review_XXX.txt, one per chunk, answered in review_out_XXX.json."""
    f, dr, name = folder(nn), api.Douay(), api.dr_name(nn)
    (f / "REVIEW_INSTRUCTIONS.md").write_text(api.RULES + "\n\n" + REVIEW_TASK + "\n", encoding="utf-8")
    english = json.loads((api.ENGLISH / f"{nn}.json").read_text(encoding="utf-8"))
    gs = {g["id"]: g for g in api.glosses(nn)}
    total = 0
    for n in chunks_:
        ids = json.loads((f / f"chunk_{n}.ids.json").read_text(encoding="utf-8"))
        part = [gs[i] for i in ids if len(gs[i]["latin"]) >= api.MID]
        (f / f"review_{n}.txt").write_text(api.gloss_block(part, dr, name, english) + "\n", encoding="utf-8")
        total += len(part)
    print(f"{total} drafts in {len(chunks_)} review files")


def review_apply(nn: str) -> None:
    """The reviewers' corrections into english/NN.json, less those whose reason says the draft was fine (as merge()
    in translate_glossa_api.py); each applied one is listed in review_applied.json for checking."""
    import re
    f = folder(nn)
    p = api.ENGLISH / f"{nn}.json"
    english = json.loads(p.read_text(encoding="utf-8"))
    gs = {g["id"]: g for g in api.glosses(nn)}
    applied = {}
    for q in sorted(f.glob("review_out_*.json")):
        for k, x in load(q).items():
            if k not in english or not isinstance(x, dict) or not str(x.get("english", "")).strip():
                continue
            why = str(x.get("why", ""))
            if re.search(r"(?i)no substantive|no real error|no error|sense (is )?(the )?(same|unchanged|retained)|"
                         r"^minor[.;]?$|minor wording only|draft is fine|no change in sense|correct as", why):
                continue
            new = api.curly(api.unheaded(gs[k], x["english"].strip()))
            if new != english[k]:
                applied[k] = {"draft": english[k], "fix": new, "why": why}
                english[k] = new
    p.write_text(json.dumps(english, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (f / "review_applied.json").write_text(json.dumps(applied, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(applied)} corrections applied")


def load(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"  {p.name}: unreadable ({e})")
        return {}


def drafts(nn: str, report: bool = False) -> dict:
    f, out = folder(nn), {}
    for ids_file in sorted(f.glob("chunk_*.ids.json")):
        n = ids_file.name[6:9]
        ids = json.loads(ids_file.read_text(encoding="utf-8"))
        got = load(f / f"out_{n}.json") if (f / f"out_{n}.json").exists() else {}
        have = {k: v for k, v in got.items() if k in ids and isinstance(v, str) and v.strip()}
        out.update(have)
        if report and len(have) < len(ids):
            missing = [k for k in ids if k not in have]
            print(f"chunk {n}: {len(have)} of {len(ids)}" + (f"; missing {missing[:5]}" if have else " (not done)"))
    return out


def lemmas(nn: str, report: bool = False) -> dict:
    f = folder(nn)
    order = json.loads((f / "lemma_order.json").read_text(encoding="utf-8"))
    out = {}
    for p in sorted(f.glob("lemma_[0-9]*.txt")):
        n = p.stem[6:]
        got = load(f / f"lemma_out_{n}.json") if (f / f"lemma_out_{n}.json").exists() else {}
        for k, v in got.items():
            if str(k).isdigit() and 1 <= int(k) <= len(order) and isinstance(v, str) and v.strip():
                out.setdefault(order[int(k) - 1], v.strip())
    if report:
        print(f"lemmas: {len(out)} of {len(order)}")
    return out


def main():
    nn, stage = sys.argv[1], sys.argv[2]
    sys.stdout.reconfigure(encoding="utf-8")
    if stage == "prep":
        prep(nn)
    elif stage == "status":
        d = drafts(nn, report=True)
        print(f"glosses: {len(d)} of {len(api.glosses(nn))}")
        lemmas(nn, report=True)
    elif stage == "merge":
        gs, d = api.glosses(nn), drafts(nn)
        missing = [g["id"] for g in gs if g["id"] not in d]
        if missing:
            sys.exit(f"{len(missing)} glosses have no translation yet: {missing[:10]}")
        english = {g["id"]: api.curly(api.unheaded(g, d[g["id"]])) for g in gs}
        lem = lemmas(nn, report=True)
        (api.ENGLISH / f"{nn}.json").write_text(json.dumps(english, ensure_ascii=False, indent=1) + "\n",
                                                encoding="utf-8")
        (api.LEMMAS / f"{nn}.json").write_text(json.dumps(lem, ensure_ascii=False, indent=1) + "\n",
                                               encoding="utf-8")
        print(f"{len(english)} glosses, {len(lem)} lemmas merged")
    elif stage == "review-prep":       # NN review-prep 006,007,...  (chunk numbers)
        review_prep(nn, sys.argv[3].split(","))
    elif stage == "review-apply":
        review_apply(nn)
    else:
        sys.exit("stage: prep | status | merge | review-prep CHUNKS | review-apply")


if __name__ == "__main__":
    main()
