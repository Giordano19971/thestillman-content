"""Shared brand constants and helpers for The Still Man content pipeline."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "brand" / "fonts"
LOGO_SVG = ROOT / "brand" / "logo-mono.svg"

GROUND = (21, 23, 26)
INK = (237, 232, 223)
MUTED = (163, 158, 149)
BRONZE = (192, 138, 78)
LINE = (52, 56, 61)

VOICE_ID = os.environ.get("VOICE_ID", "t1yzxMpe9zK42bXmI1T2")  # K. V. Hagen - Deep Warm Natural Narrator
TTS_MODEL = os.environ.get("TTS_MODEL", "eleven_multilingual_v2")
PAGES_BASE = os.environ.get("PAGES_BASE", "https://giordano19971.github.io/thestillman-content")


def font(name, size):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONTS / name), size)


def logo_png(size, color="#C08A4E"):
    import cairosvg, io
    from PIL import Image
    svg = LOGO_SVG.read_text().replace('fill="currentColor"', f'fill="{color}"').replace('stroke="currentColor"', f'stroke="{color}"')
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=size, output_height=size)
    return Image.open(io.BytesIO(png)).convert("RGBA")
