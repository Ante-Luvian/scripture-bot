"""
Map cards for !place: a biblical place marked on a map of its region, with
nearby places named for orientation and a small locator map of the whole
Bible world in the corner. Drawn with Pillow from data/people_places/
basemap.json (Natural Earth coastlines, lakes, rivers).
"""
import functools
import io
import json
import math

from PIL import Image, ImageDraw, ImageFont

from core import ROOT

BASEMAP_PATH = ROOT / "data" / "people_places" / "basemap.json"
FONTS = "C:/Windows/Fonts/"
W, H, SCALE = 1000, 700, 2                     # drawn at twice the size, then shrunk: smooth lines

SEA = (196, 214, 222)
LAND = (240, 232, 212)
COAST = (150, 140, 118)
RIVER = (120, 160, 190)
INK = (60, 50, 40)
MUTED = (125, 112, 95)
WATER_INK = (60, 100, 135)
RED = (178, 34, 34)
LOCATOR = (10.0, 22.0, 52.0, 43.0)              # the inset: Rome to Persia, Egypt to the Black Sea
WATER_KINDS = {"Water", "River", "Spring", "Sea", "Lake"}
AREA_KINDS = {"Region", "Country"}


@functools.lru_cache(maxsize=1)
def basemap() -> dict:
    return json.loads(BASEMAP_PATH.read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=16)
def _font(name: str, size: int):
    try:
        return ImageFont.truetype(FONTS + name, size * SCALE)
    except OSError:
        return ImageFont.load_default()


def span_for(place: dict, places: list) -> float:
    """Half the map's height in degrees of latitude: close in where places
    crowd together (Judea), wider where they're sparse (Rome, Persia)."""
    spots = {(round(p["lat"] / 0.15), round(p["lon"] / 0.15)) for p in places   # several names for one
             if p is not place and p["lat"] is not None}                         # spot count once (Babylon)
    dists = sorted(d for d in (math.hypot(a * 0.15 - place["lat"], (b * 0.15 - place["lon"]) * math.cos(math.radians(place["lat"])))
                               for a, b in spots) if d > 0.1)
    d = dists[min(10, len(dists) - 1)] if dists else 2.0
    return max(0.9, min(8.0, d * 1.6))


class _Projection:
    def __init__(self, lat0: float, lon0: float, half_lat: float, w: int, h: int, x0: int = 0, y0: int = 0):
        self.k = h / (2 * half_lat)
        self.c = math.cos(math.radians(lat0))
        self.lat0, self.lon0, self.w, self.h, self.x0, self.y0 = lat0, lon0, w, h, x0, y0

    def __call__(self, lon: float, lat: float) -> tuple:
        return (self.x0 + self.w / 2 + (lon - self.lon0) * self.c * self.k,
                self.y0 + self.h / 2 - (lat - self.lat0) * self.k)

    def bounds(self) -> tuple:
        half_lon = self.w / 2 / (self.c * self.k)
        half_lat = self.h / 2 / self.k
        return self.lon0 - half_lon, self.lat0 - half_lat, self.lon0 + half_lon, self.lat0 + half_lat


def _draw_geography(draw, proj, line_scale: float = 1.0) -> None:
    lon_a, lat_a, lon_b, lat_b = proj.bounds()

    def visible(shape):
        xs = [p[0] for p in shape]
        ys = [p[1] for p in shape]
        return max(xs) >= lon_a and min(xs) <= lon_b and max(ys) >= lat_a and min(ys) <= lat_b

    bm = basemap()
    for poly in bm["land"]:
        if len(poly) > 2 and visible(poly):
            draw.polygon([proj(x, y) for x, y in poly], fill=LAND, outline=COAST, width=max(1, int(2 * line_scale)))
    for poly in bm["lakes"]:
        if len(poly) > 2 and visible(poly):
            draw.polygon([proj(x, y) for x, y in poly], fill=SEA, outline=COAST, width=max(1, int(2 * line_scale)))
    for line in bm["rivers"]:
        if len(line) > 1 and visible(line):
            draw.line([proj(x, y) for x, y in line], fill=RIVER, width=max(1, int(3 * line_scale)), joint="curve")


def _overlaps(box, boxes) -> bool:
    return any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in boxes)


def render_map(place: dict, places: list) -> io.BytesIO:
    """A PNG map of `place` ({"name", "lat", "lon", "approx", "kind"}) among `places`
    (the same, plus "weight": how often each is named)."""
    w, h = W * SCALE, H * SCALE
    img = Image.new("RGB", (w, h), SEA)
    draw = ImageDraw.Draw(img)
    half = span_for(place, places)
    proj = _Projection(place["lat"], place["lon"], half, w, h)
    _draw_geography(draw, proj)

    # the place itself, labelled first so nothing covers it
    x, y = proj(place["lon"], place["lat"])
    r = 11 * SCALE
    label_font = _font("georgiab.ttf", 26)
    boxes = []
    name = place["name"].split(" (")[0]
    tw = draw.textlength(name, font=label_font)
    th = 30 * SCALE
    lx = min(max(x - tw / 2, 12 * SCALE), w - tw - 12 * SCALE)
    ly = y - r - th - 8 * SCALE if y - r - th - 8 * SCALE > 10 * SCALE else y + r + 8 * SCALE
    boxes.append((w - 270 * SCALE, 0, w, 170 * SCALE))           # the locator map
    boxes.append((0, h - 60 * SCALE, 300 * SCALE, h))               # the scale bar
    boxes.append((w - 360 * SCALE, h - 30 * SCALE, w, h))           # the credit
    boxes.append((x - r * 2, y - r * 2, x + r * 2, y + r * 2))
    boxes.append((lx - 8 * SCALE, ly - 4 * SCALE, lx + tw + 8 * SCALE, ly + th + 4 * SCALE))

    # other places for orientation: the most-mentioned first, wherever a label fits
    lon_a, lat_a, lon_b, lat_b = proj.bounds()
    small, area_font, water_font = _font("georgia.ttf", 17), _font("georgia.ttf", 18), _font("georgiai.ttf", 18)
    others = sorted((p for p in places if p is not place and p["lat"] is not None
                     and lon_a < p["lon"] < lon_b and lat_a < p["lat"] < lat_b
                     and p["name"] != place["name"] and not p.get("approx")),
                    key=lambda p: -p.get("weight", 0))
    labelled = 0
    for p in others:
        if labelled >= 16:
            break
        px, py = proj(p["lon"], p["lat"])
        kind = p.get("kind", "")
        text = p["name"].split(" (")[0]
        font = water_font if kind in WATER_KINDS else area_font if kind in AREA_KINDS else small
        if kind in AREA_KINDS:
            text = " ".join(text.upper())
        tw2 = draw.textlength(text, font=font)
        box = (px - tw2 / 2 - 4 * SCALE, py - 26 * SCALE, px + tw2 / 2 + 4 * SCALE, py + 6 * SCALE)
        if box[0] < 0 or box[2] > w or box[1] < 0 or _overlaps(box, boxes):
            continue
        boxes.append(box)
        if kind in WATER_KINDS:
            draw.text((px - tw2 / 2, py - 22 * SCALE), text, font=font, fill=WATER_INK)
        elif kind in AREA_KINDS:
            draw.text((px - tw2 / 2, py - 22 * SCALE), text, font=font, fill=MUTED)
        else:
            d = 4 * SCALE
            draw.ellipse((px - d, py - d, px + d, py + d), fill=MUTED)
            draw.text((px - tw2 / 2, py - 26 * SCALE), text, font=font, fill=INK)
        labelled += 1

    # the marker: a red dot, or a dashed ring where the site is uncertain
    if place.get("approx"):
        ring = 34 * SCALE
        for a in range(0, 360, 20):
            draw.arc((x - ring, y - ring, x + ring, y + ring), a, a + 11, fill=RED, width=4 * SCALE)
    draw.ellipse((x - r, y - r, x + r, y + r), fill=RED, outline=(255, 255, 255), width=3 * SCALE)
    draw.rounded_rectangle((lx - 8 * SCALE, ly - 4 * SCALE, lx + tw + 8 * SCALE, ly + th + 4 * SCALE),
                           radius=6 * SCALE, fill=(255, 250, 240), outline=RED, width=2 * SCALE)
    draw.text((lx, ly), name, font=label_font, fill=RED)

    _draw_scale(draw, proj, w, h)
    _draw_locator(img, proj, place)
    note = "Approximate location" if place.get("approx") else ""
    credit = "Map: Natural Earth · places: OpenBible.info / Theographic"
    cf = _font("georgia.ttf", 13)
    text = f"{note} · {credit}" if note else credit
    cw = draw.textlength(text, font=cf)
    draw.rectangle((w - cw - 16 * SCALE, h - 24 * SCALE, w, h), fill=(255, 255, 255))
    draw.text((w - cw - 8 * SCALE, h - 21 * SCALE), text, font=cf, fill=MUTED)

    img = img.resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


def _arrow(draw, a: tuple, b: tuple, colour, size: float) -> None:
    """A small arrowhead halfway along a->b, pointing towards b."""
    (x1, y1), (x2, y2) = a, b
    length = math.hypot(x2 - x1, y2 - y1)
    if length < size * 4:
        return
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    mx, my = (x1 + x2) / 2 + ux * size / 2, (y1 + y2) / 2 + uy * size / 2
    draw.polygon([(mx, my), (mx - ux * size - uy * size * 0.6, my - uy * size + ux * size * 0.6),
                  (mx - ux * size + uy * size * 0.6, my - uy * size - ux * size * 0.6)], fill=colour)


ROUTE_CREDIT = "places: OpenBible.info / Theographic"


def render_route(title: str, stops: list, places: list, locator: tuple = LOCATOR,
                 credit: str = ROUTE_CREDIT) -> io.BytesIO:
    """A PNG map of a journey: `stops` (place dicts, in order, repeats allowed)
    joined by a line with arrows, each place numbered by when it is reached; the
    corner map shows `locator` (lon, lat, lon, lat), the Bible world unless told."""
    w, h = W * SCALE, H * SCALE
    img = Image.new("RGB", (w, h), SEA)
    draw = ImageDraw.Draw(img)
    lats, lons = [s["lat"] for s in stops], [s["lon"] for s in stops]
    lat0, lon0 = (min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2
    c = math.cos(math.radians(lat0))
    half = max((max(lats) - min(lats)) / 2 * 1.35 + 0.3,
               (max(lons) - min(lons)) * c / 2 * H / W * 1.35 + 0.3, 0.7)
    proj = _Projection(lat0 + half * 0.08, lon0, half, w, h)    # a little room above for the title
    _draw_geography(draw, proj)
    pts = [proj(s["lon"], s["lat"]) for s in stops]

    # which numbers each place gets: "Bethel 4, 6"
    order, numbers = [], {}
    for i, s in enumerate(stops, 1):
        key = s["name"]
        if key not in numbers:
            order.append(s)
            numbers[key] = []
        numbers[key].append(i)

    title_font = _font("georgiab.ttf", 24)
    tw = draw.textlength(title, font=title_font)
    title_box = (0, 0, tw + 40 * SCALE, 52 * SCALE)
    # the locator goes in whichever corner the route leaves empty
    trail = [(a[0] + (b[0] - a[0]) * t / 20, a[1] + (b[1] - a[1]) * t / 20)
             for a, b in zip(pts, pts[1:] or pts) for t in range(21)]
    corner = next((c for c, box in LOCATOR_SPOTS(w, h).items()
                   if not any(box[0] - 20 * SCALE < x < box[2] and box[1] < y < box[3] + 20 * SCALE
                              for x, y in trail)), "tr")
    boxes = [title_box, LOCATOR_SPOTS(w, h)[corner], (0, h - 60 * SCALE, 300 * SCALE, h),
             (w - 360 * SCALE, h - 30 * SCALE, w, h)]

    for a, b in zip(pts, pts[1:]):
        draw.line([a, b], fill=RED, width=4 * SCALE)
    for a, b in zip(pts, pts[1:]):
        _arrow(draw, a, b, RED, 11 * SCALE)

    r = 11 * SCALE
    for s in order:
        x, y = proj(s["lon"], s["lat"])
        boxes.append((x - r, y - r, x + r, y + r))
    font, num_font = _font("georgiab.ttf", 17), _font("georgiab.ttf", 15)
    th = 22 * SCALE
    labels = []
    for s in order:
        x, y = proj(s["lon"], s["lat"])
        nums = numbers[s["name"]]
        text = s["name"].split(" (")[0] + (f"  ({', '.join(map(str, nums))})" if len(nums) > 1 else "")
        t = draw.textlength(text, font=font)
        # beside the dot if there's room, else further out (with a leader line), in eight directions
        placed = None
        for d in (r + 5 * SCALE, r + 34 * SCALE, r + 70 * SCALE, r + 110 * SCALE):
            for ux, uy in ((1, 0), (-1, 0), (0, -1), (0, 1), (1, -1), (-1, -1), (1, 1), (-1, 1)):
                cx = x + ux * (d + t / 2) if ux else x
                cy = y + uy * (d + th / 2) if uy else y
                if ux and uy:
                    cx, cy = x + ux * (d * 0.7 + t / 2), y + uy * (d * 0.7 + th / 2)
                box = (cx - t / 2 - 4 * SCALE, cy - th / 2 - 2 * SCALE, cx + t / 2 + 4 * SCALE, cy + th / 2 + 2 * SCALE)
                if box[0] >= 0 and box[2] <= w and box[1] >= 0 and box[3] <= h and not _overlaps(box, boxes):
                    placed = (box, d > r + 5 * SCALE)
                    break
            if placed:
                break
        if placed is None:
            box = (x + r, y - th / 2, x + r + t + 8 * SCALE, y + th / 2 + 4 * SCALE)
            placed = (box, False)
        boxes.append(placed[0])
        labels.append((x, y, text, *placed))
    for x, y, text, box, leader in labels:
        if leader:
            bx = min(max(x, box[0]), box[2])
            by = min(max(y, box[1]), box[3])
            draw.line([(x, y), (bx, by)], fill=INK, width=2 * SCALE)
    for x, y, text, box, leader in labels:
        draw.rounded_rectangle(box, radius=4 * SCALE, fill=(255, 250, 240), outline=MUTED if leader else None,
                               width=SCALE)
        draw.text((box[0] + 4 * SCALE, box[1] + 2 * SCALE), text, font=font, fill=INK)

    for s in order:
        x, y = proj(s["lon"], s["lat"])
        if s.get("approx"):
            ring = 20 * SCALE
            for a in range(0, 360, 30):
                draw.arc((x - ring, y - ring, x + ring, y + ring), a, a + 15, fill=RED, width=3 * SCALE)
        first = numbers[s["name"]][0]
        draw.ellipse((x - r, y - r, x + r, y + r), fill=RED if first == 1 else (255, 255, 255),
                     outline=RED, width=3 * SCALE)
        draw.text((x, y + SCALE), str(first), font=num_font, fill=(255, 255, 255) if first == 1 else RED,
                  anchor="mm")

    draw.rectangle(title_box, fill=(255, 250, 240))
    draw.text((20 * SCALE, 12 * SCALE), title, font=title_font, fill=INK)
    _draw_scale(draw, proj, w, h)
    _draw_locator(img, proj, {"lat": lat0, "lon": lon0}, corner, locator)
    note = "Dashed rings: site uncertain · " if any(s.get("approx") for s in stops) else ""
    text = note + "Map: Natural Earth · " + credit
    cf = _font("georgia.ttf", 13)
    cw = draw.textlength(text, font=cf)
    draw.rectangle((w - cw - 16 * SCALE, h - 24 * SCALE, w, h), fill=(255, 255, 255))
    draw.text((w - cw - 8 * SCALE, h - 21 * SCALE), text, font=cf, fill=MUTED)

    img = img.resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


def _draw_scale(draw, proj, w: int, h: int) -> None:
    km_per_px = 111.0 / proj.k
    target = km_per_px * 160 * SCALE
    nice = next((n for n in (5, 10, 20, 25, 50, 100, 200, 250, 500, 1000) if n >= target * 0.6), 1000)
    px = nice / km_per_px
    x0, y0 = 24 * SCALE, h - 34 * SCALE
    draw.rectangle((x0 - 8 * SCALE, y0 - 24 * SCALE, x0 + px + 70 * SCALE, y0 + 14 * SCALE), fill=(255, 255, 255))
    draw.line((x0, y0, x0 + px, y0), fill=INK, width=3 * SCALE)
    for xx in (x0, x0 + px):
        draw.line((xx, y0 - 7 * SCALE, xx, y0 + 7 * SCALE), fill=INK, width=3 * SCALE)
    miles = round(nice * 0.621)
    draw.text((x0 + px + 8 * SCALE, y0 - 20 * SCALE), f"{nice} km", font=_font("georgia.ttf", 14), fill=INK)
    draw.text((x0 + px + 8 * SCALE, y0 - 4 * SCALE), f"{miles} mi", font=_font("georgia.ttf", 12), fill=MUTED)


def LOCATOR_SPOTS(w: int, h: int) -> dict:
    """Where the locator map can go: the area it covers, by corner (top right first)."""
    return {"tr": (w - 270 * SCALE, 0, w, 170 * SCALE),
            "br": (w - 270 * SCALE, h - 200 * SCALE, w, h - 30 * SCALE),
            "bl": (0, h - 230 * SCALE, 270 * SCALE, h - 60 * SCALE)}


def _draw_locator(img, main, place: dict, corner: str = "tr", region: tuple = LOCATOR) -> None:
    """A small map of the whole region in a corner (top right unless told), the main map's area boxed in red."""
    iw, ih = 250 * SCALE, 150 * SCALE
    lon_a, lat_a, lon_b, lat_b = region
    lat0, lon0 = (lat_a + lat_b) / 2, (lon_a + lon_b) / 2
    inset = Image.new("RGB", (iw, ih), SEA)
    d = ImageDraw.Draw(inset)
    proj = _Projection(lat0, lon0, (lat_b - lat_a) / 2, iw, ih)
    _draw_geography(d, proj, line_scale=0.5)
    a, b, c, e = main.bounds()
    x1, y1 = proj(a, e)
    x2, y2 = proj(c, b)
    if x2 - x1 < 8 * SCALE:                         # too small to see: a dot instead
        px, py = proj(place["lon"], place["lat"])
        d.ellipse((px - 5 * SCALE, py - 5 * SCALE, px + 5 * SCALE, py + 5 * SCALE), fill=RED)
    else:
        d.rectangle((x1, y1, x2, y2), outline=RED, width=3 * SCALE)
    d.rectangle((0, 0, iw - 1, ih - 1), outline=INK, width=2 * SCALE)
    spot = LOCATOR_SPOTS(img.width, img.height)[corner]
    img.paste(inset, (int(spot[0] + 10 * SCALE) if corner != "bl" else 16 * SCALE, int(spot[1]) + 16 * SCALE
                      if corner == "tr" else int(spot[3] - ih - 4 * SCALE)))
