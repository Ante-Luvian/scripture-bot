"""
Louis Ginzberg's The Legends of the Jews (1909-1913), volumes 1-4 (the stories; 5-6 are his notes, 7 the index), from
Project Gutenberg #1493, #1494, #2881, #2882, into data/jewish/legends_of_the_jews.json.

A chapter is volume.chapter ("Legends of the Jews 1.3", The Ten Generations), its paragraphs the verses, each section's
title ("The Ascension of Enoch") in italics leading its first paragraph. Left out: Gutenberg's front and back matter,
the volume's title pages, contents and preface.

    python scripts/build_jewish_legends.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_platonists import blocks, expect, gutenberg, split, text  # noqa: E402

OUT = ROOT / "data" / "jewish" / "legends_of_the_jews.json"
VOLUMES = {1: 1493, 2: 1494, 3: 2881, 4: 2882}
ROMAN = re.compile(r"^([IVXLC]+)\.?\s+(.+)$")
SMALL = {"of", "the", "and", "to", "in", "a", "an", "on", "by", "for", "from", "at", "with", "his", "her", "its"}


def roman(s: str) -> int:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    return sum(-vals[c] if i + 1 < len(s) and vals[s[i + 1]] > vals[c] else vals[c] for i, c in enumerate(s))


def title(s: str) -> str:
    """ "THE ASCENSION OF ENOCH" -> "The Ascension of Enoch" (keeping "Mt." and roman numerals)."""
    words = s.strip().split()
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if re.fullmatch(r"[IVXLC]+[.,]?", w) and len(w) > 1:
            out.append(w)
        elif i and lw in SMALL:
            out.append(lw)
        else:
            out.append(lw[:1].upper() + lw[1:])
    t = " ".join(out)
    return re.sub(r"(?<=['’])S\b", "s", t)


NOT_STORIES = re.compile(r"Project Gutenberg|^The Legends of the Jews$|^by Louis|^TRANSLATED|^VOLUME|^CONTENTS$|^PREFACE$|"
                         r"^INDEX|^NOTES$|^FOOTNOTES$", re.IGNORECASE)


def volume(number: int, ebook: int) -> dict:
    """{"<volume>.<story>": {paragraph: text}}: every titled story (an h2 or h3) a chapter, numbered through the
    volume; Ginzberg's chapter headings ("I JOSEPH", "II. THE JUDGES") lead the story after them. (Volume 3's e-text
    has lost its chapter headings: its stories are numbered all the same.)"""
    t = gutenberg(ebook)
    t = t[:t.find("*** END")] if "*** END" in t else t
    t = re.sub(r'(?is)<span class="pagenum"[^>]*>.*?</span>|<a [^>]*class="pginternal"[^>]*>\s*\[?\d+\]?\s*</a>', "", t)
    stories, chapter_head = [], None
    for head, body in split(t, r"(?is)<h[23][^>]*>(.*?)</h[23]>"):
        h = text(head).strip()
        if not h or NOT_STORIES.search(h):
            continue
        m = ROMAN.match(h)
        paras = blocks(body)
        if m:                                            # (one of Ginzberg's chapters)
            chapter_head = f"*{m.group(1)}. {title(m.group(2))}*"
            if not paras:
                continue
            h = title(m.group(2))                        # (a chapter with no sections: itself the story)
        else:
            h = title(h)
        if not paras:                                    # (a heading with no text: a chapter's, unnumbered)
            chapter_head = f"*{h}*"
            continue
        lead = [chapter_head] if chapter_head else []
        paras[0] = "\n".join(lead + [f"*{h}*", paras[0]])
        chapter_head = None
        stories.append(paras)
    expect(len(stories) > 20, f"Legends vol. {number}: {len(stories)} stories")
    return {f"{number}.{s}": {str(i + 1): p for i, p in enumerate(paras)} for s, paras in enumerate(stories, 1)}


def main() -> None:
    chapters = {}
    for number, ebook in VOLUMES.items():
        vol = volume(number, ebook)
        expect(vol, f"Legends vol. {number}: no chapters")
        print(f"  volume {number}: chapters {list(vol)[0]}-{list(vol)[-1]}, {sum(len(c) for c in vol.values())} paragraphs")
        chapters.update(vol)
    payload = {"source": "Louis Ginzberg, trans. Henrietta Szold and Paul Radin (1909-13)",
               "books": {"Legends of the Jews": chapters}}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    words = sum(len(v.split()) for c in chapters.values() for v in c.values())
    print(f"Legends of the Jews: {len(chapters)} chapters, {words:,} words -> {OUT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
