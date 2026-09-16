import urllib.request, re

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Bot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

# Check file sizes and section counts
print("=== PLOTINUS ===")
text = fetch("https://classics.mit.edu/Plotinus/enneads.mb.txt")
print(f"File size: {len(text)} chars")
tractates = re.findall(r'(\w+) Tractate ', text)
print(f"All tractate names found: {tractates}")
sections = re.findall(r'\n(\d+)\. ', text)
print(f"Section markers found: {len(sections)}, values: {sections[:20]}")

print("\n=== NIC ETHICS ===")
text2 = fetch("https://classics.mit.edu/Aristotle/nicomachaen.mb.txt")
print(f"File size: {len(text2)} chars")
books = re.findall(r'BOOK ([IVXLCDM]+)', text2)
print(f"Books found: {books}")

# Show what blocks the parser actually sees around section 1 and 2
idx = text2.find('BOOK I')
chunk = text2[idx:idx+600]
blocks = re.split(r'\n{2,}', chunk)
print(f"\nBlocks in first 600 chars:")
for i, b in enumerate(blocks[:8]):
    print(f"  [{i}] stripped={b.strip()!r}  match_num={bool(re.match(r'^\\d+\\s*$', b.strip()))}")
