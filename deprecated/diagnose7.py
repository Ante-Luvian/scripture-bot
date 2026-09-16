import urllib.request, re, time

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Bot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

# === NIC ETHICS: test the exact match logic ===
print("=== NIC ETHICS ===")
text = fetch("https://classics.mit.edu/Aristotle/nicomachaen.mb.txt")
text = text.replace('\r', '')
text = re.sub(r'^.*?-{60,}', '', text, flags=re.DOTALL)
text = re.sub(r'-{60,}.*$',  '', text, flags=re.DOTALL)

blocks = re.split(r'\n{2,}', text)
print(f"Total blocks: {len(blocks)}")

# Show first 15 blocks with their match results
for i, block in enumerate(blocks[:15]):
    b = block.strip()
    bm = re.match(r'^BOOK\s+([IVXLCDM]+)$', b, re.IGNORECASE)
    nm = re.match(r'^\d+$', b)
    print(f"  [{i:3}] book={bool(bm)} num={bool(nm)} stripped={b[:40]!r}")

# Count how many bare number blocks exist
num_blocks = [b.strip() for b in blocks if re.match(r'^\d+$', b.strip())]
print(f"\nBare number blocks found: {len(num_blocks)}, first 10: {num_blocks[:10]}")

time.sleep(1)

# === PLOTINUS: test tractate matching ===
print("\n=== PLOTINUS ===")
text2 = fetch("https://classics.mit.edu/Plotinus/enneads.mb.txt")
text2 = text2.replace('\r', '')
text2 = re.sub(r'^.*?-{60,}', '', text2, flags=re.DOTALL)
text2 = re.sub(r'-{60,}.*$',  '', text2, flags=re.DOTALL)

tractate_re = re.compile(r'^(\w+)\s+Tractate\s*$')
section_re  = re.compile(r'^(\d+)\.\s+(.*)')

tractate_matches = []
section_matches = []
for line in text2.split('\n'):
    s = line.strip()
    if tractate_re.match(s):
        tractate_matches.append(s)
    if section_re.match(s):
        section_matches.append(s[:30])

print(f"Tractate matches: {len(tractate_matches)}")
print(f"  {tractate_matches}")
print(f"Section matches: {len(section_matches)}, first 10: {section_matches[:10]}")
