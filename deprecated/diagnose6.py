import urllib.request, re

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Bot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

# === PLOTINUS: find all lines containing "Tractate" ===
print("=== PLOTINUS: all lines with 'Tractate' ===")
text = fetch("https://classics.mit.edu/Plotinus/enneads.mb.txt")
for i, line in enumerate(text.split('\n')):
    if 'Tractate' in line:
        print(f"  {i:5}: {line!r}")

# === NIC ETHICS: exact bytes of block [1] ===
print("\n=== NIC ETHICS: repr of raw block around '1 ' ===")
text2 = fetch("https://classics.mit.edu/Aristotle/nicomachaen.mb.txt")
idx = text2.find('BOOK I\n\n')
chunk = text2[idx:idx+30]
print(f"  Raw: {chunk!r}")
# Check each char
for i, c in enumerate(chunk):
    if ord(c) > 127 or ord(c) < 32:
        print(f"  char {i}: ord={ord(c)} ({c!r})")
