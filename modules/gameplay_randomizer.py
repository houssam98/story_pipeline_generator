"""
Module: gameplay_randomizer.py
================================
Fix 2 — Crop to 9:16 instead of resize/shrink:
  Scale so the SHORT side fills the target, then center-crop the excess.
  No black bars, no distortion, zero content loss on the dominant axis.

  Landscape 16:9 source  → scale height to 1920 → width = 3413 → crop sides to 1080
  Portrait  source       → scale width  to 1080 → height ≥ 1920 → crop top/bottom
"""

import os
import random
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _get_video_info(path: str) -> Tuple[float, int, int]:
    from moviepy.editor import VideoFileClip
    with VideoFileClip(path) as c:
        return c.duration, c.size[0], c.size[1]


def _smart_crop_to_9_16(clip, out_w: int, out_h: int):
    """
    Scale then center-crop to out_w × out_h without ANY distortion.
    Always fills the full frame — no black bars ever.
    """
    src_w, src_h = clip.size
    scale_by_w   = out_w / src_w   # scale factor if we fit width
    scale_by_h   = out_h / src_h   # scale factor if we fit height

    # Use whichever scale makes BOTH dimensions >= target (fills the frame)
    scale = max(scale_by_w, scale_by_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    clip  = clip.resize((new_w, new_h))

    # Center crop to exact target
    x1 = (new_w - out_w) // 2
    y1 = (new_h - out_h) // 2
    clip = clip.crop(x1=x1, y1=y1, x2=x1 + out_w, y2=y1 + out_h)
    return clip


def extract_clip(
    source_path: str,
    version_id: str,
    config: dict,
    audio_duration: float = None,
    output_dir: str = "gameplay",
    used_starts: Optional[List[float]] = None,
) -> Dict:
    from moviepy.editor import VideoFileClip, concatenate_videoclips
    import moviepy.video.fx.all as vfx

    clip_cfg   = config["clip"]
    speed_min  = clip_cfg["speed_variation_min"]
    speed_max  = clip_cfg["speed_variation_max"]
    zoom_px    = clip_cfg.get("zoom_variation_px", 15)
    out_w      = config["output"]["resolution_width"]
    out_h      = config["output"]["resolution_height"]
    max_dur    = config["output"].get("max_video_length", 60)  # safety ceiling

    # Clip length synced to actual audio duration
    clip_length = min(
        audio_duration if audio_duration else clip_cfg["max_length_seconds"],
        max_dur
    )

    os.makedirs(output_dir, exist_ok=True)
    used_starts   = used_starts or []
    total_dur, sw, sh = _get_video_info(source_path)
    max_start = total_dur - clip_length

    if max_start <= 0:
        raise ValueError(
            f"Source video ({total_dur:.1f}s) too short for clip ({clip_length:.1f}s)."
        )

    for _ in range(30):
        start = round(random.uniform(0, max_start), 2)
        if all(abs(start - s) >= 10 for s in used_starts):
            break

    end   = round(start + clip_length, 2)
    speed = round(random.uniform(speed_min, speed_max), 3)
    output_path = os.path.join(output_dir, f"clip_{version_id}.mp4")

    try:
        with VideoFileClip(source_path) as src:
            sub = src.subclip(start, min(end, total_dur))

            # Loop if source is shorter than needed
            if sub.duration < clip_length:
                loops = int(clip_length / sub.duration) + 2
                sub   = concatenate_videoclips([sub] * loops)
            sub = sub.subclip(0, clip_length)

            # Speed variation
            if abs(speed - 1.0) > 0.005:
                sub = sub.fx(vfx.speedx, speed)

            # ── Crop to exact 9:16 (no distortion, no black bars) ────────
            sub = _smart_crop_to_9_16(sub, out_w, out_h)

            # Minor additional uniquification crop
            if zoom_px > 0:
                w, h  = sub.size
                x1    = random.randint(0, zoom_px)
                y1    = random.randint(0, zoom_px)
                x2    = w - random.randint(0, zoom_px)
                y2    = h - random.randint(0, zoom_px)
                sub   = sub.crop(x1=x1, y1=y1, x2=x2, y2=y2)
                sub   = sub.resize((out_w, out_h))

            sub.write_videofile(
                output_path,
                fps=config["output"]["fps"],
                codec="libx264",
                audio=False,
                verbose=False,
                logger=None,
            )

        logger.info(
            f"Clip {version_id}: start={start}s len={clip_length:.1f}s "
            f"speed={speed}x src={sw}x{sh} → {out_w}x{out_h} [smart-crop]"
        )
        return {
            "version_id": version_id,
            "clip_start":  start,
            "clip_end":    end,
            "clip_length": clip_length,
            "speed":       speed,
            "clip_path":   output_path,
            "clip_ok":     True,
        }

    except Exception as e:
        logger.error(f"Clip extraction failed {version_id}: {e}")
        return {"version_id": version_id, "clip_path": None, "clip_ok": False}


def extract_all_clips(
    source_path: str,
    scripts: List[Dict],
    config: dict,
    output_dir: str = "gameplay",
) -> List[Dict]:
    results, used_starts = [], []
    for script in scripts:
        vid       = script["version_id"]
        audio_dur = script.get("audio_duration")
        result    = extract_clip(source_path, vid, config, audio_dur, output_dir, used_starts)
        if result.get("clip_ok"):
            used_starts.append(result["clip_start"])
        results.append(result)
    return results