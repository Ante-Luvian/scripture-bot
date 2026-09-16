"""
diagnose3.py — inspect actual structure around section breaks
Run: python diagnose3.py
"""
import re, urllib.request, time

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Bot/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace").replace('\r','')

# ── Plotinus: show lines 14-50 (first tractate, first sections)
print("="*60)
print("PLOTINUS — lines around first sections")
print("="*60)
text = fetch("https://classics.mit.edu/Plotinus/enneads.mb.txt")
lines = text.split('\n')
for i, l in enumerate(lines[10:80], 10):
    print(f"{i:4}: {l!r}")

time.sleep(1)

# ── Nic Ethics: show first 60 lines of content
print("\n" + "="*60)
print("NICOMACHEAN ETHICS — lines around first sections")
print("="*60)
text2 = fetch("https://classics.mit.edu/Aristotle/nicomachaen.mb.txt")
# Find BOOK I
idx = text2.find('BOOK I')
chunk = text2[idx:idx+2000] if idx != -1 else text2[:2000]
for i, l in enumerate(chunk.split('\n')[:60]):
    print(f"{i:4}: {l!r}")
