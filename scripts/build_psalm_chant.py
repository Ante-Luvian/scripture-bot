"""
The 150 psalms chanted in Latin, for `!psalm 110 chant`: each sung by the schola and played
on the organ, in a psalm tone, with the Gloria Patri.

    python scripts/build_psalm_chant.py          # what's missing
    python scripts/build_psalm_chant.py --all    # everything again
    python scripts/build_psalm_chant.py 109 50   # just these (Vulgate numbers)

Writes data/psalter/latin_psalms.json (the Latin as the Breviary divides it, the
Douay-Rheims English, the tone; committed) and the audio to data/psalter/chant/
(sung/ and organ/, Ogg; rebuilt here rather than kept in git, being made from the above).
Numbering is the Vulgate's throughout, as the Latin is; the bot maps the usual (Hebrew)
numbers to it. Psalm 118 (Hebrew 119, 176 verses) is sung as the Breviary sings it, in
its 22 sections of eight verses, each with its Gloria Patri.
"""
import concurrent.futures
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_chant as bc
import build_sung_chant as sung
import sung_psalms as sp

ROOT = bc.ROOT
DATA = ROOT / "data" / "psalter" / "latin_psalms.json"
AUDIO = ROOT / "data" / "psalter" / "chant"
# each psalm a tone, the eight in turn (Psalm 109, Dixit Dominus, in the 8th, as in the sample the owner liked)
TONE_ORDER = ["8G", "1D", "2D", "3a", "4E", "5a", "6F", "7c"]
LETTERS = ["Aleph", "Beth", "Gimel", "Daleth", "He", "Vau", "Zain", "Heth", "Teth", "Jod", "Caph", "Lamed", "Mem",
           "Nun", "Samech", "Ain", "Phe", "Sade", "Coph", "Res", "Sin", "Tau"]


def tone_for(n: int) -> str:
    return TONE_ORDER[(n + 3) % 8]


def pieces(n: int, lines: list) -> list:
    """[(file stem, lines)]: one per psalm, Psalm 118 in its 22 sections."""
    if n == 118:
        return [(f"ps-118-{i + 1:02d}", lines[i * 8:(i + 1) * 8]) for i in range(len(lines) // 8)]
    return [(f"ps-{n:03d}", lines)]


def organ(sylls: list, out: Path, title: str) -> None:
    notes, t = [], 0.0
    for _, ns, pause, _ in sylls:
        for pitch, seconds in ns:
            notes.append((t, t + seconds, pitch, 0))
            t += seconds
        t += pause
    shift = 12 * round((62 - statistics.median(p for _, _, p, _ in notes)) / 12)   # as build_chant centres chant
    bc.render([(a, b, p + shift, ch) for a, b, p, ch in notes], out, title)


def render(job) -> str:
    stem, lines, tone, title = job
    t, ending = tone[0], tone[1:]
    sylls = sp.chant_lines(lines, t, ending)
    sung.render(sylls, AUDIO / "sung" / f"{stem}.ogg", title)
    organ(sylls, AUDIO / "organ" / f"{stem}.ogg", title)
    return stem


def main():
    for sub in ("sung", "organ"):
        (AUDIO / sub).mkdir(parents=True, exist_ok=True)
    only = {int(a) for a in sys.argv[1:] if a.isdigit()}
    psalms, jobs = {}, []
    for n in range(1, 151):
        lines = sp.latin_psalm(n)
        tone = tone_for(n)
        parts = pieces(n, lines)
        psalms[str(n)] = {"latin": lines, "english": sp.english_psalm(n), "tone": tone,
                          "parts": [{"file": stem, "lines": len(ls),
                                     "name": LETTERS[i] if n == 118 else ""} for i, (stem, ls) in enumerate(parts)]}
        for i, (stem, ls) in enumerate(parts):
            missing = not (AUDIO / "sung" / f"{stem}.ogg").exists() or not (AUDIO / "organ" / f"{stem}.ogg").exists()
            if (only and n in only) or (not only and ("--all" in sys.argv or missing)):
                title = f"Psalm {n} (Vulgate)" + (f", {LETTERS[i]}" if n == 118 else "") + f", tone {tone}"
                jobs.append((stem, ls, tone, title))
    DATA.write_text(json.dumps({"about": "The psalms in Latin (Vulgate numbering, as the Breviary divides the verses) "
                                         "and the Douay-Rheims, from jgabc; built by scripts/build_psalm_chant.py.",
                                "psalms": psalms}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(jobs)} to render")
    with concurrent.futures.ProcessPoolExecutor() as pool:
        futures = {pool.submit(render, j): j[0] for j in jobs}
        for done, f in enumerate(concurrent.futures.as_completed(futures), 1):
            try:
                f.result()
            except Exception as e:
                print(f"  {futures[f]}: {e}")
            if done % 25 == 0:
                print(f"  {done}/{len(jobs)}", flush=True)
    sizes = sorted(((f.stat().st_size, f.name) for f in (AUDIO / "sung").glob("*.ogg")), reverse=True)
    print(f"sung {sum(s for s, _ in sizes) / 1e6:.1f} MB, organ "
          f"{sum(f.stat().st_size for f in (AUDIO / 'organ').glob('*.ogg')) / 1e6:.1f} MB; largest {sizes[:3]}")


if __name__ == "__main__":
    main()
