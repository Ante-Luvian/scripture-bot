import urllib.request, re, html as html_mod

url = "https://catholicbible.online/knox/OT/Gen/ch_1"
req = urllib.request.Request(url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
})
with urllib.request.urlopen(req, timeout=20) as r:
    raw = r.read().decode("utf-8", errors="replace")

print(f"Total HTML length: {len(raw)}")

# Show what's around the first verse text
idx = raw.find("beginning of time")
if idx >= 0:
    print(f"\n=== 800 chars around 'beginning of time' (pos {idx}) ===")
    print(repr(raw[max(0,idx-400):idx+400]))
else:
    print("Verse text NOT found in raw HTML")
    # Maybe it's loaded via JS / AJAX?
    # Check for any script tags that might fetch content
    ajax = re.findall(r'(fetch|XMLHttpRequest|\.ajax|api|/text|/chapter)[^<]{0,100}', raw[:5000])
    print("Possible AJAX indicators:", ajax[:5])
    print("\nFirst 3000 chars of HTML:")
    print(repr(raw[:3000]))
