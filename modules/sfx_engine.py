"""
Module: sfx_engine.py
======================
Updated for Teen Story Pipeline.

New emotion → SFX folder mappings added:
  romantic   → assets/sfx/romantic/    (piano hit, heartbeat, notification, sparkle)
  heartbreak → assets/sfx/heartbreak/  (glass shatter, thud, sad piano, sob)
  tension    → assets/sfx/tension/     (suspense sting, fast heartbeat, dramatic hit)
  crying     → assets/sfx/crying/      (sob, sniff, piano cry)
  awkward    → assets/sfx/awkward/     (crickets, buzzer, trombone)

Original emotions (shock, hype, rage, sadness, cringe) unchanged — Roblox pipeline unaffected.

SFX folder resolution order:
  1. Exact emotion folder  (e.g. assets/sfx/romantic/)
  2. Mapped fallback folder (e.g. heartbreak → sadness)
  3. Silence (logged as warning)
"""

import os
import random
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

_used_sfx: List[str] = []

# New emotions map to closest existing folder as fallback
# when the dedicated folder is empty / missing
EMOTION_FALLBACK = {
    "romantic":   "hype",
    "heartbreak": "sadness",
    "tension":    "shock",
    "crying":     "sadness",
    "awkward":    "cringe",
}


def _get_sfx_files(emotion: str, assets_dir: str) -> List[str]:
    """Return all audio files in assets/sfx/<emotion>/"""
    folder = os.path.join(assets_dir, "sfx", emotion)
    if not os.path.isdir(folder):
        return []
    exts = (".mp3", ".wav", ".ogg", ".m4a", ".mp4")
    files = []
    for f in os.listdir(folder):
        if f.lower().endswith(exts) and os.path.getsize(os.path.join(folder, f)) > 500:
            files.append(os.path.join(folder, f))
    return files


def _pick_sfx(emotion: str, assets_dir: str) -> Optional[str]:
    """
    Pick an SFX file for the given emotion.
    Tries dedicated folder first, then fallback folder.
    """
    candidates = _get_sfx_files(emotion, assets_dir)

    # Try fallback folder if dedicated is empty
    if not candidates:
        fallback_emotion = EMOTION_FALLBACK.get(emotion)
        if fallback_emotion:
            candidates = _get_sfx_files(fallback_emotion, assets_dir)
            if candidates:
                logger.debug(f"SFX: '{emotion}' folder empty, using fallback '{fallback_emotion}'")

    if not candidates:
        logger.warning(f"No SFX for '{emotion}' — run python download_sfx.py to add sounds")
        return None

    fresh  = [c for c in candidates if c not in _used_sfx]
    chosen = random.choice(fresh if fresh else candidates)
    _used_sfx.append(chosen)
    return chosen


def _build_sfx_clip(
    sfx_path: str,
    start_time: float,
    video_duration: float,
    sfx_volume: float,
    max_sfx_duration: float = 2.0,
) -> Optional[object]:
    try:
        from moviepy.editor import AudioFileClip

        if start_time >= video_duration - 0.5:
            return None

        sfx = AudioFileClip(sfx_path)

        # Trim to max_sfx_duration so SFX doesn't overrun narration
        if sfx.duration > max_sfx_duration:
            sfx = sfx.subclip(0, max_sfx_duration)

        # Never let SFX run past end of video
        remaining = video_duration - start_time - 0.05
        if sfx.duration > remaining:
            sfx = sfx.subclip(0, max(0.1, remaining))

        if sfx.duration <= 0.05:
            sfx.close()
            return None

        return sfx.volumex(sfx_volume).set_start(start_time)

    except Exception as e:
        logger.warning(f"SFX clip build failed ({sfx_path}): {e}")
        return None


def inject_sfx(
    emotion_data: List[Dict],
    video_duration: float,
    config: dict,
    assets_dir: str = "assets",
    selected_triggers: List[Dict] = None,
) -> Dict:
    sfx_cfg = config.get("sfx", {})
    if not sfx_cfg.get("enable_sfx", True):
        return {"sfx_clips": [], "sfx_used": []}

    sfx_volume       = sfx_cfg.get("sfx_volume", 0.15)
    max_sfx_duration = sfx_cfg.get("max_sfx_duration", 2.0)
    max_sfx_count    = sfx_cfg.get("max_sfx_per_video", 3)

    if selected_triggers is None:
        from modules.meme_engine import compute_inject_timestamps
        selected_triggers = compute_inject_timestamps(
            emotion_data, video_duration, max_sfx_duration, max_sfx_count
        )

    if not selected_triggers:
        logger.info("No SFX triggers found")
        return {"sfx_clips": [], "sfx_used": []}

    sfx_clips, sfx_used = [], []

    for trigger in selected_triggers:
        emotion  = trigger["emotion"]
        sfx_file = _pick_sfx(emotion, assets_dir)
        if not sfx_file:
            continue

        clip = _build_sfx_clip(sfx_file, trigger["inject_ts"],
                               video_duration, sfx_volume, max_sfx_duration)
        if clip:
            sfx_clips.append(clip)
            sfx_used.append({
                "emotion":   emotion,
                "file":      os.path.basename(sfx_file),
                "timestamp": trigger["inject_ts"],
            })
            logger.info(
                f"SFX: {os.path.basename(sfx_file)} [{emotion}] "
                f"@ {trigger['inject_ts']:.2f}s vol={sfx_volume}"
            )

    logger.info(f"SFX injected: {len(sfx_clips)}/{len(selected_triggers)}")
    return {"sfx_clips": sfx_clips, "sfx_used": sfx_used}


def reset_used_sfx():
    global _used_sfx
    _used_sfx = []
