"""
Module: output_logger.py
=========================
Updated to log memes_used, sfx_used, and emotion_tags_detected per video.
"""

import os
import csv
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def write_log(
    scripts:   List[Dict],
    clips:     List[Dict],
    subtitles: List[Dict],
    exports:   List[Dict],
    log_path:  str,
) -> None:
    os.makedirs(os.path.dirname(log_path) if os.path.dirname(log_path) else ".", exist_ok=True)

    # Index by version_id
    clips_map = {c.get("version_id"): c for c in clips}
    subs_map  = {s.get("version_id"): s for s in subtitles}
    exp_map   = {e.get("version_id"): e for e in exports}

    fieldnames = [
        "version_id", "hook", "word_count", "estimated_duration_seconds",
        "voice_name", "audio_duration", "audio_ok",
        "clip_start", "clip_length", "clip_ok",
        "subtitle_groups", "preset_used",
        "emotion_tags_detected",
        "memes_used", "sfx_used",
        "export_duration", "export_ok", "export_path",
    ]

    rows = []
    for script in scripts:
        vid   = script.get("version_id", "")
        clip  = clips_map.get(vid, {})
        sub   = subs_map.get(vid, {})
        exp   = exp_map.get(vid, {})

        # Flatten emotion summary
        emotion_summary = sub.get("emotion_summary", {})
        emotion_str     = " | ".join(
            f"{k}:{v}" for k, v in emotion_summary.items() if k != "neutral"
        )

        # Flatten memes used
        memes = exp.get("memes_used", [])
        memes_str = " | ".join(
            f"{m['emotion']}@{m['timestamp']:.1f}s:{m['file']}" for m in memes
        )

        # Flatten SFX used
        sfx   = exp.get("sfx_used", [])
        sfx_str = " | ".join(
            f"{s['emotion']}@{s['timestamp']:.1f}s:{s['file']}" for s in sfx
        )

        rows.append({
            "version_id":               vid,
            "hook":                     script.get("hook", "")[:60],
            "word_count":               script.get("word_count", 0),
            "estimated_duration_seconds": script.get("estimated_duration_seconds", 0),
            "voice_name":               script.get("voice_name", ""),
            "audio_duration":           round(script.get("audio_duration", 0), 2),
            "audio_ok":                 script.get("audio_ok", False),
            "clip_start":               round(clip.get("clip_start", 0), 2),
            "clip_length":              round(clip.get("clip_length", 0), 2),
            "clip_ok":                  clip.get("clip_ok", False),
            "subtitle_groups":          sub.get("group_count", 0),
            "preset_used":              sub.get("preset_used", ""),
            "emotion_tags_detected":    emotion_str or "none",
            "memes_used":               memes_str or "none",
            "sfx_used":                 sfx_str   or "none",
            "export_duration":          round(exp.get("duration", 0), 2),
            "export_ok":                exp.get("ok", False),
            "export_path":              exp.get("export_path", ""),
        })

    try:
        with open(log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        logger.info(f"Pipeline log saved: {log_path} ({len(rows)} entries)")
    except Exception as e:
        logger.error(f"Log write failed: {e}")


def print_summary(exports: List[Dict]) -> None:
    ok      = [e for e in exports if e.get("ok")]
    failed  = [e for e in exports if not e.get("ok")]
    total_memes = sum(len(e.get("memes_used", [])) for e in ok)
    total_sfx   = sum(len(e.get("sfx_used",   [])) for e in ok)

    print("\n" + "=" * 55)
    print(f"  PIPELINE COMPLETE")
    print(f"  ✅  {len(ok)} exported  |  ❌  {len(failed)} failed")
    print(f"  🎭  {total_memes} meme overlays injected")
    print(f"  🔊  {total_sfx} sound effects injected")
    print("=" * 55)
    for e in ok:
        memes = len(e.get("memes_used", []))
        sfx   = len(e.get("sfx_used",   []))
        print(
            f"  ✅  {e['version_id']}  "
            f"{e.get('duration', 0):.1f}s  "
            f"🎭×{memes}  🔊×{sfx}"
        )
    for e in failed:
        print(f"  ❌  {e.get('version_id')}  {e.get('error','unknown error')[:60]}")
    print("=" * 55 + "\n")
