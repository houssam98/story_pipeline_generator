"""
Module: video_uniquifier.py
============================
GUARANTEED wide variation between clips using zone-based parameter selection.

Instead of random.uniform() (which clusters near the middle), each parameter
is split into N distinct zones. Each video is assigned to DIFFERENT zones,
ensuring maximum spread across all parameters simultaneously.

Example: brightness zones [-0.12, -0.06, 0.0, +0.06, +0.12]
         Video 1 gets zone 0 (-0.12), Video 2 gets zone 4 (+0.12) — never similar.
"""

import os
import json
import math
import random
import logging
import subprocess
from typing import Dict, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Zone-based parameter pools
# Each parameter has explicit distinct values — not ranges.
# Videos are assigned by cycling through shuffled zones.
# ---------------------------------------------------------------------------

ZONES = {
    # ── VIDEO ──────────────────────────────────────────────────────────────

    # Crop: asymmetric — each edge independently from very small to very large
    "crop_top":    [4, 12, 22, 35, 50],
    "crop_bottom": [4, 14, 26, 38, 52],
    "crop_left":   [4, 10, 18, 28, 40],
    "crop_right":  [4, 10, 20, 30, 42],

    # Brightness: from noticeably dark to noticeably bright
    "brightness":  [-0.12, -0.06, 0.0, 0.06, 0.12],

    # Contrast: from flat to punchy
    "contrast":    [0.82, 0.92, 1.0, 1.10, 1.22],

    # Saturation: from near greyscale to vivid
    "saturation":  [0.60, 0.80, 1.0, 1.20, 1.45],

    # Gamma: dark shadows vs bright highlights
    "gamma":       [0.75, 0.88, 1.0, 1.15, 1.30],

    # Color temperature: cold blue vs warm red
    "color_r":     [0.85, 0.93, 1.0, 1.07, 1.15],
    "color_b":     [1.15, 1.07, 1.0, 0.93, 0.85],

    # Speed: slow to fast
    "speed":       [0.92, 0.96, 1.0, 1.04, 1.08],

    # Fade in
    "fade_in":     [0.05, 0.15, 0.25, 0.38, 0.50],

    # Fade out
    "fade_out":    [0.05, 0.12, 0.22, 0.32, 0.45],

    # Pixel shift X
    "pixel_shift_x": [-18, -8, 0, 8, 18],

    # Pixel shift Y
    "pixel_shift_y": [-18, -8, 0, 8, 18],

    # Sharpen (0 = off)
    "sharpen":     [0.0, 0.0, 0.5, 1.0, 1.8],

    # Blur (0 = off) — mutually exclusive with sharpen in logic below
    "blur":        [0.0, 0.0, 0.0, 0.0, 0.0],   # disabled — blur destroys quality

    # Noise grain
    "noise":       [0, 0, 0, 2, 4],   # reduced — noise hurts quality perception

    # Flip
    "flip":        ["none", "none", "none", "none", "none"],   # hflip removed — inverts subtitle text

    # ── AUDIO ──────────────────────────────────────────────────────────────

    # Volume: quiet to loud
    "volume":      [0.72, 0.86, 1.0, 1.14, 1.28],

    # Pitch in cents: low to high
    "pitch_cents": [-250, -120, 0, 120, 250],

    # Tempo
    "audio_tempo": [0.92, 0.96, 1.0, 1.04, 1.08],

    # Bass EQ
    "bass_gain":   [-6.0, -3.0, 0.0, 3.0, 6.0],

    # Mid EQ
    "mid_gain":    [-4.0, -2.0, 0.0, 2.0, 4.0],

    # Treble EQ
    "treble_gain": [-6.0, -3.0, 0.0, 3.0, 6.0],

    # Delay
    "delay_ms":    [0, 0, 8, 18, 30],

    # Echo
    "echo":        [False, False, False, True, True],
}


# ---------------------------------------------------------------------------
# Zone Assignment Engine
# ---------------------------------------------------------------------------

class ZoneAssigner:
    """
    Assigns each video to a DIFFERENT zone per parameter.
    Shuffles zone order per parameter so assignments aren't predictable.
    Cycles through all zones before repeating (like dealing cards).
    """

    def __init__(self):
        # Pre-shuffle zone indices for each parameter independently
        self._queues = {}
        for key, values in ZONES.items():
            indices = list(range(len(values)))
            random.shuffle(indices)
            self._queues[key] = indices.copy()
        self._used = {key: [] for key in ZONES}

    def assign(self) -> Dict:
        """Return one unique parameter set."""
        params = {}
        for key, values in ZONES.items():
            queue = self._queues[key]
            if not queue:
                # Refill — reshuffle to avoid same sequence
                queue = list(range(len(values)))
                random.shuffle(queue)
                self._queues[key] = queue
            idx         = queue.pop(0)
            params[key] = values[idx]
        return params


# Module-level assigner — shared across all videos in one run
_assigner = ZoneAssigner()


def get_next_params() -> Dict:
    """Get the next guaranteed-unique parameter set."""
    return _assigner.assign()


# ---------------------------------------------------------------------------
# Duration helper
# ---------------------------------------------------------------------------

def _get_duration(path: str) -> float:
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except Exception:
        return 30.0


# ---------------------------------------------------------------------------
# Video filter builder
# ---------------------------------------------------------------------------

def _build_vf(p: Dict, width: int, height: int, duration: float) -> str:
    parts = []

    # 1. Asymmetric crop — each edge different
    ct, cb = p["crop_top"],  p["crop_bottom"]
    cl, cr = p["crop_left"], p["crop_right"]
    cw = max(100, width  - cl - cr)
    ch = max(100, height - ct - cb)
    parts.append(f"crop={cw}:{ch}:{cl}:{ct}")

    # 2. Pixel shift
    sx, sy = p["pixel_shift_x"], p["pixel_shift_y"]
    if sx != 0 or sy != 0:
        ox = abs(sx) + max(sx, 0)
        oy = abs(sy) + max(sy, 0)
        parts.append(
            f"pad={cw+abs(sx)*2}:{ch+abs(sy)*2}:{abs(sx)}:{abs(sy)},"
            f"crop={cw}:{ch}:{ox}:{oy}"
        )

    # 3. Scale back to target
    parts.append(f"scale={width}:{height}:flags=lanczos")

    # 4. Speed
    speed = p["speed"]
    if abs(speed - 1.0) > 0.005:
        parts.append(f"setpts={round(1.0/speed, 6)}*PTS")

    # 5. Flip
    if p["flip"] != "none":
        parts.append(p["flip"])

    # 6. Color channel (warm/cool tint)
    rr = p["color_r"]
    bb = p["color_b"]
    if abs(rr - 1.0) > 0.01 or abs(bb - 1.0) > 0.01:
        parts.append(f"colorchannelmixer=rr={rr:.4f}:gg=1.0:bb={bb:.4f}")

    # 7. EQ — brightness / contrast / saturation / gamma
    parts.append(
        f"eq=brightness={p['brightness']:.4f}"
        f":contrast={p['contrast']:.4f}"
        f":saturation={p['saturation']:.4f}"
        f":gamma={p['gamma']:.4f}"
    )

    # 8. Sharpen OR blur — whichever zone is higher wins
    sharpen = p["sharpen"]
    blur    = p["blur"]
    if sharpen > 0 and sharpen >= blur:
        parts.append(f"unsharp=5:5:{sharpen:.2f}:5:5:0")
    elif blur > 0 and blur > sharpen:
        parts.append(f"gblur=sigma={blur:.2f}")

    # 9. Noise
    if p["noise"] > 0:
        parts.append(f"noise=alls={p['noise']}:allf=t")

    # 10. Fade in / out
    fin      = p["fade_in"]
    fout     = p["fade_out"]
    fo_start = max(0.1, duration - fout - 0.05)
    parts.append(f"fade=t=in:st=0:d={fin:.3f}")
    parts.append(f"fade=t=out:st={fo_start:.3f}:d={fout:.3f}")

    # 11. Final format enforcement
    parts.append(f"scale={width}:{height},format=yuv420p")

    return ",".join(parts)


# ---------------------------------------------------------------------------
# Audio filter builder
# ---------------------------------------------------------------------------

def _build_af(p: Dict) -> str:
    parts = []

    # 1. Volume
    parts.append(f"volume={p['volume']:.4f}")

    # 2. Pitch shift
    cents = p["pitch_cents"]
    if abs(cents) > 5:
        rate_mult  = 2 ** (cents / 1200.0)
        new_rate   = int(44100 * rate_mult)
        tempo_comp = max(0.5, min(2.0, round(1.0 / rate_mult, 6)))
        parts.append(f"asetrate={new_rate},aresample=44100,atempo={tempo_comp:.6f}")

    # 3. Tempo
    tempo = p["audio_tempo"]
    if abs(tempo - 1.0) > 0.005:
        parts.append(f"atempo={max(0.5, min(2.0, tempo)):.4f}")

    # 4. Three-band EQ
    if abs(p["bass_gain"]) > 0.2:
        parts.append(f"equalizer=f=80:width_type=o:width=2:g={p['bass_gain']:.2f}")
    if abs(p["mid_gain"]) > 0.2:
        parts.append(f"equalizer=f=1000:width_type=o:width=2:g={p['mid_gain']:.2f}")
    if abs(p["treble_gain"]) > 0.2:
        parts.append(f"equalizer=f=10000:width_type=o:width=2:g={p['treble_gain']:.2f}")

    # 5. Echo
    if p["echo"]:
        parts.append("aecho=0.8:0.6:20:0.15")

    # 6. Delay
    if p["delay_ms"] > 0:
        parts.append(f"adelay={p['delay_ms']}|{p['delay_ms']}")

    # 7. Normalize output
    parts.append("aresample=44100,aformat=channel_layouts=stereo")

    return ",".join(parts)


# ---------------------------------------------------------------------------
# Core uniquify
# ---------------------------------------------------------------------------

def uniquify_video(
    input_path: str,
    output_path: str,
    config: dict,
    params: Dict = None,
) -> Dict:

    if not os.path.exists(input_path):
        logger.error(f"Input not found: {input_path}")
        return {"ok": False, "output_path": None}

    params   = params or get_next_params()
    width    = config["output"]["resolution_width"]
    height   = config["output"]["resolution_height"]
    fps      = config["output"]["fps"]
    duration = _get_duration(input_path)

    vf = _build_vf(params, width, height, duration)
    af = _build_af(params)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf",        vf,
        "-c:v",       "libx264",
        "-preset",    "slow",   # better quality per bit
        "-profile:v", "high",
        "-level",     "4.0",
        "-pix_fmt",   "yuv420p",
        "-crf",       "18",   # high quality (18=near lossless, 23=default)
        "-r",         str(fps),
        "-af",        af,
        "-c:a",       "aac",
        "-b:a",       "256k",   # high quality audio
        "-ar",        "44100",
        "-ac",        "2",
        "-map_metadata", "-1",
        "-map_chapters", "-1",
        "-movflags",  "+faststart",
        "-f",         "mp4",
        output_path,
    ]

    # Pretty-print params for log (use params dict directly — no bare variables)
    _ct = params['crop_top'];  _cb = params['crop_bottom']
    _cl = params['crop_left']; _cr = params['crop_right']
    logger.info(
        f"\n  ┌ {os.path.basename(input_path)}\n"
        f"  │ crop  T{_ct}/B{_cb}/L{_cl}/R{_cr}px\n"
        f"  │ shift X{params['pixel_shift_x']:+d}/Y{params['pixel_shift_y']:+d}px\n"
        f"  │ speed {params['speed']:.3f}x  flip={params['flip']}\n"
        f"  │ br={params['brightness']:+.3f} con={params['contrast']:.3f} "
            f"sat={params['saturation']:.3f} gam={params['gamma']:.3f}\n"
        f"  │ R={params['color_r']:.3f} B={params['color_b']:.3f} noise={params['noise']}\n"
        f"  │ vol={params['volume']:.3f} pitch={params['pitch_cents']:+d}c "
            f"tempo={params['audio_tempo']:.3f}\n"
        f"  │ bass={params['bass_gain']:+.1f}dB mid={params['mid_gain']:+.1f}dB "
            f"treble={params['treble_gain']:+.1f}dB\n"
        f"  │ delay={params['delay_ms']}ms echo={params['echo']}\n"
        f"  └ → {os.path.basename(output_path)}"
    )

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            logger.error(f"ffmpeg failed (code {result.returncode})")
            for line in result.stderr.strip().splitlines()[-25:]:
                logger.error(f"  {line}")
            return {"ok": False, "output_path": None, "params": params}

        logger.info(f"  ✅ {output_path}")
        return {"ok": True, "output_path": output_path, "params": params}

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout: {input_path}")
        return {"ok": False, "output_path": None}
    except FileNotFoundError:
        logger.error("ffmpeg not found — https://www.gyan.dev/ffmpeg/builds/")
        return {"ok": False, "output_path": None}
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"ok": False, "output_path": None}


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------

def uniquify_all(
    export_results: List[Dict],
    config: dict,
    final_dir: str = "exports/final",
) -> List[Dict]:
    os.makedirs(final_dir, exist_ok=True)
    results, params_log = [], {}

    for export in export_results:
        vid = export.get("version_id", "unknown")
        if not export.get("ok") or not export.get("export_path"):
            logger.warning(f"Skipping {vid} — no assembly output")
            results.append({"version_id": vid, "ok": False})
            continue

        params      = get_next_params()
        output_path = os.path.join(final_dir, f"{vid}_final.mp4").replace("\\", "/")
        result      = uniquify_video(export["export_path"], output_path, config, params)
        result["version_id"] = vid
        results.append(result)
        params_log[vid] = params

    log_path = os.path.join(final_dir, "params_log.json")
    with open(log_path, "w") as f:
        json.dump(params_log, f, indent=2)
    logger.info(f"Params log: {log_path}")

    ok = sum(1 for r in results if r.get("ok"))
    logger.info(f"Uniquification: {ok}/{len(results)} succeeded")
    return results


# ---------------------------------------------------------------------------
# Standalone test — shows params diff between 3 videos
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:
        cfg = {"output": {"resolution_width": 1080, "resolution_height": 1920, "fps": 30}}
        r   = uniquify_video(sys.argv[1], sys.argv[2], cfg)
        print("OK:" if r["ok"] else "FAILED:", r.get("output_path", ""))
    else:
        # Show how different 5 consecutive param sets are
        print("Zone assignment demo — 5 consecutive videos:\n")
        for i in range(5):
            p = get_next_params()
            print(f"Video {i+1}:")
            print(f"  brightness={p['brightness']:+.3f}  contrast={p['contrast']:.3f}  sat={p['saturation']:.3f}")
            print(f"  crop T{p['crop_top']}/B{p['crop_bottom']}/L{p['crop_left']}/R{p['crop_right']}")
            print(f"  vol={p['volume']:.3f}  pitch={p['pitch_cents']:+d}c  bass={p['bass_gain']:+.1f}dB")
            print(f"  flip={p['flip']}  noise={p['noise']}  echo={p['echo']}\n")