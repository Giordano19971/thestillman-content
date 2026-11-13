"""Build every post of a week file into docs/<week>/ and write docs/<week>/manifest.json.

Usage: python pipeline/build_week.py content/weeks/2026-11-16.yaml [--only carousel]
Posts already built (listed in an existing manifest) are skipped, so re-runs are cheap.
"""
import json, re, os, sys, tempfile
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
            entry = {k: post[k] for k in ("date", "time", "type", "platforms", "caption", "title") if k in post}
            print(f"[build] {pid} ({post['type']})", flush=True)
            if post["type"] == "carousel":
                paths = carousel.render(post, out, pid)
                entry["images"] = [url(p) for p in paths]
            else:
                with tempfile.TemporaryDirectory() as tmp:
                    tmp = Path(tmp)
                    words = sources.tts_with_words(post["voiceover"], post.get("voice_id", VOICE_ID), TTS_MODEL, tmp / "vo.mp3")
                    brolls, credits = [], []
                    for i, q in enumerate(post["broll"]):
                        pth, cr = sources.broll_video(q, used, tmp / f"b{i}.mp4")
                        brolls.append(pth); credits.append(cr)
                    mp4, jpg = out / f"{pid}.mp4", out / f"{pid}-cover.jpg"
                    dur = reel.render(post, words, tmp / "vo.mp3", brolls, tmp / "work", mp4, jpg)
                entry.update(video=url(mp4), cover=url(jpg), duration=dur, broll_credits=credits)
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
    print(f"[done] {len(manifest['posts'])} posts in {man_path}")
    err_path = out / "build-errors.txt"
    if errors:
        err_path.write_text("\n".join(errors) + "\n")
    elif err_path.exists():
        err_path.unlink()
    if errors:
        print("[failed] " + " | ".join(errors))
        sys.exit(1)


if __name__ == "__main__":
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    main(sys.argv[1], only)
