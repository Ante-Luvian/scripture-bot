"""
Family tree pictures for !tree, drawn with Pillow from the people data behind
!who (data/people_places/, Theographic Bible Metadata).

  family_chart(slug, people)   a person among their family: grandparents,
                               parents, brothers and sisters, husband or wife,
                               and children, with their line of descent above
  lineage_chart(slugs, people) a line of descent, one generation to a box,
                               in columns (Abraham to David, Adam to Jesus)
"""
import functools
import io
import re

from PIL import Image, ImageDraw, ImageFont

S = 2                                      # drawn at twice the size, then shrunk: smooth lines
FONTS = "C:/Windows/Fonts/"
PAPER = (246, 240, 226)
BOX = (255, 252, 244)
EDGE = (170, 150, 120)
INK = (60, 50, 40)
MUTED = (125, 112, 95)
LINE = (150, 130, 100)
RED = (178, 34, 34)
HIGHLIGHT = (252, 236, 205)
BOX_H, GAP, ROW_GAP, MARGIN = 46, 14, 40, 28
MAX_ROW = 8                                # boxes in a row before "and N more"
MAX_CHILDREN = 15                          # two full rows with "and N more"
UP_GENERATIONS, UP_GAP = 6, 18             # fathers drawn above the grandfather


@functools.lru_cache(maxsize=16)
def _font(name: str, size: int):
    try:
        return ImageFont.truetype(FONTS + name, size * S)
    except OSError:
        return ImageFont.load_default()


def short_name(person: dict) -> str:
    """'Judah (patriarch)' -> 'Judah'"""
    return re.sub(r"\s*\(.*\)$", "", person["name"]).strip()


class _Box:
    def __init__(self, text: str, note: str = "", main: bool = False, faint: bool = False):
        self.text, self.note, self.main, self.faint = text, note, main, faint
        name_w = _font("georgiab.ttf" if main else "georgia.ttf", 16).getlength(text) / S
        note_w = _font("georgiai.ttf", 12).getlength(note) / S
        self.w = max(96, int(max(name_w, note_w)) + 22)
        self.x = self.y = 0                # centre x, top y

    @property
    def top(self):
        return (self.x, self.y)

    @property
    def bottom(self):
        return (self.x, self.y + BOX_H)

    def draw(self, d, dx: int, dy: int) -> None:
        x0, y0 = (self.x - self.w / 2 + dx) * S, (self.y + dy) * S
        d.rounded_rectangle([x0, y0, x0 + self.w * S, y0 + BOX_H * S], radius=7 * S,
                            fill=HIGHLIGHT if self.main else BOX if not self.faint else PAPER,
                            outline=RED if self.main else EDGE, width=(3 if self.main else 2) * S)
        font = _font("georgiab.ttf" if self.main else "georgia.ttf", 16)
        cx = (self.x + dx) * S
        ink = RED if self.main else MUTED if self.faint else INK
        if self.note:
            d.text((cx, y0 + 15 * S), self.text, font=font, fill=ink, anchor="mm")
            d.text((cx, y0 + 34 * S), self.note, font=_font("georgiai.ttf", 12), fill=MUTED, anchor="mm")
        else:
            d.text((cx, y0 + BOX_H / 2 * S), self.text, font=font, fill=ink, anchor="mm")


def _row(boxes: list, centre: float, y: int) -> None:
    """Lay boxes side by side, centred on `centre`."""
    width = sum(b.w for b in boxes) + GAP * (len(boxes) - 1)
    x = centre - width / 2
    for b in boxes:
        b.x, b.y = x + b.w / 2, y
        x += b.w + GAP


def _capped(slugs: list, people: dict, note: str, limit: int) -> list:
    boxes = [_Box(short_name(people[s]), note) for s in slugs[:limit]]
    if len(slugs) > limit:
        boxes.append(_Box(f"and {len(slugs) - limit} more", faint=True))
    return boxes


def _best_known(slugs: list, people: dict) -> list:
    """Those named in the most verses first, so a long list cut short keeps Solomon and Absalom."""
    return sorted((s for s in slugs if s in people), key=lambda s: -len(people[s]["verses"]))


def _kids_note(person: dict) -> str:
    return "daughter" if person.get("gender") == "Female" else "son"


def _render(boxes: list, links: list, title: str, subtitle: str, credit: str) -> io.BytesIO:
    """Draw boxes and links ([(x1, y1, x2, y2), ...] in layout units) under a title."""
    left = min(b.x - b.w / 2 for b in boxes)
    right = max(b.x + b.w / 2 for b in boxes)
    top = min(b.y for b in boxes)
    bottom = max(b.y + BOX_H for b in boxes) - top
    title_font, sub_font = _font("georgiab.ttf", 22), _font("georgiai.ttf", 14)
    sub_lines = _wrap(subtitle, sub_font, 900) if subtitle else []
    head = 40 + 20 * len(sub_lines) + 24
    width = int(max(right - left + 2 * MARGIN, title_font.getlength(title) / S + 2 * MARGIN,
                    max((sub_font.getlength(t) / S for t in sub_lines), default=0) + 2 * MARGIN, 420))
    height = int(head + bottom + MARGIN + 22)
    dx = (width - (right - left)) / 2 - left
    dy = head - top
    img = Image.new("RGB", (width * S, height * S), PAPER)
    d = ImageDraw.Draw(img)
    d.text((width / 2 * S, 24 * S), title, font=title_font, fill=INK, anchor="mm")
    for i, t in enumerate(sub_lines):
        d.text((width / 2 * S, (48 + 20 * i) * S), t, font=sub_font, fill=MUTED, anchor="mm")
    for x1, y1, x2, y2 in links:
        d.line([((x1 + dx) * S, (y1 + dy) * S), ((x2 + dx) * S, (y2 + dy) * S)], fill=LINE, width=2 * S)
    for b in boxes:
        b.draw(d, dx, dy)
    cf = _font("georgia.ttf", 11)
    d.text(((width - 8) * S, (height - 8) * S), credit, font=cf, fill=MUTED, anchor="rs")
    img = img.resize((width, height), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf


def _wrap(text: str, font, width: int) -> list:
    lines, line = [], ""
    for word in text.split(" "):
        trial = f"{line} {word}".strip()
        if line and font.getlength(trial) / S > width:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + ([line] if line else [])


def _fork(parent: tuple, children: list, links: list) -> None:
    """Lines from a parent's bottom (or a couple's midpoint) to each child's top."""
    if not children:
        return
    px, py = parent
    mid = children[0].y - ROW_GAP / 2
    links.append((px, py, px, mid))
    xs = [c.x for c in children]
    links.append((min(xs + [px]), mid, max(xs + [px]), mid))
    for c in children:
        links.append((c.x, mid, c.x, c.y))


def paternal_line(slug: str, people: dict, limit: int = 12) -> list:
    """The person's father, his father, and so on: nearest first."""
    out, seen = [], {slug}
    while len(out) < limit:
        # Luke 3:38 ends "Adam, which was the son of God": the line of fathers stops at Adam
        fathers = [f for f in people[slug]["father"] if f in people and f not in seen
                   and people[f]["name"] != "God"]
        if not fathers:
            break
        slug = fathers[0]
        seen.add(slug)
        out.append(slug)
    return out


def _forefathers(grandfather: str, gf_box: "_Box", people: dict, links: list) -> list:
    """A column of fathers above the grandfather (great-grandfather and up), then a
    box for how much further the line goes: '… 58 more generations, back to Adam'."""
    line = paternal_line(grandfather, people, limit=1000)
    boxes, below = [], gf_box
    for i, slug in enumerate(line[:UP_GENERATIONS]):
        note = "great-grandfather" if i == 0 else f"{i + 1}× great-grandfather"
        b = _Box(short_name(people[slug]), note)
        b.x, b.y = gf_box.x, below.y - BOX_H - UP_GAP
        links.append((b.x, b.y + BOX_H, b.x, below.y))
        boxes.append(b)
        below = b
    rest = len(line) - UP_GENERATIONS
    if rest > 0:
        b = _Box(f"… {rest} more generation{'s' if rest != 1 else ''}",
                 f"back to {short_name(people[line[-1]])}", faint=True)
        b.x, b.y = gf_box.x, below.y - BOX_H - UP_GAP
        links.append((b.x, b.y + BOX_H, b.x, below.y))
        boxes.append(b)
    return boxes


def family_chart(slug: str, people: dict) -> io.BytesIO:
    me = people[slug]
    boxes, links = [], []
    y_gp, y_par, y_me = 0, BOX_H + ROW_GAP, 2 * (BOX_H + ROW_GAP)
    y_kids = y_me + BOX_H + ROW_GAP

    # me, my brothers and sisters, then my husband or wives
    sibs = _best_known([s for s in me["siblings"] if s != slug], people)
    sib_boxes = _capped(sibs, people, "", MAX_ROW - 1)
    for b, s in zip(sib_boxes, sibs):
        if not b.faint:
            b.note = "sister" if people[s].get("gender") == "Female" else "brother"
    me_box = _Box(short_name(me), main=True)
    spouses = _best_known(me["partners"], people)
    spouse_word = "husband" if me.get("gender") == "Female" else "wife"
    sp_boxes = _capped(spouses, people, spouse_word, 4)
    _row(sib_boxes + [me_box], 0, y_me)
    x = me_box.x + me_box.w / 2 + GAP * 2.5
    for b in sp_boxes:
        b.x, b.y = x + b.w / 2, y_me
        x += b.w + GAP
    if sp_boxes:
        # a double line joins a married couple
        y = y_me + BOX_H / 2
        links += [(me_box.x + me_box.w / 2, y - 3, sp_boxes[0].x - sp_boxes[0].w / 2, y - 3),
                  (me_box.x + me_box.w / 2, y + 3, sp_boxes[0].x - sp_boxes[0].w / 2, y + 3)]
    boxes += sib_boxes + [me_box] + sp_boxes

    # parents above, over the brothers and sisters; grandparents above them
    row_mid = (min(b.x - b.w / 2 for b in sib_boxes + [me_box]) + me_box.x + me_box.w / 2) / 2
    parents = [(s, "father") for s in me["father"][:1] if s in people] + \
              [(s, "mother") for s in me["mother"][:1] if s in people]
    par_boxes = []
    if parents:
        width_gp = 0
        for s, _ in parents:
            gps = [g for g in people[s]["father"][:1] + people[s]["mother"][:1] if g in people]
            width_gp = max(width_gp, sum(_Box(short_name(people[g])).w for g in gps) + GAP)
        par_boxes = [_Box(short_name(people[s]), note) for s, note in parents]
        if len(par_boxes) == 2:
            spread = max(width_gp, par_boxes[0].w / 2 + par_boxes[1].w / 2 + GAP * 3) / 2 + GAP
            par_boxes[0].x, par_boxes[1].x = row_mid - spread, row_mid + spread
            for b in par_boxes:
                b.y = y_par
            y = y_par + BOX_H / 2
            links += [(par_boxes[0].x + par_boxes[0].w / 2, y - 3, par_boxes[1].x - par_boxes[1].w / 2, y - 3),
                      (par_boxes[0].x + par_boxes[0].w / 2, y + 3, par_boxes[1].x - par_boxes[1].w / 2, y + 3)]
            _fork((row_mid, y + 3), sib_boxes[:len(sibs)] + [me_box], links)
        else:
            _row(par_boxes, row_mid, y_par)
            _fork(par_boxes[0].bottom, sib_boxes[:len(sibs)] + [me_box], links)
        boxes += par_boxes
        for pb, (s, _) in zip(par_boxes, parents):
            gps = [(g, "father") for g in people[s]["father"][:1] if g in people] + \
                  [(g, "mother") for g in people[s]["mother"][:1] if g in people]
            if not gps:
                continue
            gp_boxes = [_Box(short_name(people[g]), "grandfather" if n == "father" else "grandmother")
                        for g, n in gps]
            _row(gp_boxes, pb.x, y_gp)
            boxes += gp_boxes
            _fork((sum(b.x for b in gp_boxes) / len(gp_boxes), y_gp + BOX_H), [pb], links)
            if pb is par_boxes[0] and gps[0][1] == "father":
                boxes += _forefathers(gps[0][0], gp_boxes[0], people, links)

    # children below, in up to two rows
    kids = _best_known(me["children"], people)
    if kids:
        kid_boxes = [_Box(short_name(people[k]), _kids_note(people[k])) for k in kids[:MAX_CHILDREN]]
        if len(kids) > MAX_CHILDREN:
            kid_boxes.append(_Box(f"and {len(kids) - MAX_CHILDREN} more", faint=True))
        start = (me_box.x + sp_boxes[0].x) / 2 if sp_boxes else me_box.x
        rows = [kid_boxes[i:i + MAX_ROW] for i in range(0, len(kid_boxes), MAX_ROW)]
        source = (start, y_me + BOX_H / 2 + 3) if sp_boxes else me_box.bottom
        if len(rows) == 1:
            _row(rows[0], start, y_kids)
            _fork(source, rows[0], links)
        else:
            # several rows: a trunk down the left side, a bar along the top of each row
            for i, row in enumerate(rows):
                _row(row, start, y_kids + i * (BOX_H + ROW_GAP))
            trunk = min(b.x - b.w / 2 for b in kid_boxes) - 12
            bars = [y_kids + i * (BOX_H + ROW_GAP) - ROW_GAP / 2 for i in range(len(rows))]
            links += [(source[0], source[1], source[0], bars[0]), (trunk, bars[0], trunk, bars[-1])]
            for row, bar in zip(rows, bars):
                links.append((trunk, bar, max(max(b.x for b in row), source[0]), bar))
                links += [(b.x, bar, b.x, b.y) for b in row if b.text and not b.faint]
        boxes += kid_boxes

    return _render(boxes, links, f"The family of {short_name(me)}", "", "Theographic Bible Metadata")


def lineage_chart(slugs: list, people: dict) -> io.BytesIO:
    """One box per generation, top to bottom, wrapping into columns."""
    n = len(slugs)
    per_col = n if n <= 12 else -(-n // -(-n // 16))      # at most 16 a column, columns evened out
    boxes = []
    for i, s in enumerate(slugs):
        b = _Box(short_name(people[s]), f"generation {i + 1}" if 0 < i < n - 1 else "",
                 main=i in (0, n - 1))
        boxes.append(b)
    col_w = max(b.w for b in boxes) + 48
    step = BOX_H + 22
    links = []
    for i, b in enumerate(boxes):
        col, pos = divmod(i, per_col)
        b.x, b.y = col * col_w, pos * step
    for a, b in zip(boxes, boxes[1:]):
        if b.x == a.x:
            links.append((a.x, a.y + BOX_H, b.x, b.y))
        else:                               # into the next column: down, across, up, across, down
            gap_x = a.x + col_w / 2
            low, high = a.y + BOX_H + 11, b.y - 11
            links += [(a.x, a.y + BOX_H, a.x, low), (a.x, low, gap_x, low), (gap_x, low, gap_x, high),
                      (gap_x, high, b.x, high), (b.x, high, b.x, b.y)]
    first, last = short_name(people[slugs[0]]), short_name(people[slugs[-1]])
    return _render(boxes, links, f"From {first} to {last}", f"{n} generations, parent to child",
                   "Theographic Bible Metadata")
