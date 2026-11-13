"""Render brand carousels (1080x1350 JPEG slides) for Instagram and TikTok photo mode."""
from PIL import Image, ImageDraw
from common import GROUND, INK, MUTED, BRONZE, LINE, font

W, H = 1080, 1350
M = 96  # outer margin


def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if d.textlength(t, font=f) <= maxw:
            cur = t
        else:
            lines.append(cur); cur = word
    if cur: lines.append(cur)
    return lines


def text_block(d, xy, text, f, fill, maxw, lh):
    x, y = xy
    for ln in wrap(d, text, f, maxw):
        d.text((x, y), ln, font=f, fill=fill); y += lh
    return y


def base(mark=True):
    im = Image.new("RGB", (W, H), GROUND)
    d = ImageDraw.Draw(im)
    if mark: d.text((M, H - 92), "The Still Man", font=font("Fraunces-600.ttf", 30), fill=MUTED)
    return im, d


def slide(s):
    k = s["kind"]
    im, d = base(mark=(k != "cta"))
    if k == "cover":
        y = text_block(d, (M, 300), s["title"], font("Fraunces-600.ttf", 104), INK, W - 2 * M, 112)
        d.rectangle([M, y + 40, M + 300, y + 43], fill=BRONZE)
        if s.get("subtitle"):
            text_block(d, (M, y + 80), s["subtitle"], font("Inter-500.ttf", 34), MUTED, W - 2 * M, 46)
    elif k == "point":
        d.text((M, 230), str(s["num"]), font=font("Fraunces-600.ttf", 200), fill=BRONZE)
        y = text_block(d, (M, 500), s["title"], font("Fraunces-600.ttf", 84), INK, W - 2 * M, 94)
        d.rectangle([M, y + 36, W - M, y + 38], fill=LINE)
        if s.get("body"):
            text_block(d, (M, y + 72), s["body"], font("Inter-500.ttf", 40), MUTED, W - 2 * M - 40, 54)
    elif k == "cta":
        y = text_block(d, (M, 330), s["title"], font("Fraunces-600.ttf", 96), INK, W - 2 * M, 106)
        bf = font("Inter-800.ttf", 34); label = s.get("button", "Save")
        bw = d.textlength(label, font=bf) + 80
        d.rounded_rectangle([M, y + 60, M + bw, y + 140], 6, fill=BRONZE)
        d.text((M + 40, y + 81), label, font=bf, fill=GROUND)
        d.text((M, H - 300), "The Still Man", font=font("Fraunces-600.ttf", 72), fill=INK)
        d.text((M, H - 205), "Calm confidence, built daily.", font=font("Inter-500.ttf", 32), fill=MUTED)
    return im


def render(post, out_dir, prefix):
    paths = []
    for i, s in enumerate(post["slides"], 1):
        p = out_dir / f"{prefix}-{i}.jpg"
        slide(s).save(p, quality=92)
        paths.append(p)
    return paths
