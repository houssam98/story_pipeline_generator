"""
Module: meme_engine.py
=======================
Uses real subtitle-aligned timestamps.
Meme centered, 55% video width, pop animation.
"""

import os
import random
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)
_used_memes: List[str] = []


def _get_meme_files(emotion: str, assets_dir: str) -> List[str]:
    folder = os.path.join(assets_dir, "memes", emotion)
    if not os.path.isdir(folder):
        return []
    return [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    ]


def _pick_meme(emotion: str, assets_dir: str) -> Optional[str]:
    candidates = _get_meme_files(emotion, assets_dir)
    if not candidates:
        logger.warning(f"No meme assets for '{emotion}' in {assets_dir}/memes/{emotion}/")
        return None
    fresh = [c for c in candidates if c not in _used_memes] or candidates
    chosen = random.choice(fresh)
    _used_memes.append(chosen)
    return chosen


def _build_meme_clip(
    image_path: str,
    start_time: float,
    display_duration: float,
    video_w: int,
    video_h: int,
    video_duration: float,
) -> Optional[object]:
    try:
        from moviepy.editor import ImageClip
        import numpy as np
        from PIL import Image as PILImage

        if start_time >= video_duration - 0.2:
            return None
        display_duration = min(display_duration, video_duration - start_time - 0.1)
        if display_duration <= 0.1:
            return None

        # Size: 55% of video width
        target_w = int(video_w * 0.55)
        img      = PILImage.open(image_path).convert("RGBA")
        ratio    = target_w / img.width
        target_h = int(img.height * ratio)
        img      = img.resize((target_w, target_h), PILImage.LANCZOS)
        meme_w, meme_h = img.size

        # Always centered
        center_x = (video_w - meme_w) // 2
        center_y = (video_h - meme_h) // 2
        pop_dur  = 0.15

        def make_frame(t):
            scale  = min(1.0, 0.3 + 0.7 * (t / pop_dur)) if t < pop_dur else 1.0
            sw, sh = max(1, int(meme_w * scale)), max(1, int(meme_h * scale))
            scaled = img.resize((sw, sh), PILImage.LANCZOS)
            canvas = PILImage.new("RGBA", (meme_w, meme_h), (0, 0, 0, 0))
            canvas.paste(scaled, ((meme_w - sw) // 2, (meme_h - sh) // 2))
            return np.array(canvas)[:, :, :3]

        return (
            ImageClip(np.array(img)[:, :, :3])
            .fl(lambda gf, t: make_frame(t), apply_to="video")
            .set_start(start_time)
            .set_duration(display_duration)
            .set_position((center_x, center_y))
        )
    except Exception as e:
        logger.warning(f"Meme clip failed ({image_path}): {e}")
        return None


def compute_inject_timestamps(
    emotion_data: List[Dict],
    video_duration: float,
    display_duration: float,
    max_memes: int,
) -> List[Dict]:
    """
    Select injection points from emotion_data.
    Uses 'timestamp' field which is NOW a real subtitle-aligned time.
    Adds a small delay (0.3s) so the voice STARTS the sentence before
    the meme appears — feels natural, not early.
    """
    target_emotions = ["shock", "rage", "hype", "sadness", "cringe"]
    candidates = [e for e in emotion_data if e["emotion"] in target_emotions]
    if not candidates:
        return []

    selected, last_ts = [], -10.0
    shuffled = sorted(candidates, key=lambda x: x["timestamp"])  # chronological

    for c in shuffled:
        ts = c["timestamp"]
        if ts - last_ts >= 6.0 and len(selected) < max_memes:
            # +0.3s delay: voice says first word THEN meme appears
            inject_ts = round(ts + 0.3, 3)
            inject_ts = max(0.5, min(inject_ts, video_duration - display_duration - 0.5))
            selected.append({**c, "inject_ts": inject_ts})
            last_ts = ts

    return selected


def inject_memes(
    emotion_data: List[Dict],
    video_w: int,
    video_h: int,
    video_duration: float,
    config: dict,
    assets_dir: str = "assets",
    selected_triggers: List[Dict] = None,
) -> Dict:
    meme_cfg = config.get("memes", {})
    if not meme_cfg.get("enable_memes", True):
        return {"meme_clips": [], "memes_used": []}

    max_memes   = meme_cfg.get("max_memes_per_video", 3)
    display_dur = meme_cfg.get("meme_display_duration", 1.5)

    if selected_triggers is None:
        selected_triggers = compute_inject_timestamps(
            emotion_data, video_duration, display_dur, max_memes
        )

    if not selected_triggers:
        logger.info("No emotion triggers — no memes injected")
        return {"meme_clips": [], "memes_used": []}

    meme_clips, memes_used = [], []

    for trigger in selected_triggers:
        image = _pick_meme(trigger["emotion"], assets_dir)
        if not image:
            continue
        clip = _build_meme_clip(
            image, trigger["inject_ts"], display_dur,
            video_w, video_h, video_duration,
        )
        if clip:
            meme_clips.append(clip)
            memes_used.append({
                "emotion":   trigger["emotion"],
                "file":      os.path.basename(image),
                "timestamp": trigger["inject_ts"],
                "position":  "center",
            })
            logger.info(
                f"Meme: {os.path.basename(image)} ({trigger['emotion']}) "
                f"@ {trigger['inject_ts']:.3f}s  "
                f"[real_ts={trigger['timestamp']:.3f}s + 0.3s delay]"
            )

    logger.info(f"Memes injected: {len(meme_clips)}")
    return {"meme_clips": meme_clips, "memes_used": memes_used}


def reset_used_memes():
    global _used_memes
    _used_memes = []