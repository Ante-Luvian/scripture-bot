"""
Draws every chant's score in square notation, for the 🎼 Score button under !hymn:
data/hymns/scores/chant-NNNNN-P.png (GregoBase id, page). Rebuilt on the bot's machine and
not kept in git, being made from the GregoBase scores.

    python scripts/build_chant_scores.py          # what's missing
    python scripts/build_chant_scores.py --all    # everything again
    python scripts/build_chant_scores.py 3326     # just these GregoBase ids

The score is the same gabc the organ and the singer use (build_chant.full_score). It is
laid out and drawn by scripts/score/render.js (exsurge under Node; `npm install` there,
which this does when needed); long scores are then cut into pages at the gaps between
staves, so Discord shows them at a readable size.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_chant as bc

ROOT = bc.ROOT
SCORE_JS = Path(__file__).resolve().parent / "score"
OUT = ROOT / "data" / "hymns" / "scores"
CHANTS = ROOT / "data" / "hymns" / "more_hymns.json"
BATCH = 50                     # scores per Node process
PAGE = 1500                    # the tallest page, in pixels (about four staves)
PAPER = (255, 253, 248)        # render.js's background


def pages(full: Path, gid: int) -> int:
    """Cut a drawn score into pages at blank bands between staves; returns how many."""
    img = Image.open(full).convert("RGB")
    w, h = img.size
    px = img.load()
    step = max(1, w // 400)
    blank = [all(sum(abs(a - b) for a, b in zip(px[x, y], PAPER)) < 30 for x in range(0, w, step)) for y in range(h)]
    cuts, top = [], 0
    while h - top > PAGE:
        limit = top + PAGE
        run_end, best = None, None
        for y in range(limit, top + PAGE // 3, -1):            # the lowest blank band that fits
            if blank[y]:
                run_end = run_end or y
            elif run_end:
                best = (y + run_end) // 2
                if run_end - y >= 12:
                    break
                run_end = None
        cut = best or limit
        cuts.append(cut)
        top = cut
    bounds = [0] + cuts + [h]
    for old in OUT.glob(f"chant-{gid:05d}-*.png"):
        old.unlink()
    for i, (a, b) in enumerate(zip(bounds, bounds[1:]), 1):
        img.crop((0, a, w, b)).save(OUT / f"chant-{gid:05d}-{i}.png", optimize=True)
    return len(bounds) - 1


def main():
    if not shutil.which("node"):
        sys.exit("node isn't on the PATH")
    if not (SCORE_JS / "node_modules").exists():
        subprocess.run("npm install --no-audit --no-fund", cwd=SCORE_JS, shell=True, check=True)
    OUT.mkdir(parents=True, exist_ok=True)
    chants = [h for h in json.loads(CHANTS.read_text(encoding="utf-8"))["hymns"] if h.get("gregobase")]
    only = {int(a) for a in sys.argv[1:] if a.isdigit()}
    rows = {int(r["id"]): r for r in bc.chosen(bc.corpus())}
    todo = [h["gregobase"] for h in chants if (not only or h["gregobase"] in only)
            and ("--all" in sys.argv or only or not list(OUT.glob(f"chant-{h['gregobase']:05d}-*.png")))]
    print(f"{len(todo)} to draw", flush=True)
    counts = {}
    # a fresh Node process for each batch (jsdom holds on to memory across hundreds of scores),
    # and each batch's pages saved before the next, so an interrupted run keeps what it drew
    for start in range(0, len(todo), BATCH):
        batch = todo[start:start + BATCH]
        with tempfile.TemporaryDirectory() as tmp:
            jobs = [{"gabc": bc.full_score(rows[g]), "out": str(Path(tmp) / f"{g}.png")} for g in batch]
            (Path(tmp) / "jobs.json").write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
            subprocess.run(["node", "render.js", str(Path(tmp) / "jobs.json")], cwd=SCORE_JS, check=True)
            for g in batch:
                full = Path(tmp) / f"{g}.png"
                if full.exists():
                    counts[g] = pages(full, g)
        print(f"  {start + len(batch)}/{len(todo)}", flush=True)
    missing = [g for g in todo if g not in counts]
    size = sum(f.stat().st_size for f in OUT.glob("*.png"))
    print(f"drew {len(counts)}; pages {sum(counts.values())}, most {max(counts.values(), default=0)}; "
          f"{size / 1e6:.1f} MB; not drawn: {missing}")


if __name__ == "__main__":
    main()
