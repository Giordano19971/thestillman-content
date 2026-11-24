"""Build every post of a week file into docs/<week>/ and write docs/<week>/manifest.json.

Usage: python pipeline/build_week.py content/weeks/2026-11-16.yaml [--only carousel]
Posts already built (listed in an existing manifest) are skipped, so re-runs are cheap.
"""
import json, re, os, shutil, sys, tempfile
from pathlib import Path
import yaml
from common import ROOT, VOICE_ID, TTS_MODEL, PAGES_BASE
import carousel, reel, sources


def main(week_file, only=None):
    spec = yaml.safe_load(Path(week_file).read_text())
    week = str(spec["week"])
    out = ROOT / "docs" / week; out.mkdir(parents=True, exist_ok=True)
    man_path = out / "manifest.json"
    manifest = json.loads(man_path.read_text()) if man_path.exists() else {"week": week, "posts": {}}
    used = set(manifest.get("pexels_used", []))
    url = lambda p: f"{PAGES_BASE}/{week}/{Path(p).name}"
    errors = []
    posts = sorted(spec["posts"], key=lambda p: p["type"] != "carousel")  # carousels first: no API keys needed
    for post in posts:
        pid = post["id"]
        if pid in manifest["posts"] or (only and post["type"] != only):
            continue
        try:
            entry = {k: post[k] for k in ("date", "time", "type", "platforms", "caption", "title", "tiktok_title", "tiktok_caption") if k in post}
            print(f"[build] {pid} ({post['type']})", flush=True)
            if post["type"] == "carousel":
                paths = carousel.render(post, out, pid)
                entry["images"] = [url(p) for p in paths]
            else:
                with tempfile.TemporaryDirectory() as tmp:
                    tmp = Path(tmp)
                    brolls, credits = [], []  # b-roll first: a failure here costs no TTS credits
                    for i, q in enumerate(post["broll"]):
                        pth, cr = sources.broll_video(q, used, tmp / f"b{i}.mp4", post.get("allow_statues", False))
                        brolls.append(pth); credits.append(cr)
                    words = sources.tts_with_words(post["voiceover"], post.get("voice_id", VOICE_ID), TTS_MODEL, tmp / "vo.mp3", post.get("voice_settings"))
                    mp4, jpg = out / f"{pid}.mp4", out / f"{pid}-cover.jpg"
                    dur = reel.render(post, words, tmp / "vo.mp3", brolls, tmp / "work", mp4, jpg)
                    (out / "voice").mkdir(exist_ok=True)
                    shutil.copy(tmp / "vo.mp3", out / "voice" / f"{pid}.mp3")
                entry.update(video=url(mp4), cover=url(jpg), duration=dur, broll_credits=credits)
                m = reel.pick_music(post)
                entry["music"] = m.name if m else None
            manifest["posts"][pid] = entry
            manifest["pexels_used"] = sorted(used)
            man_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str))
        except Exception as e:
            msg = re.sub(r"(key=)[^&\s'\"]+", r"\1***", f"{type(e).__name__}: {e}")
            for k in ("PIXABAY_API_KEY", "PEXELS_API_KEY", "ELEVENLABS_API_KEY"):
                if os.environ.get(k):
                    msg = msg.replace(os.environ[k], "***")
            print(f"[error] {pid}: {msg}", flush=True)
            errors.append(f"{pid}: {msg[:600]}")
    # add background music to reels built before music existed (no new TTS needed)
    for post in posts:
        e = manifest["posts"].get(post["id"])
        if not e or post["type"] == "carousel" or "music" in e:
            continue
        m = reel.pick_music(post)
        if not m:
            continue
        try:
            reel.add_music(out / f"{post['id']}.mp4", m, e["duration"], post.get("music_volume"),
                           out / "voice" / f"{post['id']}.mp3")
            e["music"] = m.name
            man_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str))
            print(f"[music] {post['id']} <- {m.name}", flush=True)
        except Exception as ex:
            errors.append(f"{post['id']} music: {ex}")
    print(f"[done] {len(manifest['posts'])} posts in {man_path}")
    err_path = out / "build-errors.txt"
    if errors:
        k = sources.PIXABAY_KEY
        hint = f"pixabay key: len={len(k)} format_ok={bool(re.fullmatch(r'\\d+-[0-9a-f]{25,40}', k))}"
        err_path.write_text("\n".join(errors) + "\n" + hint + "\n")
    elif err_path.exists():
        err_path.unlink()
    if errors:
        print("[failed] " + " | ".join(errors))
        sys.exit(1)


if __name__ == "__main__":
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    main(sys.argv[1], only)
