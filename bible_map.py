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


def _draw_locator(img, main, place: dict) -> None:
    """A small map of the whole region in the top-right corner, the main map's area boxed in red."""
    iw, ih = 250 * SCALE, 150 * SCALE
    lon_a, lat_a, lon_b, lat_b = LOCATOR
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
    img.paste(inset, (img.width - iw - 16 * SCALE, 16 * SCALE))
