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


def scene_cuts(words, n, dur, min_len=1.6):
    """Cut points for up to n scenes, snapped to voice pauses near equal splits; every scene >= min_len seconds."""
    n = max(1, min(n, int(dur // min_len)))
    gaps = [(words[i]["end"] + words[i + 1]["start"]) / 2 for i in range(len(words) - 1)
            if words[i + 1]["start"] - words[i]["end"] > 0.22]
    cuts = [0.0]
    for k in range(1, n):
        target = dur * k / n
        lo, hi = cuts[-1] + min_len, dur - min_len * (n - k)
        if lo > hi:
            break
        cand = [g for g in gaps if lo <= g <= hi] or [min(max(target, lo), hi)]
        cuts.append(min(cand, key=lambda g: abs(g - target)))
    cuts.append(dur)
    return cuts


def caption_groups(words, highlight, max_words=3, upper=False, lower=False):
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
        n = -(-len(p) // max_words)
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
                    "words": [((lambda t: t.upper() if upper else (t.lower() if lower else t))(w["text"].replace("...", "").rstrip("…")), clean(w["text"]) in hl) for w in g]})
    return out


def ts(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def write_ass(path, groups, dur, style="sans", strong_pop=False):
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{"Fraunces Italic Display" if style == "serif_italic" else "Inter ExtraBold"},{98 if style == "serif_italic" else 90},{INK_ASS},{INK_ASS},&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,0,4,5,60,60,0,1
Style: Num,Fraunces SemiBold,190,{BRONZE_ASS},{BRONZE_ASS},&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,0,3,5,60,60,0,1
Style: Mark,Fraunces SemiBold,42,{MUTED_ASS},{MUTED_ASS},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,8,60,60,170,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{ts(0)},{ts(dur)},Mark,,0,0,0,,The Still Man
"""
    lines = []
    for g in groups:
        pop = (r"{\pos(540,1150)\fscx70\fscy70\t(0,90,\fscx112\fscy112)\t(90,170,\fscx100\fscy100)}" if strong_pop
               else r"{\pos(540,1150)\fscx88\fscy88\t(0,140,\fscx100\fscy100)}")
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



MUSIC_DIR = Path(__file__).resolve().parent.parent / "brand" / "music"
MUSIC_VOLUME = 0.22


def pick_music(post):
    """Background track: post['music'] (file name or 'none'), else warm/* for core reels and dark/* for mono reels."""
    import hashlib
    choice = post.get("music")
    if choice == "none":
        return None
    if choice:
        p = MUSIC_DIR / choice
        return p if p.exists() else None
    mood = "dark" if post.get("grade") == "mono" else "warm"
    tracks = sorted((MUSIC_DIR / mood).glob("*.mp3"))
    if not tracks:
        return None
    return tracks[int(hashlib.md5(post["id"].encode()).hexdigest(), 16) % len(tracks)]

def series_tag(post):
    """On-screen series label for The 30-Day Rebuild episodes (title "Day N · ...")."""
    import re
    m = re.match(r"Day (\d+)\s*·", post.get("title", ""))
    if not m or "Rebuild" not in post.get("caption", ""):
        return ""
    f = f"{FONTS}/Inter-800.ttf"
    sh = ":shadowcolor=black@0.6:shadowx=2:shadowy=2"
    return (f",drawtext=fontfile={f}:text='THE 30-DAY REBUILD':fontsize=40:fontcolor=0xEDE8DF:x=(w-tw)/2:y=250{sh}"
            f",drawtext=fontfile={f}:text='DAY {m.group(1)} / 30':fontsize=34:fontcolor=0xC08A4E:x=(w-tw)/2:y=310{sh}")


WHOOSH = Path(__file__).resolve().parent.parent / "brand" / "sfx" / "whoosh.wav"


def add_whoosh(audio, work, times, vol=0.35):
    """Overlay a short whoosh at each intro cut onto the voice track (returns new audio path)."""
    out = Path(work) / "vo_sfx.wav"
    ins = ["-i", str(audio)] + sum([["-i", str(WHOOSH)] for _ in times], [])
    parts = [f"[{k + 1}:a]adelay={int(t * 1000)}|{int(t * 1000)},volume={vol}[w{k}]" for k, t in enumerate(times)]
    fc = ";".join(parts) + ";[0:a]" + "".join(f"[w{k}]" for k in range(len(times))) + \
         f"amix=inputs={len(times) + 1}:duration=first:normalize=0[a]"
    run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", fc, "-map", "[a]", str(out)])
    return out

def render(post, words, audio, brolls, work, out_mp4, out_cover):
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    dur = round(words[-1]["end"] + 1.6, 2)
    v2 = post.get("style") == "v2"
    if v2 and len(brolls) >= 5:
        # three fast 0.7 s cuts to stop the scroll, then normal scenes snapped to voice pauses
        intro = [0.0, 0.7, 1.4, 2.1]
        rest = scene_cuts([{**w, "start": w["start"] - 2.1, "end": w["end"] - 2.1} for w in words if w["start"] >= 2.1] or words, len(brolls) - 3, dur - 2.1)
        cuts = intro + [2.1 + c for c in rest[1:]]
    else:
        cuts = scene_cuts(words, len(brolls), dur)
    brolls = brolls[:len(cuts) - 1]
    clips = []
    for i, src in enumerate(brolls):
        d = cuts[i + 1] - cuts[i] + (0.3 if (i < len(brolls) - 1 and not (v2 and i < 3)) else 0)
        c = work / f"clip{i}.mp4"
        grade = ("eq=saturation=0.75:contrast=1.06:gamma=1.12:brightness=0.02,"
                 "colorchannelmixer=rr=1.04:gg=0.98:bb=0.9,vignette=PI/5,") if (v2 and post.get("grade") != "mono") else \
                ("eq=saturation=0.12:contrast=1.12:brightness=-0.05,colorchannelmixer=rr=1.03:gg=1.0:bb=0.95,"
                 "noise=alls=7:allf=t,vignette=PI/4,") if post.get("grade") == "mono" else \
                ("eq=saturation=0.72:contrast=1.05:brightness=-0.04,"
                 "colorchannelmixer=rr=1.04:gg=0.98:bb=0.9,vignette=PI/4.5,")
        fades = "" if (v2 and i < 3) else f"fade=in:st=0:d=0.3,fade=out:st={max(0, d - 0.3):.2f}:d=0.3,"
        zoom = (f"zoompan=z='min(1+0.10*on/{max(1, int(d * FPS))},1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},"
                if (v2 and i == 0) else "")
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},{zoom}"
              f"{grade}{fades}format=yuv420p")
        run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-ss", "0.5", "-t", f"{d:.2f}", "-i", str(src),
             "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(c)])
        clips.append(c)
    lst = work / "list.txt"; lst.write_text("".join(f"file '{c.name}'\n" for c in clips))
    base = work / "base.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(base)])
    ass = work / "captions.ass"; write_ass(ass, caption_groups(words, post.get("highlight", []), post.get("caption_words", 2 if v2 else 3), post.get("caption_upper", False), post.get("caption_lower", False)), dur, post.get("caption_style", "sans"), strong_pop=v2)
    shade = work / "shade.png"; shade_png(shade)
    logo = work / "logo.png"; logo_png(230).save(logo)
    t_logo = max(0.0, dur - 1.8)
    fc = (f"[0:v][1:v]overlay=0:0[s];[s]ass={ass}:fontsdir={FONTS}{series_tag(post)}[c];"
          f"[2:v]format=rgba,fade=in:st={t_logo:.2f}:d=0.6:alpha=1[l];[c][l]overlay=(W-w)/2:360:shortest=0[v]")
    music = pick_music(post)
    if music:
        fc += (f";[3:a]apad,atrim=0:{dur:.2f},asplit[v1][v2];"
               f"[4:a]atrim=0:{dur:.2f},volume={post.get('music_volume', MUSIC_VOLUME)},afade=t=in:d=0.8,"
               f"afade=t=out:st={max(0, dur - 1.8):.2f}:d=1.8[m];"
               f"[m][v2]sidechaincompress=threshold=0.04:ratio=5:attack=25:release=450[md];"
               f"[v1][md]amix=inputs=2:duration=first:normalize=0[a]")
        ins = ["-i", str(audio), "-stream_loop", "-1", "-i", str(music)]
        amap = ["-map", "[a]"]
    else:
        ins = ["-i", str(audio)]
        amap = ["-map", "3:a", "-af", "apad"]
    if v2 and WHOOSH.exists():
        audio = add_whoosh(audio, work, [0.0, 0.7, 1.4, 2.1])
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(base), "-loop", "1", "-i", str(shade), "-loop", "1", "-i", str(logo),
         *ins, "-filter_complex", fc, "-map", "[v]", *amap,
         "-t", f"{dur:.2f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out_mp4)])
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1.2", "-i", str(out_mp4), "-frames:v", "1", "-q:v", "3", str(out_cover)])
    return dur


def add_music(mp4, music, dur, volume=None, voice=None):
    """Mix a background track under the existing voice of a rendered reel (video stream copied)."""
    volume = MUSIC_VOLUME if volume is None else volume
    mp4 = Path(mp4); tmp = mp4.with_suffix(".music.mp4")
    src = [str(voice)] if voice and Path(voice).exists() else [str(mp4)]
    fc = (f"[0:a]apad,atrim=0:{dur:.2f},asplit[v1][v2];"
          f"[1:a]atrim=0:{dur:.2f},volume={volume},afade=t=in:d=0.8,afade=t=out:st={max(0, dur - 1.8):.2f}:d=1.8[m];"
          f"[m][v2]sidechaincompress=threshold=0.04:ratio=5:attack=25:release=450[md];"
          f"[v1][md]amix=inputs=2:duration=first:normalize=0[a]")
    if src[0] != str(mp4):
        fc = fc.replace("[0:a]", "[2:a]")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-stream_loop", "-1", "-i", str(music),
         *(["-i", src[0]] if src[0] != str(mp4) else []),
         "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-t", f"{dur:.2f}", "-movflags", "+faststart", str(tmp)])
    tmp.replace(mp4)
