"""
Scrub every corpus file under data/ with corpus_clean (web-page furniture,
licence text, footnotes, page markers, indexes, Beta Code). Idempotent.
The files are cleaned in parallel, one process a core (the whole library took ~10 minutes on one).

    python scripts/clean_corpora.py                      # rewrite the files
    python scripts/clean_corpora.py --dry                # just report what would change
    python scripts/clean_corpora.py patristics esoteric  # only the files under data/ whose path has one of these
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from corpus_clean import clean_corpus  # noqa: E402

DATA = ROOT / "data"


def corpus_paths(only=()):
    """The corpus files under data/ (a dict with "books"), those whose path has one of `only` if given."""
    for path in sorted(DATA.rglob("*.json")):
        rel = path.relative_to(DATA).as_posix()
        if "New folder" in path.parts or only and not any(o in rel for o in only):
            continue
        yield path


def _load(path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) and isinstance(payload.get("books"), dict) else None


def corpus_files(only=()):
    for path in corpus_paths(only):
        payload = _load(path)
        if payload is not None:
            yield path, payload


def clean_file(path, dry=False) -> int:
    """Clean one file (and write it back, unless dry); how many verses changed or went."""
    payload = _load(path)
    if payload is None:
        return 0
    n = clean_corpus(payload, path.relative_to(DATA).as_posix())
    if n and not dry:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=_indent(path)), encoding="utf-8")
    return n


def _clean_one(args):
    path, dry = args
    return path, clean_file(path, dry)


def clean_all(only=(), dry=False, workers=None) -> dict:
    """{path: verses changed} for those that changed, cleaned a process a core."""
    paths = list(corpus_paths(only))
    # the biggest files first, so the last to finish isn't one long file on its own
    paths.sort(key=lambda p: p.stat().st_size, reverse=True)
    # (half the cores: all eight on the largest files at once froze the owner's computer)
    with ProcessPoolExecutor(max_workers=workers or max(2, (os.cpu_count() or 4) // 2)) as pool:
        return {p: n for p, n in pool.map(_clean_one, [(p, dry) for p in paths], chunksize=1) if n}


def main():
    dry = "--dry" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    changed = clean_all(only, dry)
    for path in sorted(changed):
        print(f"{changed[path]:6d}  {path.relative_to(DATA).as_posix()}")
    print(f"{sum(changed.values())} verses changed or removed" + (" (dry run)" if dry else ""))


def _indent(path: Path):
    """Keep each file's own layout (compact, or indented by n spaces)."""
    with open(path, encoding="utf-8") as f:
        f.readline()
        second = f.readline()
    return (len(second) - len(second.lstrip(" "))) or None if second else None


if __name__ == "__main__":
    main()
