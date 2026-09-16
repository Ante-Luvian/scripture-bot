"""
clean_stats.py — run once to clean up bad entries in stats.json
"""
import json, re
from pathlib import Path

path = Path("data/stats.json")
if not path.exists():
    print("No stats.json found")
    exit()

stats = json.loads(path.read_text(encoding="utf-8"))

# Clean book_counts: remove bare numbers, single chars
bc = stats.get("book_counts", {})
bad_books = [k for k in bc if k.isdigit() or len(k) <= 1]
for k in bad_books:
    print(f"  Removing book: {k!r} ({bc[k]})")
    del bc[k]

# Clean verse_counts: remove refs with no colon (chapter-only refs like "Quran 2")
vc = stats.get("verse_counts", {})
bad_verses = [k for k in vc if ":" not in k]
for k in bad_verses:
    print(f"  Removing verse: {k!r} ({vc[k]})")
    del vc[k]

stats["book_counts"] = bc
stats["verse_counts"] = vc
path.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"✓ stats.json cleaned ({len(bad_books)} bad books, {len(bad_verses)} bad verses removed)")
