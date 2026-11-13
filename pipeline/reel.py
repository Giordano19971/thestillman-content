"""Render a 1080x1920 Reel: Pexels b-roll + brand grade + word-synced captions + voice + logo end card."""
import re, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from common import FONTS, logo_png

W, H, FPS = 1080, 1920, 30
BRONZE_ASS = "&H004E8AC0"; INK_ASS = "&H00DFE8ED"; MUTED_ASS = "&H00959EA3"
NUM_WORDS = {"one", "two", "three", "four", "five", "1", "2", "3", "4", "5"}


def run(cmd):
    subprocess.run(cmd, check=True)


def clean(w):
    return re.sub(r"[^\w']", "", w).lower()


def scene_cuts(words, n, dur):
    """Cut points for n scenes, snapped to the pauses in the voice nearest to equal splits."""
    gaps = [(words[i]["end"] + words[i + 1]["start"]) / 2 for i in range(len(words) - 1)
            if words[i + 1]["start"] - words[i]["end"] > 0.22]
    cuts = [0.0]
    for k in range(1, n):
        target = dur * k / n
        cand = [g for g in gaps if g > cuts[-1] + 1.2] or [target]
        cuts.append(min(cand, key=lambda g: abs(g - target)))
    cuts.append(dur)
    return cuts


def caption_groups(words, highlight):
    """Phrases split at punctuation/pauses/spoken numbers, then into balanced chunks of at most 3 words."""
    hl = {clean(h) for h in highlight}
    is_num = lambda w: clean(w["text"]) in NUM_WORDS and w["text"].endswith(".")
    phrases, cur = [], []
    for i, w in enumerate(words):
        nxt = words[i + 1] if i + 1 < len(words) else None
        if is_num(w):
            if cur: phrases.append(cur); cur = []
            phrases.append([w]); continue
        cur.append(w)
        if (nxt is None or re.search(r"[.,!?:;]$|\.\.\.$|…$", w["text"]) or nxt["start"] - w["end"] > 0.3 or is_num(nxt)):
            phrases.append(cur); cur = []
    if cur: phrases.append(cur)
    groups = []
    for p in phrases:
        n = -(-len(p) // 3)
        k = 0
        for j in range(n):
            size = len(p) // n + (1 if j < len(p) % n else 0)
            groups.append(p[k:k + size]); k += size
    out = []
    for i, g in enumerate(groups):
        start = g[0]["start"]
        end = groups[i + 1][0]["start"] if i + 1 < len(groups) else g[-1]["end"] + 1.2
        num = len(g) == 1 and is_num(g[0])
        out.append({"start": start, "end": end, "num": num,
                    "words": [(w["text"].replace("...", "").rstrip("…"), clean(w["text"]) in hl) for w in g]})
    return out


def ts(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def write_ass(path, groups, dur):
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Inter ExtraBold,90,{INK_ASS},{INK_ASS},&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,0,4,5,60,60,0,1
Style: Num,Fraunces SemiBold,190,{BRONZE_ASS},{BRONZE_ASS},&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,0,3,5,60,60,0,1
Style: Mark,Fraunces SemiBold,42,{MUTED_ASS},{MUTED_ASS},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,8,60,60,170,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{ts(0)},{ts(dur)},Mark,,0,0,0,,The Still Man
"""
    lines = []
    for g in groups:
        pop = r"{\pos(540,1150)\fscx88\fscy88\t(0,140,\fscx100\fscy100)}"
        if g["num"]:
            txt = re.sub(r"[^\w]", "", g["words"][0][0])
            txt = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5"}.get(txt.lower(), txt)
            lines.append(f"Dialogue: 1,{ts(g['start'])},{ts(g['end'])},Num,,0,0,0,,{pop}{txt}")
            continue
        parts = []
        for word, hl in g["words"]:
            parts.append(("{\\c" + BRONZE_ASS + "&}" + word + "{\\c" + INK_ASS + "&}") if hl else word)
        lines.append(f"Dialogue: 1,{ts(g['start'])},{ts(g['end'])},Cap,,0,0,0,,{pop}{' '.join(parts)}")
    Path(path).write_text(head + "\n".join(lines) + "\n", encoding="utf-8")


def shade_png(path):
    """Legibility gradient: darker top (wordmark) and a soft band behind captions."""
    a = Image.new("L", (W, H), 0); d = ImageDraw.Draw(a)
    for y in range(H):
        v = 0
        if y < 380: v = int(170 * (1 - y / 380))
        if 860 < y < 1440: v = max(v, int(120 * (1 - abs(y - 1150) / 290)))
        if y > 1500: v = max(v, int(90 * (y - 1500) / 420))
        d.line([(0, y), (W, y)], fill=v)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 255)); im.putalpha(a); im.save(path)


def render(post, words, audio, brolls, work, out_mp4, out_cover):
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    dur = round(words[-1]["end"] + 1.6, 2)
    cuts = scene_cuts(words, len(brolls), dur)
    clips = []
    for i, src in enumerate(brolls):
        d = cuts[i + 1] - cuts[i] + (0.3 if i < len(brolls) - 1 else 0)
        c = work / f"clip{i}.mp4"
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
              f"eq=saturation=0.72:contrast=1.05:brightness=-0.04,"
              f"colorchannelmixer=rr=1.04:gg=0.98:bb=0.9,vignette=PI/4.5,"
              f"fade=in:st=0:d=0.3,fade=out:st={max(0, d - 0.3):.2f}:d=0.3,format=yuv420p")
        run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-ss", "0.5", "-t", f"{d:.2f}", "-i", str(src),
             "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(c)])
        clips.append(c)
    lst = work / "list.txt"; lst.write_text("".join(f"file '{c.name}'\n" for c in clips))
    base = work / "base.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(base)])
    ass = work / "captions.ass"; write_ass(ass, caption_groups(words, post.get("highlight", [])), dur)
    shade = work / "shade.png"; shade_png(shade)
    logo = work / "logo.png"; logo_png(230).save(logo)
    t_logo = max(0.0, dur - 1.8)
    fc = (f"[0:v][1:v]overlay=0:0[s];[s]ass={ass}:fontsdir={FONTS}[c];"
          f"[2:v]format=rgba,fade=in:st={t_logo:.2f}:d=0.6:alpha=1[l];[c][l]overlay=(W-w)/2:360:shortest=0[v]")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(base), "-loop", "1", "-i", str(shade), "-loop", "1", "-i", str(logo),
         "-i", str(audio), "-filter_complex", fc, "-map", "[v]", "-map", "3:a", "-af", "apad",
         "-t", f"{dur:.2f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out_mp4)])
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1.2", "-i", str(out_mp4), "-frames:v", "1", "-q:v", "3", str(out_cover)])
    return dur
