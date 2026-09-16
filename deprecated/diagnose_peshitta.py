#!/usr/bin/env python3
"""Run this in your scripture bot directory to diagnose file formats."""
from pathlib import Path

BASE = Path.cwd()

print("=== Peshitta OT plain/0.1 ===")
p = BASE / "peshitta" / "plain" / "0.1"
if p.exists():
    files = sorted(p.glob("*.txt"))
    print(f"Found {len(files)} .txt files")
    if files:
        f = next((x for x in files if "Genesis" in x.stem), files[0])
        print(f"First 10 lines of {f.name}:")
        with open(f, encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if i >= 10: break
                print(f"  {i+1}: {repr(line.rstrip())}")
else:
    print(f"NOT FOUND: {p}")
    # Check what IS in the peshitta repo
    repo = BASE / "peshitta"
    if repo.exists():
        print("Peshitta repo contents:")
        for item in sorted(repo.iterdir()):
            print(f"  {item.name}/") if item.is_dir() else print(f"  {item.name}")
        # Check plain/ subdirs
        plain = repo / "plain"
        if plain.exists():
            print("plain/ subdirs:", [x.name for x in plain.iterdir()])

print()
print("=== Syriac NT ===")
for nt_path in [
    BASE / "syrnt" / "plain" / "0.1",
    BASE / "syrnt" / "source" / "0.1",
    BASE / "syrnt" / "plain",
    BASE / "syrnt",
]:
    files = sorted(nt_path.glob("*.txt")) if nt_path.exists() else []
    if files:
        print(f"Found {len(files)} .txt files in {nt_path.relative_to(BASE)}")
        f = next((x for x in files if "Matthew" in x.stem or "Matt" in x.stem.title()), files[0])
        print(f"First 10 lines of {f.name}:")
        with open(f, encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if i >= 10: break
                print(f"  {i+1}: {repr(line.rstrip())}")
        break
    elif nt_path.exists():
        print(f"{nt_path.relative_to(BASE)} exists but no .txt files")
        subs = [x.name for x in nt_path.iterdir()]
        print(f"  Contents: {subs[:10]}")
