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


def pixabay_video(query, used_ids, dest):
    """Download a Pixabay video for `query` (prefers 4K/vertical so a 9:16 crop stays sharp)."""
    if not PIXABAY_KEY:
        raise RuntimeError("PIXABAY_API_KEY missing")
    hits = []
    for q in (query, " ".join(query.split()[:3]), " ".join(query.split()[:2])):
        r = _get("https://pixabay.com/api/videos/", params={"key": PIXABAY_KEY, "q": q[:100], "per_page": 30, "safesearch": "true"})
        hits = [h for h in r.json().get("hits", []) if f"pb{h['id']}" not in used_ids and h.get("duration", 0) >= 4]
        if hits:
            break
    if not hits:
        raise RuntimeError(f"No Pixabay video for: {query}")
    def score(h):
        v = h["videos"]; big = v.get("large") or {}
        vertical = any(x.get("height", 0) > x.get("width", 0) for x in v.values() if isinstance(x, dict))
        return (vertical, big.get("height", 0) >= 2160, h.get("likes", 0))
    hits.sort(key=score, reverse=True)
    h = hits[0]
    v = h["videos"]
    f = next(v[k] for k in ("large", "medium", "small") if v.get(k, {}).get("url"))
    with _get(f["url"], stream=True) as resp, open(dest, "wb") as out:
        for chunk in resp.iter_content(1 << 20):
            out.write(chunk)
    used_ids.add(f"pb{h['id']}")
    return dest, {"pixabay_id": h["id"], "author": h.get("user"), "url": h.get("pageURL")}


def broll_video(query, used_ids, dest):
    """Pexels when a key is configured, otherwise Pixabay."""
    if PEXELS_KEY:
        try:
            return pexels_video(query, used_ids, dest)
        except Exception as e:
            if not PIXABAY_KEY:
                raise
            print(f"[pexels] {e} -> falling back to Pixabay", flush=True)
    return pixabay_video(query, used_ids, dest)


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
