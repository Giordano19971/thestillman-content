"""Render brand carousels (1080x1350 JPEG slides) for Instagram and TikTok photo mode.

Design v2: textured charcoal ground, slide counter + progress bar, big hook cover with a
bronze key word, oversized ghost numbers on point slides, larger readable body text and
a follow/save end card. Same slide schema as before (cover / point / cta).
"""
import random
from PIL import Image, ImageDraw, ImageFilter
from common import GROUND, INK, MUTED, BRONZE, LINE, font, logo_png

W, H = 1080, 1350
M = 96  # outer margin
HANDLE = "The Still Man"
STOP = {"a", "an", "the", "of", "to", "and", "or", "in", "on", "at", "for", "with", "is", "his", "your", "you", "he", "it",
        "before", "after", "when", "what", "how", "do", "this", "that", "4", "5", "3", "6", "7"}


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


def text_block(d, xy, text, f, fill, maxw, lh, accent=None, accent_fill=BRONZE):
    """Draw wrapped text; words in `accent` (lowercase, stripped) are drawn in accent_fill."""
    x, y = xy
    for ln in wrap(d, text, f, maxw):
        if accent:
            cx = x
            for i, w in enumerate(ln.split(" ")):
                piece = w + (" " if i < len(ln.split(" ")) - 1 else "")
                col = accent_fill if w.lower().strip(".,:;!?'\"") in accent else fill
                d.text((cx, y), piece, font=f, fill=col)
                cx += d.textlength(piece, font=f)
        else:
            d.text((x, y), ln, font=f, fill=fill)
        y += lh
    return y


def block_height(text, f, maxw, lh):
    d = ImageDraw.Draw(Image.new("RGB", (W, H)))
    return len(wrap(d, text, f, maxw)) * lh


_GROUND_CACHE = {}


def ground(seed=0):
    """Charcoal ground with a soft top glow, vignette and fine film grain."""
    if seed in _GROUND_CACHE:
        return _GROUND_CACHE[seed].copy()
    im = Image.new("RGB", (W, H), GROUND)
    glow = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-300, -520, W + 300, 620], fill=38)
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    warm = Image.new("RGB", (W, H), (58, 50, 42))
    im = Image.composite(warm, im, glow)
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).rectangle([0, 0, W, H], fill=0)
    edge = Image.new("L", (W, H), 255)
    ImageDraw.Draw(edge).ellipse([-200, -100, W + 200, H + 220], fill=0)
    edge = edge.filter(ImageFilter.GaussianBlur(140))
    im = Image.composite(Image.new("RGB", (W, H), (10, 11, 13)), im, edge.point(lambda v: int(v * 0.7)))
    rnd = random.Random(seed)
    noise = Image.effect_noise((W, H), 22).point(lambda v: 128 + (v - 128) // 3)
    im = Image.blend(im, Image.merge("RGB", (noise, noise, noise)), 0.06)
    _GROUND_CACHE[seed] = im
    return im.copy()


def chrome(im, d, idx, total, dark_mark=True):
    """Top bar (logo + handle, slide counter) and bottom progress segments."""
    try:
        lg = logo_png(56).resize((56, 56))
        im.paste(lg, (M, 70), lg)
        hx = M + 74
    except Exception:
        hx = M
    d.text((hx, 82), "The Still Man", font=font("Fraunces-600.ttf", 30), fill=INK)
    cnt = f"{idx}/{total}"
    cf = font("Inter-800.ttf", 26)
    d.text((W - M - d.textlength(cnt, font=cf), 86), cnt, font=cf, fill=MUTED)
    # progress bar
    gap, y = 10, H - 70
    seg = (W - 2 * M - gap * (total - 1)) / total
    for i in range(total):
        x0 = M + i * (seg + gap)
        d.rounded_rectangle([x0, y, x0 + seg, y + 6], 3, fill=BRONZE if i < idx else LINE)


def keywords(title, given=None):
    if given:
        return {w.lower() for w in given}
    words = [w.lower().strip(".,:;!?'\"") for w in title.split()]
    cand = [w for w in words if w and w not in STOP and len(w) > 3]
    return {max(cand, key=len)} if cand else set()


def slide(s, idx, total):
    k = s["kind"]
    im = ground(idx)
    d = ImageDraw.Draw(im)
    chrome(im, d, idx, total)
    if k == "cover":
        tf = font("Inter-800.ttf", 112 if len(s["title"]) < 40 else 96)
        title = s["title"].upper()
        lh = int(tf.size * 1.06)
        th = block_height(title, tf, W - 2 * M, lh)
        sub = s.get("subtitle", "")
        sf = font("Fraunces-600-Italic.ttf", 46)
        sh = block_height(sub, sf, W - 2 * M, 60) if sub else 0
        y = max(250, (H - th - sh - 90) // 2 - 20)
        y = text_block(d, (M, y), title, tf, INK, W - 2 * M, lh, accent=keywords(s["title"], s.get("accent")))
        d.rectangle([M, y + 34, M + 140, y + 40], fill=BRONZE)
        if sub:
            text_block(d, (M, y + 80), sub, sf, MUTED, W - 2 * M, 60)
        # swipe chip
        chip = "SWIPE"
        cf = font("Inter-800.ttf", 28)
        cw = d.textlength(chip, font=cf) + 110
        x0, y0 = W - M - cw, H - 170
        d.rounded_rectangle([x0, y0, W - M, y0 + 58], 29, outline=BRONZE, width=3)
        d.text((x0 + 30, y0 + 13), chip, font=cf, fill=BRONZE)
        ax = x0 + 30 + d.textlength(chip, font=cf) + 16
        d.line([(ax, y0 + 29), (ax + 34, y0 + 29)], fill=BRONZE, width=4)
        d.polygon([(ax + 34, y0 + 19), (ax + 48, y0 + 29), (ax + 34, y0 + 39)], fill=BRONZE)
    elif k == "point":
        num = str(s["num"])
        # ghost number
        gf = font("Fraunces-600.ttf", 560)
        gx = W - M - d.textlength(num, font=gf) + 40
        ghost = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(ghost).text((gx, 420), num, font=gf, fill=(*BRONZE, 34))
        im.paste(ghost, (0, 0), ghost); d = ImageDraw.Draw(im)
        tf = font("Fraunces-600.ttf", 92)
        bf = font("Inter-500.ttf", 54)
        th = block_height(s["title"], tf, W - 2 * M - 60, 102)
        bh = block_height(s.get("body", ""), bf, W - 2 * M - 70, 72) if s.get("body") else 0
        y = max(240, (H - (100 + th + 40 + bh)) // 2 - 10)
        d.rounded_rectangle([M, y, M + 96, y + 56], 28, fill=BRONZE)
        nf = font("Inter-800.ttf", 30)
        d.text((M + 48 - d.textlength(num.zfill(2), font=nf) / 2, y + 11), num.zfill(2), font=nf, fill=GROUND)
        y = text_block(d, (M, y + 100), s["title"], tf, INK, W - 2 * M - 60, 102)
        if s.get("body"):
            y += 40
            d.rectangle([M, y, M + 6, y + bh - 14], fill=BRONZE)
            text_block(d, (M + 40, y - 6), s["body"], bf, (205, 200, 191), W - 2 * M - 70, 72)
    elif k == "cta":
        tf = font("Fraunces-600.ttf", 100)
        th = block_height(s["title"], tf, W - 2 * M, 110)
        y = max(280, (H - th - 420) // 2)
        # bookmark icon
        bx, by = M, y
        d.polygon([(bx, by), (bx + 64, by), (bx + 64, by + 86), (bx + 32, by + 64), (bx, by + 86)], fill=BRONZE)
        y = text_block(d, (M, y + 130), s["title"], tf, INK, W - 2 * M, 110)
        bf = font("Inter-800.ttf", 36); label = (s.get("button", "Save") + " it").upper() if s.get("button", "Save") == "Save" else s["button"].upper()
        bw = d.textlength(label, font=bf) + 96
        d.rounded_rectangle([M, y + 60, M + bw, y + 150], 45, fill=BRONZE)
        d.text((M + 48, y + 84), label, font=bf, fill=GROUND)
        d.rectangle([M, H - 330, W - M, H - 328], fill=LINE)
        d.text((M, H - 290), "Follow " + HANDLE, font=font("Inter-800.ttf", 44), fill=INK)
        d.text((M, H - 222), "One small rep a day. Calm confidence, built daily.", font=font("Inter-500.ttf", 32), fill=MUTED)
    return im


def render(post, out_dir, prefix):
    paths = []
    total = len(post["slides"])
    for i, s in enumerate(post["slides"], 1):
        p = out_dir / f"{prefix}-{i}.jpg"
        slide(s, i, total).save(p, quality=92)
        paths.append(p)
    return paths
