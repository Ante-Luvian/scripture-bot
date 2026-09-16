"""
fix_julian.py — fix the two missing Julian works
Run: python fix_julian.py
"""
import json, re, time, urllib.request, urllib.error
from pathlib import Path

OUT = Path("data/classical")

def fetch(url, delay=1.0, timeout=30):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; ScriptureBot/1.0)"
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            time.sleep(delay)
            return raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 60*(attempt+1); print(f"\n    429—{wait}s..."); time.sleep(wait)
            elif e.code == 404: return None
            else: print(f"\n    HTTP {e.code}: {url}"); return None
        except Exception as ex:
            if attempt < 3: time.sleep(8)
            else: print(f"\n    {ex}"); return None
    return None

def clean(t):
    return re.sub(r"\s+", " ", t).strip()

def strip_html(html):
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL|re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL|re.IGNORECASE)
    html = re.sub(r'<[^>]+>', ' ', html)
    html = html.replace('&nbsp;',' ').replace('&amp;','&').replace('&lt;','<').replace('&gt;','>')
    html = html.replace('&#39;',"'").replace('&quot;','"')
    html = re.sub(r'&#x[0-9a-fA-F]+;', '', html)
    html = re.sub(r'&#\d+;', '', html)
    html = re.sub(r'&\w+;', '', html)
    return html.replace('\r','')

def parse_numbered(text, min_len=30):
    results = {}; current = None; buf = []
    def flush():
        if current is not None and buf:
            t = clean(" ".join(buf))
            if len(t) >= min_len:
                results[str(current)] = {"1": t}
    sec_re = re.compile(r'^\s*(\d+)\.\s+(.*)')
    for line in text.split('\n'):
        m = sec_re.match(line)
        if m:
            flush(); buf = []; current = int(m.group(1))
            rest = m.group(2).strip()
            if rest: buf.append(rest)
        else:
            s = line.strip()
            if s and current is not None and len(s) > 4 and not s.startswith('@'):
                buf.append(s)
    flush()
    return results

def as_single_section(text, min_len=200):
    """Store whole text as section 1 if no numbered sections found."""
    lines = [l.strip() for l in text.split('\n')
             if l.strip() and len(l.strip()) > 40
             and not l.strip().startswith('@')
             and not l.strip().startswith('{')]
    t = clean(" ".join(lines))
    if len(t) > min_len:
        return {"1": {"1": t}}
    return {}


# ── Against the Galilaeans — Tertullian (Wright/Loeb, text surviving via Cyril)
print("\n── Against the Galilaeans ────────────────────────────────────────────")
print("  Fetching from Tertullian...", end=" ", flush=True)
html = fetch("https://www.tertullian.org/fathers/julian_apostate_galileans_1_text.htm", delay=1.5)
gal_sects = {}
if html:
    text = strip_html(html)
    # This text is numbered by Stephanus page numbers inline like "43." "106." etc.
    gal_sects = parse_numbered(text, min_len=50)
    if not gal_sects:
        gal_sects = as_single_section(text)
    print(f"✓ {len(gal_sects)}")
else:
    print("not found")

# ── The Caesars — Tertullian
print("  The Caesars from Tertullian...", end=" ", flush=True)
html = fetch("https://www.tertullian.org/fathers/julian_apostate_symposium_caesars_1_text.htm", delay=1.5)
caes_sects = {}
if html:
    text = strip_html(html)
    caes_sects = parse_numbered(text, min_len=50)
    if not caes_sects:
        caes_sects = as_single_section(text)
    print(f"✓ {len(caes_sects)}")
else:
    print("not found — trying alternate URL")
    html = fetch("https://www.tertullian.org/fathers/julian_apostate_caesars_1_trans.htm", delay=1.5)
    if html:
        text = strip_html(html)
        caes_sects = parse_numbered(text, min_len=50)
        if not caes_sects:
            caes_sects = as_single_section(text)
        print(f"✓ {len(caes_sects)}")
    else:
        print("not found — storing from sacred-texts")
        # Last resort: sacred-texts has it as toj02.htm
        html = fetch("https://sacred-texts.com/cla/toj/toj02.htm", delay=1.5)
        if html:
            text = strip_html(html)
            # Filter out JSON-LD garbage
            lines = [l for l in text.split('\n') if l.strip() and len(l.strip()) > 40
                     and not l.strip().startswith('{') and not l.strip().startswith('@')
                     and '"@' not in l and 'BreadcrumbList' not in l]
            t = clean(" ".join(l.strip() for l in lines))
            if len(t) > 500:
                # Try to find actual start of text
                idx = max(t.find('Kronos'), t.find('HERMES'), t.find('Romulus'), 0)
                if idx > 100:
                    t = t[idx:]
                caes_sects = {"1": {"1": t}}
                print(f"✓ 1 (full text)")

# ── Update julian.json
path = OUT / "julian.json"
data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"books":{}}

if gal_sects:
    data["books"]["Against the Galilaeans"] = gal_sects
if caes_sects:
    data["books"]["The Caesars"] = caes_sects

path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
kb = path.stat().st_size // 1024
total = sum(len(v) for v in data["books"].values())
print(f"\n    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")
