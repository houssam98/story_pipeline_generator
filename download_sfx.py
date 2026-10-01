"""
download_sfx.py
================
Downloads SFX using the Pixabay VIDEO API (documented, works reliably).

The Pixabay image/video API documented at pixabay.com/api/docs/ only covers
images (/api/) and videos (/api/videos/). There is no /api/audio/ endpoint.
Previous versions hit /api/audio/ which returned HTML error pages saved
as .mp3 — causing the "silent audio" bug.

This version:
  1. Uses /api/videos/ with category=music to find short SFX clips (.mp4)
  2. Extracts audio from each .mp4 using ffmpeg → saves as .mp3
  3. Validates files contain real audio (checks first bytes + ffprobe)
  4. Falls back to generate_sfx.py (ffmpeg synthesis) for any miss

Run order:
    python download_sfx.py    ← real recordings where available
    python generate_sfx.py    ← fills gaps with ffmpeg synthesis
"""

import os
import sys
import time
import json
import subprocess
import urllib.request
import urllib.parse
import urllib.error
import tempfile

API_KEY  = os.environ.get("PIXABAY_API_KEY", "7et dyalk asa7biiiiiiiiiiiiiiiiii")
BASE     = "assets/sfx"
VIDEO_API = "https://pixabay.com/api/videos/"


# ── Search queries: (dest, primary_query, fallback_query, category) ───────
# category must be one of Pixabay's accepted values:
# backgrounds, fashion, nature, science, education, feelings, health,
# people, religion, places, animals, industry, computer, food, sports,
# transportation, travel, buildings, business, music

MANIFEST = [
    # ── ROMANTIC ──────────────────────────────────────────────────────────
    ("romantic/notification_ding.mp3",  "notification ding",    "ding bell",         "music"),
    ("romantic/sparkle.mp3",            "sparkle magic chime",  "magic bells",       "music"),
    ("romantic/heartbeat_soft.mp3",     "heartbeat gentle",     "heart beat",        "health"),
    ("romantic/piano_hit.mp3",          "soft piano romantic",  "piano melody",      "music"),
    ("romantic/aww_crowd.mp3",          "crowd applause short", "audience cheer",    "people"),

    # ── HEARTBREAK ────────────────────────────────────────────────────────
    ("heartbreak/glass_shatter.mp3",    "glass breaking",       "glass shatter",     "industry"),
    ("heartbreak/deep_thud.mp3",        "impact thud bass",     "thud sound",        "music"),
    ("heartbreak/sad_piano.mp3",        "sad piano music",      "melancholy piano",  "music"),
    ("heartbreak/cry_sob.mp3",          "crying sobbing",       "cry weeping",       "people"),

    # ── TENSION ───────────────────────────────────────────────────────────
    ("tension/suspense_sting.mp3",      "suspense horror sting","tension music",     "music"),
    ("tension/heartbeat_fast.mp3",      "fast heartbeat panic", "rapid heartbeat",   "health"),
    ("tension/dramatic_hit.mp3",        "dramatic hit cinematic","epic hit music",   "music"),
    ("tension/clock_tick.mp3",          "clock ticking",        "ticking timer",     "buildings"),

    # ── AWKWARD ───────────────────────────────────────────────────────────
    ("awkward/crickets.mp3",            "crickets night",       "cricket insects",   "nature"),
    ("awkward/wrong_buzzer.mp3",        "fail buzzer sound",    "wrong answer buzz", "music"),
    ("awkward/trombone_sad.mp3",        "sad trombone fail",    "trombone womp",     "music"),

    # ── CRYING ────────────────────────────────────────────────────────────
    ("crying/sob.mp3",                  "person crying sobbing","crying sound",      "people"),
    ("crying/sniff.mp3",                "sniffling nose sound", "sniff quiet",       "people"),
    ("crying/piano_cry.mp3",            "emotional piano sad",  "sad piano crying",  "music"),

    # ── SHOCK ─────────────────────────────────────────────────────────────
    ("shock/female_gasp.mp3",           "gasp surprise",        "shock gasp",        "people"),
    ("shock/stinger.mp3",               "stinger music short",  "shock sound",       "music"),

    # ── SADNESS ───────────────────────────────────────────────────────────
    ("sadness/violin_sting.mp3",        "violin sad music",     "sad violin sting",  "music"),

    # ── HYPE ──────────────────────────────────────────────────────────────
    ("hype/whoosh.mp3",                 "whoosh transition",    "swoosh sound",      "music"),
]


# ── Helpers ────────────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept":          "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer":         "https://pixabay.com/",
        "Origin":          "https://pixabay.com",
    }


def _is_real_audio(data: bytes) -> bool:
    """Check magic bytes — reject HTML/JSON/empty responses."""
    if len(data) < 1000:
        return False
    # MP3 signatures
    if data[:3] == b'ID3':           return True   # ID3 tag
    if data[:2] in (b'\xff\xfb', b'\xff\xf3', b'\xff\xf2'): return True  # MPEG sync
    # OGG
    if data[:4] == b'OggS':          return True
    # MP4/M4A box
    if data[4:8] in (b'ftyp', b'moov', b'mdat', b'free'): return True
    # WAV
    if data[:4] == b'RIFF' and data[8:12] == b'WAVE': return True
    # Reject HTML/JSON
    if data[:1] in (b'<', b'{', b'['):  return False
    # Accept anything >50KB that isn't obviously text
    if len(data) > 50_000:
        text_chars = sum(1 for b in data[:200] if 32 <= b <= 126)
        if text_chars / 200 > 0.95:   # >95% printable ASCII = probably text
            return False
        return True
    return False


def _fetch(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        print(f"    HTTP {e.code}: {url[:70]}")
        return None
    except Exception as e:
        print(f"    Fetch error: {e}")
        return None


def _search_videos(query: str, category: str) -> list[str]:
    """Search Pixabay video API. Returns list of video URLs (tiny/small size)."""
    params = urllib.parse.urlencode({
        "key":        API_KEY,
        "q":          query,
        "per_page":   5,
        "safesearch": "true",
        "video_type": "film",
        # Only add category if it's relevant to avoid empty results
    })
    url  = f"{VIDEO_API}?{params}"
    data = _fetch(url)
    if not data:
        return []
    try:
        obj  = json.loads(data)
        hits = obj.get("hits", [])
        urls = []
        for h in hits:
            videos = h.get("videos", {})
            for size in ("tiny", "small"):
                v = videos.get(size, {})
                u = v.get("url", "")
                if u:
                    urls.append(u)
                    break
        return urls
    except Exception as e:
        print(f"    JSON parse error: {e}  data[:100]={data[:100]}")
        return []


def _extract_audio(video_data: bytes, dest: str) -> bool:
    """Write video bytes to temp file, extract audio with ffmpeg → dest."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_data)
        tmp_path = tmp.name
    try:
        r = subprocess.run([
            "ffmpeg", "-y", "-i", tmp_path,
            "-vn",                         # no video
            "-acodec", "libmp3lame",
            "-ar", "44100", "-ac", "1",
            "-q:a", "4",                   # ~128kbps
            "-t", "3.0",                   # max 3 seconds — we want short SFX
            dest
        ], capture_output=True, text=True)

        ok = (r.returncode == 0
              and os.path.exists(dest)
              and os.path.getsize(dest) > 1000)

        if not ok:
            # Check if source has no audio stream
            if "no streams" in r.stderr.lower() or "invalid data" in r.stderr.lower():
                return False
            # Try without -t limit (some short clips)
            r2 = subprocess.run([
                "ffmpeg", "-y", "-i", tmp_path,
                "-vn", "-acodec", "libmp3lame",
                "-ar", "44100", "-ac", "1", "-q:a", "4",
                dest
            ], capture_output=True, text=True)
            ok = (r2.returncode == 0
                  and os.path.exists(dest)
                  and os.path.getsize(dest) > 1000)

        return ok
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def _validate_audio(path: str) -> bool:
    """Use ffprobe to confirm file has a real audio stream with non-zero duration."""
    r = subprocess.run([
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams", path
    ], capture_output=True, text=True)
    try:
        data    = json.loads(r.stdout)
        streams = data.get("streams", [])
        for s in streams:
            if s.get("codec_type") == "audio":
                dur = float(s.get("duration", 0) or 0)
                if dur > 0.1:
                    return True
        return False
    except Exception:
        return False


# ── Main download logic ────────────────────────────────────────────────────

def download_one(rel_path: str, query: str, fallback: str, category: str) -> bool:
    dest = os.path.join(BASE, rel_path)
    name = os.path.basename(dest)

    if os.path.exists(dest) and _validate_audio(dest):
        kb = os.path.getsize(dest) // 1024
        print(f"  ~ SKIP   {name:<35} ({kb} KB, valid)")
        return True

    os.makedirs(os.path.dirname(dest), exist_ok=True)

    for attempt_query in (query, fallback):
        video_urls = _search_videos(attempt_query, category)
        if not video_urls:
            continue

        for vurl in video_urls:
            video_data = _fetch(vurl)
            if not video_data or not _is_real_audio(video_data):
                continue

            if _extract_audio(video_data, dest):
                if _validate_audio(dest):
                    kb = os.path.getsize(dest) // 1024
                    print(f"  ✓ OK     {name:<35} ({kb} KB)  [{attempt_query}]")
                    return True
                else:
                    # ffprobe says no real audio — delete and try next
                    try:
                        os.unlink(dest)
                    except Exception:
                        pass

    print(f"  ✗ FAIL   {name:<35} — no usable audio (run generate_sfx.py)")
    return False


def main():
    print("=" * 64)
    print("  Teen Story Pipeline — SFX Downloader")
    print(f"  Pixabay video API  |  key: {API_KEY[:14]}...")
    print("  Failed files → run: python generate_sfx.py")
    print("=" * 64)

    ok = fail = skip = 0

    for rel_path, query, fallback, category in MANIFEST:
        dest = os.path.join(BASE, rel_path)
        if os.path.exists(dest) and _validate_audio(dest):
            skip += 1
            kb = os.path.getsize(dest) // 1024
            print(f"  ~ SKIP   {os.path.basename(dest):<35} ({kb} KB)")
            continue

        result = download_one(rel_path, query, fallback, category)
        if result:
            ok += 1
        else:
            fail += 1
        time.sleep(0.4)

    print("\n" + "=" * 64)
    print(f"  ✓ Downloaded : {ok}")
    print(f"  ~ Skipped    : {skip}")
    print(f"  ✗ Failed     : {fail}")
    if fail:
        print(f"\n  Run: python generate_sfx.py")
        print(f"  It fills every failed slot with an ffmpeg-synthesized sound.")
    print("=" * 64)


if __name__ == "__main__":
    main()
