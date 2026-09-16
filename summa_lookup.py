"""
summa_lookup.py
---------------
Live scraper for the Summa Theologica via newadvent.org.

Citation format: ST I.2.3 = Prima Pars, Question 2, Article 3
Parts:
  I      → Prima Pars          → URL prefix 1
  I-II   → Prima Secundae      → URL prefix 2
  II-II  → Secunda Secundae    → URL prefix 3
  III    → Tertia Pars         → URL prefix 4
  Supp   → Supplementum        → URL prefix 5

URL pattern: https://www.newadvent.org/summa/{part}{question:03d}.htm
e.g. ST I.2.3  → part=1, q=2   → /summa/1002.htm  (then parse Article 3)
     ST I-II.109.1 → part=2, q=109 → /summa/2109.htm  (then parse Article 1)
"""

from __future__ import annotations
import re
import urllib.request
import html as html_mod
from typing import Optional

# ── Part name → URL digit ────────────────────────────────────────────────────

PART_MAP: dict[str, int] = {
    # Standard abbreviations
    "i":    1, "prima pars": 1, "first part": 1,
    "i-ii": 2, "ia iiae": 2, "prima secundae": 2, "first part of the second part": 2,
    "ii-ii": 3, "iia iiae": 3, "secunda secundae": 3, "second part of the second part": 3,
    "iii":  4, "tertia pars": 4, "third part": 4,
    "supp": 5, "supplement": 5, "supplementum": 5,
    # Numeric shorthands users might type
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
}

PART_DISPLAY: dict[int, str] = {
    1: "I",
    2: "I-II",
    3: "II-II",
    4: "III",
    5: "Supp.",
}

PART_LONG: dict[int, str] = {
    1: "Prima Pars",
    2: "Prima Secundae",
    3: "Secunda Secundae",
    4: "Tertia Pars",
    5: "Supplementum",
}

# Question counts per part (for random/validation)
PART_Q_MAX: dict[int, int] = {
    1: 119,
    2: 114,
    3: 189,
    4: 90,
    5: 99,
}

# ── Reference parser ──────────────────────────────────────────────────────────

def parse_summa_ref(raw: str) -> Optional[tuple[int, int, Optional[int]]]:
    """
    Parse a Summa reference into (part_digit, question, article_or_None).

    Accepted formats:
      I.2.3         ST I.2.3     ia.2.3
      I-II.109.1    I-II.109
      II-II.23      III.16.1
      Supp.1.2
    Returns None if unparseable.
    """
    raw = raw.strip()
    # Strip leading "ST" or "S.T." or "Summa"
    raw = re.sub(r"^(?:s\.?t\.?|summa\s+theologica?e?\s*)", "", raw, flags=re.IGNORECASE).strip()

    # Expect: PART . QUESTION [. ARTICLE]
    m = re.match(
        r"^([A-Za-z][A-Za-z0-9\-]*)\s*[.\s]\s*(\d+)(?:\s*[.\s]\s*(\d+))?$",
        raw, re.IGNORECASE
    )
    if not m:
        return None

    part_raw = m.group(1).lower().strip()
    question = int(m.group(2))
    article  = int(m.group(3)) if m.group(3) else None

    part_digit = PART_MAP.get(part_raw)
    if part_digit is None:
        return None

    return (part_digit, question, article)


# ── URL builder ───────────────────────────────────────────────────────────────

def _summa_url(part: int, question: int) -> str:
    return f"https://www.newadvent.org/summa/{part}{question:03d}.htm"


# ── HTML fetcher + cleaner ────────────────────────────────────────────────────

def _fetch_page(url: str) -> Optional[str]:
    """Fetch raw HTML, return plain text with tags stripped, or None on error."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ScriptureBot/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8")
        return raw
    except Exception:
        return None


def _strip_links(html: str) -> str:
    """Remove <a href=...> tags but keep their text content."""
    return re.sub(r"<a\b[^>]*>(.*?)</a>", r"\1", html, flags=re.DOTALL | re.IGNORECASE)


def _html_to_text(html: str) -> str:
    """Strip all HTML tags and decode entities."""
    html = _strip_links(html)
    html = re.sub(r"<[^>]+>", " ", html)
    html = html_mod.unescape(html)
    html = re.sub(r" {2,}", " ", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


# ── Page parser ───────────────────────────────────────────────────────────────

def _parse_question_page(html: str, question: int) -> Optional[dict]:
    """
    Extract question title and list of article titles from the page.
    Returns { "title": str, "articles": [(n, title), ...] }
    """
    # Question title from <h1>
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    q_title = _html_to_text(h1.group(1)).strip() if h1 else f"Question {question}"

    # Article titles from the ordered list at the top of the page
    # They appear as <li><a href="#articleN">title</a></li>
    articles = []
    for m in re.finditer(
        r'<a\s+href="#article(\d+)"[^>]*>(.*?)</a>',
        html, re.IGNORECASE | re.DOTALL
    ):
        n = int(m.group(1))
        title = _html_to_text(m.group(2)).strip()
        articles.append((n, title))

    return {"title": q_title, "articles": articles}


def _parse_article(html: str, article_num: int) -> Optional[dict]:
    """
    Extract the full text of a specific article from the page HTML.

    Returns:
      {
        "title": str,            # "Article 3. Whether God exists?"
        "objections": [str],     # list of objection texts
        "on_the_contrary": str,
        "i_answer_that": str,
        "replies": [str],
      }
    or None if article not found.
    """
    # Split the page into article sections by h2
    # Pattern: ## Article N.
    article_sections = re.split(
        r"<h2[^>]*>",
        html,
        flags=re.IGNORECASE
    )

    target_section = None
    for sec in article_sections:
        m = re.match(r"\s*Article\s+(\d+)\b", _html_to_text(sec[:80]), re.IGNORECASE)
        if m and int(m.group(1)) == article_num:
            target_section = sec
            break

    if target_section is None:
        return None

    text = _html_to_text(target_section)

    # Extract title (first line up to first bold marker)
    title_m = re.match(r"(Article\s+\d+\.[^\n]+)", text)
    title = title_m.group(1).strip() if title_m else f"Article {article_num}"

    # Extract objections
    objections = []
    for om in re.finditer(r"Objection\s+(\d+)\.\s+(.*?)(?=Objection\s+\d+\.|On the contrary|I answer that|Reply to|$)",
                          text, re.DOTALL | re.IGNORECASE):
        objections.append(f"**Objection {om.group(1)}.** {om.group(2).strip()}")

    # On the contrary
    otc_m = re.search(r"On the contrary,?\s+(.*?)(?=I answer that|Reply to|$)",
                      text, re.DOTALL | re.IGNORECASE)
    on_the_contrary = otc_m.group(1).strip() if otc_m else ""

    # I answer that
    iat_m = re.search(r"I answer that,?\s+(.*?)(?=Reply to Objection\s+1|$)",
                      text, re.DOTALL | re.IGNORECASE)
    i_answer = iat_m.group(1).strip() if iat_m else ""

    # Replies
    replies = []
    for rm in re.finditer(r"Reply to Objection\s+(\d+)\.\s+(.*?)(?=Reply to Objection\s+\d+\.|$)",
                          text, re.DOTALL | re.IGNORECASE):
        replies.append(f"**Reply {rm.group(1)}.** {rm.group(2).strip()}")

    return {
        "title": title,
        "objections": objections,
        "on_the_contrary": on_the_contrary,
        "i_answer_that": i_answer,
        "replies": replies,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def get_summa(part: int, question: int, article: Optional[int]) -> dict:
    """
    Fetch and return a Summa article or question listing.

    If article is None, returns the question overview (title + article list).
    If article is given, returns the full article parsed into sections.
    """
    url = _summa_url(part, question)
    html = _fetch_page(url)

    if html is None:
        return {
            "found": False,
            "error": f"Could not fetch ST {PART_DISPLAY[part]}.{question} from newadvent.org.",
            "url": url,
        }

    # Check for 404-style content
    if "not found" in html.lower()[:500] or len(html) < 500:
        return {
            "found": False,
            "error": f"ST {PART_DISPLAY[part]}.{question} not found. "
                     f"(Max question for {PART_DISPLAY[part]}: {PART_Q_MAX.get(part, '?')})",
            "url": url,
        }

    q_info = _parse_question_page(html, question)

    # Question overview (no article specified)
    if article is None:
        if not q_info:
            return {"found": False, "error": "Could not parse question page.", "url": url}
        return {
            "found": True,
            "type": "question",
            "part": part,
            "part_display": PART_DISPLAY[part],
            "part_long": PART_LONG[part],
            "question": question,
            "title": q_info["title"],
            "articles": q_info["articles"],
            "url": url,
        }

    # Specific article
    art = _parse_article(html, article)
    if art is None:
        n_articles = len(q_info["articles"]) if q_info else "?"
        return {
            "found": False,
            "error": f"ST {PART_DISPLAY[part]}.{question} has no Article {article}. "
                     f"(Articles in this question: {n_articles})",
            "url": url,
        }

    ref = f"ST {PART_DISPLAY[part]}.{question}.{article}"

    return {
        "found": True,
        "type": "article",
        "part": part,
        "part_display": PART_DISPLAY[part],
        "part_long": PART_LONG[part],
        "question": question,
        "question_title": q_info["title"] if q_info else "",
        "article": article,
        "reference": ref,
        "title": art["title"],
        "objections": art["objections"],
        "on_the_contrary": art["on_the_contrary"],
        "i_answer_that": art["i_answer_that"],
        "replies": art["replies"],
        "url": url,
    }


def get_summa_random() -> dict:
    """Return a random Summa article."""
    import random
    part = random.choice([1, 2, 3, 4])  # skip Supplement for random
    q_max = PART_Q_MAX[part]
    question = random.randint(1, q_max)

    # Fetch the page to find how many articles it has, then pick one
    url = _summa_url(part, question)
    html = _fetch_page(url)
    if html is None:
        return {"found": False, "error": "Could not reach newadvent.org for random article."}

    q_info = _parse_question_page(html, question)
    if not q_info or not q_info["articles"]:
        return {"found": False, "error": "Could not parse question for random article."}

    art_num = random.choice([n for n, _ in q_info["articles"]])
    art = _parse_article(html, art_num)
    if art is None:
        return {"found": False, "error": "Could not parse random article."}

    ref = f"ST {PART_DISPLAY[part]}.{question}.{art_num}"
    return {
        "found": True,
        "type": "article",
        "part": part,
        "part_display": PART_DISPLAY[part],
        "part_long": PART_LONG[part],
        "question": question,
        "question_title": q_info["title"],
        "article": art_num,
        "reference": ref,
        "title": art["title"],
        "objections": art["objections"],
        "on_the_contrary": art["on_the_contrary"],
        "i_answer_that": art["i_answer_that"],
        "replies": art["replies"],
        "url": _summa_url(part, question),
    }
