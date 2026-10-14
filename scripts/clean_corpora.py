"""
Scrub every corpus file under data/ with corpus_clean (web-page furniture,
licence text, footnotes, page markers, indexes, Beta Code). Idempotent.

    python scripts/clean_corpora.py            # rewrite the files
    python scripts/clean_corpora.py --dry      # just report what would change
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from corpus_clean import clean_corpus  # noqa: E402

DATA = ROOT / "data"


def corpus_files():
    for path in sorted(DATA.rglob("*.json")):
        if "New folder" in path.parts:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("books"), dict):
            yield path, payload


def main():
    dry = "--dry" in sys.argv
    total = 0
    for path, payload in corpus_files():
        rel = path.relative_to(DATA).as_posix()
        before = copy.deepcopy(payload) if dry else None
        n = clean_corpus(payload, rel)
        if n:
            total += n
            print(f"{n:6d}  {rel}")
            if not dry:
                path.write_text(json.dumps(payload, ensure_ascii=False, indent=_indent(path)),
                                encoding="utf-8")
    print(f"{total} verses changed or removed" + (" (dry run)" if dry else ""))


def _indent(path: Path):
    """Keep each file's own layout (compact, or indented by n spaces)."""
    with open(path, encoding="utf-8") as f:
        f.readline()
        second = f.readline()
    return (len(second) - len(second.lstrip(" "))) or None if second else None


if __name__ == "__main__":
    main()
