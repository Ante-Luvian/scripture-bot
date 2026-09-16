"""
build_plotinus_ennead6.py
Run: python build_plotinus_ennead6.py
Requires: pip install requests
"""
import json, re, time, sys
from pathlib import Path

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("Run: pip install requests")
    sys.exit(1)

PLOTINUS_PATH = Path("data/classical/plotinus.json")
BASE = "https://sacred-texts.com/cla/plotenn/enn"

TRACTATE_MAP = {
    "6.1": [(1,508),(2,509),(3,510),(4,511),(6,512),(7,513),(8,514),(9,515),
            (10,516),(11,517),(12,518),(13,519),(14,520),(15,521),(16,522),
            (17,523),(18,524),(19,525),(20,526),(21,527),(22,528),(23,529),
            (24,530),(25,531),(26,532),(27,533),(28,534),(29,535),(30,536)],
    "6.2": [(s, 537+s) for s in range(1, 23)],
    "6.3": [(s, 560+s) for s in range(1, 29)],
    "6.4": [(s, 589+s) for s in range(1, 17)],
    "6.5": [(s, 606+s) for s in range(1, 13)],
    "6.6": [(s, 619+s) for s in range(1, 19)],
    "6.7": [(s, 638+s) for s in range(1, 43)],
    "6.8": [(s, 681+s) for s in range(1, 22)],
    "6.9": [(s, 703+s) for s in range(1, 12)],
}

# Full browser headers including a realistic Accept and Referer
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://sacred-texts.com/cla/plotenn/index.htm",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}

session = requests.Session()
session.headers.update(HEADERS)

# Visit the index page first to get a session cookie, just like a real browser
print("Visiting index page first...")
try:
    r = session.get("https://sacred-texts.com/cla/plotenn/index.htm", timeout=15)
    print(f"  Index: {r.status_code}")
    time.sleep(2)
except Exception as e:
    print(f"  {e}")

def fetch(url, delay=2.5):
    try:
        r = session.get(url, timeout=20)
        time.sleep(delay)
        if r.status_code == 200:
            return r.text
        print(f"  HTTP {r.status_code}: {url.split('/')[-1]}")
        if r.status_code == 429:
            print("  Rate limited — waiting 60s...")
            time.sleep(60)
        return None
    except Exception as ex:
        print(f"  {ex}")
        return None

def clean(t): return re.sub(r'\s+', ' ', t).strip()

def extract_text(html):
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL|re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', html)
    for e, r in [('&nbsp;',' '),('&amp;','&'),('&lt;','<'),('&gt;','>'),('&#39;',"'"),('&quot;','"')]:
        text = text.replace(e, r)
    text = re.sub(r'&#x[0-9a-fA-F]+;', '', text)
    text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'&\w+;', '', text).replace('\r','')
    for marker in ['Sacred Texts Classics Index Previous Next', 'Sacred Texts Classics Index Next']:
        idx = text.find(marker)
        if idx >= 0:
            text = text[idx + len(marker):]
            break
    for marker in ['Previous Next', 'Next: Section', 'Next: THE', 'Sacred Texts Classics', 'Previous: Section']:
        idx = text.rfind(marker)
        if idx > len(text) * 0.6:
            text = text[:idx]
    text = re.sub(r'([,;\.!?]) \d{1,3} ([A-Z])', r'\1 \2', text)
    text = re.sub(r'([a-z]) \d{1,3} ([A-Z])', r'\1 \2', text)
    return clean(text)

print("Fetching Ennead 6...")
new_chapters = {}
total_fetched = 0
total_failed = 0

for chap_key, sections in TRACTATE_MAP.items():
    new_chapters[chap_key] = {}
    for sect_num, page_num in sections:
        url = f"{BASE}{page_num:03d}.htm"
        html = fetch(url, delay=2.5)
        if not html:
            total_failed += 1
            continue
        text = extract_text(html)
        if len(text) < 50:
            print(f"  {chap_key}:{sect_num}: too short")
            total_failed += 1
            continue
        new_chapters[chap_key][str(sect_num)] = text
        print(f"  {chap_key}:{sect_num} ✓ ({len(text)}ch)")
        total_fetched += 1

print(f"\nFetched: {total_fetched}  Failed: {total_failed}")
if total_fetched == 0:
    print("Nothing fetched. Sacred-texts may still be blocking.")
    sys.exit(1)

data = json.loads(PLOTINUS_PATH.read_text(encoding="utf-8"))
enneads = data["books"]["Enneads"]
for chap_key, verses in new_chapters.items():
    if verses:
        enneads[chap_key] = verses
data["books"]["Enneads"] = enneads
PLOTINUS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

kb = PLOTINUS_PATH.stat().st_size // 1024
total_v = sum(len(v) for v in enneads.values())
e6 = sorted(k for k in enneads if k.startswith('6.'))
print(f"\n✓ plotinus.json ({kb}KB, {len(enneads)} tractates, {total_v} sections)")
print(f"  Ennead 6: {e6}")
