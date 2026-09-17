"""
Build script: converts Samuel Zinner's public-domain English translations of
the Nag Hammadi Library (hosted at luminescence-llc.net, edited by Mark M.
Mattison with support from Other Gospels) into
data/gnostic/nag_hammadi_zinner.json.

Source: https://www.luminescence-llc.net/nag-hammadi -- the index page and
every individual tractate page state explicitly: "The following translation
has been committed to the public domain and may be freely copied and used,
changed or unchanged, for any purpose." Translator Samuel Zinner (PhD,
University of Nebraska-Lincoln, 2002) independently self-labels these same
translations "public domain" across multiple academia.edu papers, so this
isn't resting on one page's say-so. Each page cites its specific Coptic
source edition (mostly Peter Nagel's critical editions) and names both
translator and editor -- verified by reading the actual page text, not
inferred.

Only tractates hosted directly on luminescence-llc.net are included here
(the bulk of the corpus). A handful of tractates on this project's index
page link out to othergospels.com or standalone academia.edu PDFs instead
(Gospel of Thomas, Philip, Truth, Judas, Mary, the Apocryphon of John, the
First Apocalypse of James) -- those need their own separate handling and
are not fetched by this script.

Each page's front matter (the public-domain notice, source-edition
citation, and a "Symbols" legend explaining bracket notation) is stripped;
everything from the first real section heading onward is kept as the
tractate's text. Inline Coptic-manuscript page-number markers like
"[12]" are kept as plain text (their hyperlink to a facsimile scan is
dropped, the page number itself is not).

Downloads its own source -- run from anywhere:
    python deprecated/build_nag_hammadi.py
"""
import html as html_mod
import json
import re
import time
import urllib.request
from pathlib import Path

BASE = "https://www.luminescence-llc.net"
OUT_DIR = Path(__file__).parent.parent / "data" / "gnostic"
OUT_PATH = OUT_DIR / "nag_hammadi_zinner.json"

# (url slug, canonical book name) -- luminescence-llc.net pages only.
PAGES = [
    ("/the-prayer-of-paul", "The Prayer of Paul, the Apostle"),
    ("/the-secret-book-of-james", "The Secret Book of James"),
    ("/resurrection", "Treatise on the Resurrection"),
    ("/tripartate-tractate", "The Tripartite Tractate"),
    ("/the-substance-of-the-archons", "The Substance of the Archons"),
    ("/on-the-origin-of-the-world", "On the Origin of the World"),
    ("/the-exegesis-on-the-soul", "The Exegesis on the Soul"),
    ("/thomas-the-contender", "The Book of Thomas the Contender"),
    ("/the-sacred-book-of-the-great-unseen-spirit", "The Sacred Book of the Great Unseen Spirit"),
    ("/eugnostos-the-blessed", "Eugnostos the Blessed"),
    ("/sophia-of-jesus-christ", "The Sophia of Jesus Christ"),
    ("/dialogue-of-the-savior", "The Dialogue of the Savior"),
    ("/apocalypse-of-paul", "The Apocalypse of Paul"),
    ("/the-second-apocalypse-of-james", "The Second Apocalypse of James"),
    ("/the-apocalypse-of-adam", "The Apocalypse of Adam"),
    ("/acts-of-peter-and-the-twelve", "The Acts of Peter and the Twelve Apostles"),
    ("/thunder-perfect-mind", "The Thunder, Perfect Mind"),
    ("/the-authentic-logos", "The Authentic Logos"),
    ("/the-idea-of-our-great-power", "The Idea of Our Great Power"),
    ("/the-discourse-on-the-eighth-and-ninth", "The Discourse on the Eighth and Ninth"),
    ("/prayer-of-thanksgiving", "The Prayer of Thanksgiving"),
    ("/excerpt-from-the-perfect-discourse", "Excerpt from the Perfect Discourse"),
    ("/the-paraphrase-of-shem", "The Paraphrase of Shem"),
    ("/the-second-discourse-of-the-great-seth", "The Second Discourse of the Great Seth"),
    ("/apocalypse-of-peter", "The Apocalypse of Peter"),
    ("/the-teachings-of-silvanus", "The Teachings of Silvanus"),
    ("/the-three-steles-of-seth", "The Three Steles of Seth"),
    ("/zostrianos", "Zostrianos"),
    ("/the-letter-of-peter-to-philip", "The Letter of Peter to Philip"),
    ("/melchizedek", "Melchizedek"),
    ("/thought-of-norea", "The Thought of Norea"),
    ("/the-testimony-of-truth", "The Testimony of Truth"),
    ("/marsanes", "Marsanes"),
    ("/the-interpretation-of-knowledge", "The Interpretation of Knowledge"),
    ("/a-valentinian-exposition", "A Valentinian Exposition and Liturgical Readings"),
    ("/the-stranger", "Allogenes (The Stranger)"),
    ("/hypsiphrone", "Hypsiphrone"),
    ("/the-sentences-of-sextus", "The Sentences of Sextus"),
    ("/three-forms-of-primal-thought", "Trimorphic Protennoia (Three Forms of Primal Thought)"),
    ("/corpus-hermeticum-xiii", "Corpus Hermeticum XIII, On Rebirth"),
    ("/the-act-of-peter", "The Act of Peter"),
]


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def _clean(fragment):
    # Drop footnote call-out links entirely (both the tag and its visible
    # text) -- they point at a "#_ftnN"-style in-page anchor. Formatting of
    # the visible text is inconsistent across tractate pages (some wrap it
    # in brackets, some in <em>, some bare), so match on the href, not the
    # content.
    fragment = re.sub(r'<a [^>]*href="#[^"]*ftn[^"]*"[^>]*>.*?</a>', '', fragment, flags=re.IGNORECASE | re.DOTALL)
    # Drop <a>...</a> wrapping around inline page-number markers, keep the number.
    fragment = re.sub(r'<a [^>]*>(\[?\d+\]?)</a>', r'\1', fragment)
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = html_mod.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return text.strip()


def _extract_body(raw):
    idx = raw.find('data-sqsp-text-block-content')
    if idx == -1:
        return None
    # The whole front matter + content lives in one big text block; grab a
    # generous window and let the paragraph-splitter below sort it out.
    end = raw.find("</main>", idx)
    if end == -1:
        end = idx + 40000
    return raw[idx:end]


# Inline manuscript page markers ("[ 12 ]") always have internal spaces;
# footnote call-outs ("[12]") never do -- that's the reliable, consistent
# distinction used to tell them apart in Zinner's rendering.
_PAGE_RE = re.compile(r"\[\s+([A-Za-z0-9]+)\s+\]")
_FOOT_RE = re.compile(r"\[(\d+)\]")


def _split_into_verses(page_text):
    """
    Splits one manuscript page's text into verses along its own paragraph
    breaks (blank lines) -- a real structural unit already present in the
    source (each is its own <p> block), not an invented division. A bare
    section title on its own line (e.g. "First 'I Am' Speech") is folded
    into the following paragraph rather than standing alone as its own
    near-empty verse.
    """
    def _is_bare_heading(p):
        return len(p) < 60 and "\n" not in p and not p.endswith((".", "!", "?", "”", '"'))

    paras = [p.strip() for p in page_text.split("\n\n") if p.strip()]
    verses = []
    for p in paras:
        if verses and _is_bare_heading(p):
            verses[-1] = verses[-1] + "\n\n" + p
        else:
            verses.append(p)
    # A leading heading has no prior verse to merge into -- attach it to
    # the verse that follows instead of leaving it to stand alone.
    if len(verses) > 1 and _is_bare_heading(verses[0]):
        verses[1] = verses[0] + "\n\n" + verses[1]
        verses.pop(0)
    return {str(i + 1): v for i, v in enumerate(verses)} or {"1": page_text.strip()}


def _split_into_chapters(text):
    """
    Splits one tractate's full text into per-manuscript-page chapters using
    the inline "[ N ]" page markers, and strips footnote call-outs. Chapters
    are keyed by sequential position (1, 2, 3, ...), not the literal page
    label -- some tractates use letters (A, B) for short fragments, and at
    least one (The Sacred Book of the Great Unseen Spirit) has the raw page
    numbers jump out of order, so sequential position is the only reliably
    parseable/lookup-able key. The real manuscript page label stays inline
    in the chapter's own text, so nothing scholarly is lost -- it's just not
    the thing you type into `!verse`. Each page is further split into
    verses along its own paragraph breaks (see _split_into_verses).
    """
    matches = list(_PAGE_RE.finditer(text))
    if not matches:
        return {"1": _split_into_verses(_FOOT_RE.sub("", text).strip())}

    chunks = {}
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunks[str(i + 1)] = _FOOT_RE.sub("", text[start:end]).strip()

    preamble = _FOOT_RE.sub("", text[:matches[0].start()]).strip()
    if preamble:
        chunks["1"] = preamble + "\n\n" + chunks["1"]

    chunks = {k: _split_into_verses(v) for k, v in chunks.items()}
    return chunks


def main():
    entries = {}
    for slug, name in PAGES:
        raw = _fetch(BASE + slug)
        body = _extract_body(raw)
        if not body:
            print(f"SKIP (no content block): {name}")
            continue

        paras = re.findall(r"<p[^>]*>(.*?)</p>", body, re.DOTALL)
        cleaned = [_clean(p) for p in paras]
        cleaned = [c for c in cleaned if c]

        # Skip the front-matter block: everything through the "Symbols"
        # legend paragraph (if present), or through the last paragraph that
        # mentions the public-domain notice / citation (if "Symbols" isn't
        # used on this particular page).
        start_i = 0
        for i, c in enumerate(cleaned):
            if c.strip() == "Symbols":
                # skip the legend paragraph right after it too
                start_i = i + 2
                break
        else:
            for i, c in enumerate(cleaned):
                if "public domain" in c.lower():
                    start_i = i + 1
        body_paras = cleaned[start_i:]
        if not body_paras:
            print(f"SKIP (empty after front-matter strip): {name}")
            continue

        text = "\n\n".join(body_paras)
        chapters = _split_into_chapters(text)
        entries[name] = chapters
        print(f"{name}: {len(chapters)} chapters, {len(text)} chars")
        time.sleep(1)

    payload = {
        "source": (
            "The Nag Hammadi Library, trans. Samuel Zinner (PhD), ed. Mark M. "
            "Mattison (public domain, luminescence-llc.net/nag-hammadi)"
        ),
        "books": entries,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT_PATH} -- {len(entries)} tractates")


if __name__ == "__main__":
    main()
