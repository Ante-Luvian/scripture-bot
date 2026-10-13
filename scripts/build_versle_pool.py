"""
Build data/versle_pool.json for !versle: well-known verses, one a day.

"Well-known" is measured from OpenBible.info's cross-references
(data/cross_references/), where readers vote on links between verses: a
verse that many voted links point to, and that points to many itself, is
one people know and look up. The top verses (short enough to read in a
puzzle, from the 66 books) are shuffled once with a fixed seed, so puzzle N
is always the same verse; rerun only to extend the pool.

    python scripts/build_versle_pool.py
"""
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
XREFS = ROOT / "data" / "cross_references" / "cross_references.json"
OUT = ROOT / "data" / "versle_pool.json"
SIZE = 730                                   # two years of puzzles
SEED = 20261013


def main():
    from scripture_lookup import ScriptureLookup
    lookup = ScriptureLookup()
    xrefs = json.loads(XREFS.read_text(encoding="utf-8"))
    score = Counter()
    for source, targets in xrefs.items():
        score[source] += sum(v for _, v in targets[:10] if v > 0)
        for target, votes in targets:
            if votes > 0 and "-" not in target:
                score[target] += votes
    pool = []
    for ref, _ in score.most_common():
        if len(pool) == SIZE:
            break
        result = lookup.get_verse(ref)
        if not result.get("found"):
            continue
        text = re.sub(r"\*\*\[\d+\]\*\*\s*", "", result["text"]).strip()
        if 40 <= len(text) <= 260:
            pool.append(result["reference"])
    random.Random(SEED).shuffle(pool)
    OUT.write_text(json.dumps({"source": "Well-known verses by OpenBible.info cross-reference votes",
                               "verses": pool}, indent=1), encoding="utf-8")
    print(f"{len(pool)} verses; first: {pool[:8]}")


if __name__ == "__main__":
    main()
