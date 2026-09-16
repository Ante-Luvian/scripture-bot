"""diagnose4.py - check exact byte structure"""
import urllib.request, re

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Bot/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")

# Nic Ethics - check raw bytes around section numbers
text = fetch("https://classics.mit.edu/Aristotle/nicomachaen.mb.txt")
idx = text.find('BOOK I')
chunk = text[idx:idx+500]
print("NIC ETHICS - raw repr of first 500 chars after BOOK I:")
print(repr(chunk))
print()

# Count how many times a bare number appears
nums = re.findall(r'\n(\d+) \n', text)
print(f"Bare numbers found with space: {len(nums)}, first 10: {nums[:10]}")
nums2 = re.findall(r'\n(\d+)\n', text)
print(f"Bare numbers found without space: {len(nums2)}, first 10: {nums2[:10]}")

# Plotinus - check how many tractates there actually are
text2 = fetch("https://classics.mit.edu/Plotinus/enneads.mb.txt")
tractates = re.findall(r'\n(\w+) Tractate ', text2)
print(f"\nPlotinus tractate count: {len(tractates)}")
print("Tractates:", tractates)
# Check sections within first tractate
idx2 = text2.find('First Tractate')
chunk2 = text2[idx2:idx2+200]
print("\nFirst tractate start:")
print(repr(chunk2))
