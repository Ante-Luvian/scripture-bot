## What this changes and why


## Checklist
- [ ] `python -m pytest` passes
- [ ] Commands touched were stress-tested (`python -m pytest -m stress -k "<command>"`)
- [ ] New or renamed command: registry regenerated, INTRODUCTION.md and the `!help` menu updated
- [ ] New or rebuilt corpus: built by a script, `scripts/clean_corpora.py` run, `pytest -m corpus` passes
- [ ] A change users will notice has a CHANGELOG.md entry written for them
- [ ] No runtime state files or rebuildable media committed
