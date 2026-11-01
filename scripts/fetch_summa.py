"""
Aquinas's Summa Theologica (the Fathers of the English Dominican Province's translation) from newadvent.org, every
article of every question, into data/summa.json for asking the library (bot_commands/ask.py), which can't search a
website. !summa still reads newadvent live. Like data/hadith/, the file isn't committed: this script rebuilds it.

    python scripts/fetch_summa.py        (about 611 pages, a second apart; pages already fetched are kept)

data/summa.json: {"ST I.2.3": "Article 3. Whether God exists?\n\nObjection 1. ...\n\nOn the contrary, ...\n\nI answer
that, ...\n\nReply to Objection 1. ..."}, in order.
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import summa_lookup as sl  # noqa: E402
from corpus_clean import split_joined  # noqa: E402

CACHE = ROOT / "scripts" / ".cache" / "summa"
OUT = ROOT / "data" / "summa.json"
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; one-off, a page a second)"}


def page(part: int, question: int) -> str:
    path = CACHE / f"{part}{question:03d}.htm"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        for attempt in range(3):
            try:
                req = urllib.request.Request(sl._summa_url(part, question), headers=UA)
                path.write_bytes(urllib.request.urlopen(req, timeout=60).read())
                break
            except Exception as e:
                print(f"  {part}{question:03d}: {type(e).__name__} {e}; retrying")
                time.sleep(5 * (attempt + 1))
        else:
            raise SystemExit(f"could not fetch {sl._summa_url(part, question)}")
        time.sleep(1)
    return path.read_bytes().decode("utf-8", "replace")


def article_text(art: dict) -> str:
    parts = [art["title"]] + art["objections"]
    if art["on_the_contrary"]:
        parts.append("On the contrary, " + art["on_the_contrary"])
    if art["i_answer_that"]:
        parts.append("I answer that, " + art["i_answer_that"])
    parts += art["replies"]
    text = "\n\n".join(re.sub(r"\s+", " ", p.replace("**", "")).strip() for p in parts if p.strip())
    return split_joined(text, frozenset())                  # ("toYou", "theWorlds": words run together)


def main() -> None:
    out = {}
    for part, last in sl.PART_Q_MAX.items():
        for q in range(1, last + 1):
            html = page(part, q)
            info = sl._parse_question_page(html, q)
            numbers = [n for n, _ in info["articles"]] if info else []
            for n in numbers:
                art = sl._parse_article(html, n)
                if art and (art["i_answer_that"] or art["objections"]):
                    out[f"ST {sl.PART_DISPLAY[part]}.{q}.{n}"] = article_text(art)
        print(f"  {sl.PART_LONG[part]}: {sum(k.startswith(f'ST {sl.PART_DISPLAY[part]}.') for k in out)} articles")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(out)} articles, {sum(len(t.split()) for t in out.values()):,} words -> {OUT}")


if __name__ == "__main__":
    main()
