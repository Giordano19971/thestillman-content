"""External sources: Pexels b-roll and ElevenLabs voice with word timings."""
import base64, os, random, time
import requests

PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "").strip().strip('"')
PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY", "").strip().strip('"')
ELEVEN_KEY = os.environ.get("ELEVENLABS_API_KEY", "").strip().strip('"')



def _check(r):
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code} from {r.url.split('?')[0]}: {r.text[:300]}")

def _get(url, **kw):
    for attempt in range(4):
        r = requests.get(url, timeout=60, **kw)
        if r.status_code == 429:
            time.sleep(5 * (attempt + 1)); continue
        _check(r)
        return r
    _check(r)


def pexels_video(query, used_ids, dest):
    """Download a portrait Pexels video matching `query` that has not been used yet. Returns path and credit."""
    if not PEXELS_KEY:
        raise RuntimeError("PEXELS_API_KEY missing")
    headers = {"Authorization": PEXELS_KEY}
    for q in (query, " ".join(query.split()[:3])):
        r = _get("https://api.pexels.com/videos/search", headers=headers,
                 params={"query": q, "orientation": "portrait", "size": "medium", "per_page": 15})
        videos = [v for v in r.json().get("videos", []) if v["id"] not in used_ids and v.get("duration", 0) >= 4]
        if videos:
            break
    if not videos:
        raise RuntimeError(f"No Pexels video for: {query}")
    v = videos[0] if len(videos) < 3 else random.Random(query).choice(videos[:3])
    files = [f for f in v["video_files"] if f.get("file_type") == "video/mp4" and f.get("height") and f["height"] >= f.get("width", 0)]
    files.sort(key=lambda f: abs(f["height"] - 1920))
    f = files[0] if files else v["video_files"][0]
    with _get(f["link"], stream=True) as resp, open(dest, "wb") as out:
        for chunk in resp.iter_content(1 << 20):
            out.write(chunk)
    used_ids.add(v["id"])
    return dest, {"pexels_id": v["id"], "author": v.get("user", {}).get("name"), "url": v.get("url")}


BANNED_TAGS = {"jesus", "christ", "buddha", "religion", "church", "angel", "man portrait", "old man", "elderly", "woman", "women", "girl", "girls", "lady", "portrait", "face", "faces", "model", "selfie", "mask",
               "animation", "animated", "cartoon", "illustration", "3d", "render", "cgi", "fantasy", "smoke bomb",
               "halloween", "christmas", "child", "children", "kid", "baby", "fashion", "party"}


_FACE_NET = None


def has_face(path, samples=8, conf=0.7):
    """True if a human face is visible in any sampled frame (brand rule: faceless). Uses OpenCV's SSD face model."""
    global _FACE_NET
    try:
        import cv2
    except ImportError:
        return False
    if _FACE_NET is None:
        d = os.path.join(os.path.dirname(__file__), "models")
        _FACE_NET = cv2.dnn.readNetFromCaffe(os.path.join(d, "face.prototxt"), os.path.join(d, "face.caffemodel"))
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    found = False
    for i in range(samples):
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(n * (i + 0.5) / samples)))
        ok, frame = cap.read()
        if not ok:
            continue
        h, w = frame.shape[:2]
        side = min(h, w)  # square tiles along the long side so faces are not squashed
        for off in range(0, max(h, w) - side + 1, max(1, (max(h, w) - side) // 2 or 1)):
            tile = frame[off:off + side, :] if h > w else frame[:, off:off + side]
            blob = cv2.dnn.blobFromImage(cv2.resize(tile, (300, 300)), 1.0, (300, 300), (104, 177, 123))
            _FACE_NET.setInput(blob)
            det = _FACE_NET.forward()
            if (det[0, 0, :, 2] > conf).any():
                found = True; break
        if found: break
    cap.release()
    return found


def pixabay_video(query, used_ids, dest, allow_statues=False):
    """Download a faceless, real-footage Pixabay video for `query` (prefers vertical/4K so a 9:16 crop stays sharp)."""
    if not PIXABAY_KEY:
        raise RuntimeError("PIXABAY_API_KEY missing")
    tried = 0
    banned = BANNED_TAGS - {"face", "faces", "portrait"} if allow_statues else BANNED_TAGS
    for q in (query, " ".join(query.split()[:3]), " ".join(query.split()[:2])):
        r = _get("https://pixabay.com/api/videos/", params={"key": PIXABAY_KEY, "q": q[:100], "per_page": 40,
                                                           "safesearch": "true", "video_type": "film"})
        hits = [h for h in r.json().get("hits", []) if f"pb{h['id']}" not in used_ids and h.get("duration", 0) >= 4
                and not ({t.strip() for t in h.get("tags", "").lower().split(",")} & banned)]
        def score(h):
            v = h["videos"]; big = v.get("large") or {}
            vertical = any(x.get("height", 0) > x.get("width", 0) for x in v.values() if isinstance(x, dict))
            return (vertical, big.get("height", 0) >= 2160, h.get("likes", 0))
        hits.sort(key=score, reverse=True)
        for h in hits[:6]:
            v = h["videos"]
            f = next(v[k] for k in ("large", "medium", "small") if v.get(k, {}).get("url"))
            with _get(f["url"], stream=True) as resp, open(dest, "wb") as out:
                for chunk in resp.iter_content(1 << 20):
                    out.write(chunk)
            used_ids.add(f"pb{h['id']}")
            tried += 1
            if not allow_statues and has_face(dest):
                continue
            return dest, {"pixabay_id": h["id"], "author": h.get("user"), "url": h.get("pageURL")}
    raise RuntimeError(f"No faceless Pixabay video for: {query} ({tried} rejected)")



def pixabay_image_clip(query, used_ids, dest, allow_statues=False, seconds=8):
    """A slow-zoom vertical clip from a Pixabay photo (for classical/statue imagery that rarely exists as video)."""
    import subprocess
    if not PIXABAY_KEY:
        raise RuntimeError("PIXABAY_API_KEY missing")
    banned = BANNED_TAGS - {"face", "faces", "portrait"} if allow_statues else BANNED_TAGS
    hits = []
    for q in (query, " ".join(query.split()[:2])):
        for orient in ("vertical", "all"):
            r = _get("https://pixabay.com/api/", params={"key": PIXABAY_KEY, "q": q[:100], "image_type": "photo",
                                                         "orientation": orient, "per_page": 40, "safesearch": "true"})
            hits = [h for h in r.json().get("hits", []) if f"pi{h['id']}" not in used_ids
                    and min(h.get("imageWidth", 0), h.get("imageHeight", 0)) >= 1000
                    and not ({t.strip() for t in h.get("tags", "").lower().split(",")} & banned)]
            if hits:
                break
        if hits:
            break
    if not hits:
        raise RuntimeError(f"No Pixabay photo for: {query}")
    hits.sort(key=lambda h: (h["imageHeight"] >= h["imageWidth"], h.get("likes", 0)), reverse=True)
    h = hits[0]
    img = str(dest) + ".jpg"
    with _get(h.get("largeImageURL") or h["webformatURL"], stream=True) as resp, open(img, "wb") as out:
        for chunk in resp.iter_content(1 << 20):
            out.write(chunk)
    frames = seconds * 30
    vf = ("scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
          f"zoompan=z='1+0.10*on/{frames}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", img, "-vf", vf, "-frames:v", str(frames),
                    "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(dest)], check=True)
    used_ids.add(f"pi{h['id']}")
    statue = bool({t.strip() for t in h.get("tags", "").lower().split(",")} &
                  {"statue", "sculpture", "bust", "marble", "monument", "figure", "stone"})
    if not statue and has_face(dest):
        return pixabay_image_clip(query, used_ids, dest, allow_statues, seconds)
    return dest, {"pixabay_image_id": h["id"], "author": h.get("user"), "url": h.get("pageURL")}

def broll_video(query, used_ids, dest, allow_statues=False):
    """Pexels when a key is configured, otherwise Pixabay. A query starting with "img:" uses a slow-zoom photo."""
    if query.startswith("img:"):
        return pixabay_image_clip(query[4:].strip(), used_ids, dest, allow_statues)
    if PEXELS_KEY:
        try:
            return pexels_video(query, used_ids, dest)
        except Exception as e:
            if not PIXABAY_KEY:
                raise
            print(f"[pexels] {e} -> falling back to Pixabay", flush=True)
    return pixabay_video(query, used_ids, dest, allow_statues)


def tts_with_words(text, voice_id, model, dest):
    """ElevenLabs TTS with timestamps. Writes MP3 to dest, returns list of words [{text,start,end}]."""
    if not ELEVEN_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY missing")
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps",
        headers={"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"},
        params={"output_format": "mp3_44100_128"},
        json={"text": text, "model_id": model,
              "voice_settings": {"stability": 0.55, "similarity_boost": 0.8, "style": 0.15, "use_speaker_boost": True}},
        timeout=180)
    _check(r)
    data = r.json()
    with open(dest, "wb") as f:
        f.write(base64.b64decode(data["audio_base64"]))
    al = data.get("normalized_alignment") or data["alignment"]
    chars, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    words, cur, s0 = [], "", None
    for c, s, e in zip(chars, st, en):
        if c.isspace():
            if cur:
                words.append({"text": cur, "start": s0, "end": last_e}); cur = ""
            continue
        if not cur:
            s0 = s
        cur += c; last_e = e
    if cur:
        words.append({"text": cur, "start": s0, "end": last_e})
    return words
