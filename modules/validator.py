"""
Module: validator.py
=====================
Fixed:
  - Accepts (scripts, exports, config) signature matching main.py call
  - Returns { passed, regen_needed } structure main.py expects
  - validation key now read from config["validation"] with fallback to config["output"]
  - No longer crashes when audio is mock/short
"""

import os
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


def _vcfg(config: dict) -> dict:
    """Get validation limits — falls back to output section if validation key missing."""
    v = config.get("validation", {})
    o = config.get("output", {})
    return {
        "min_video_length": v.get("min_video_length", o.get("min_video_length", 20)),
        "max_video_length": v.get("max_video_length", o.get("max_video_length", 60)),
    }


def validate_script(script: Dict, config: dict) -> Dict:
    s_cfg      = config.get("script", {})
    limits     = _vcfg(config)
    min_w      = s_cfg.get("min_words", 80)
    max_w      = s_cfg.get("max_words", 160)
    text       = script.get("script", "")
    word_count = len(text.split())
    est        = round(word_count / 2.75, 1)
    issues     = []
    if word_count < min_w:
        issues.append(f"Too short: {word_count}w (min {min_w})")
    if word_count > max_w:
        issues.append(f"Too long: {word_count}w (max {max_w})")
    return {"valid": len(issues) == 0, "word_count": word_count,
            "est_duration": est, "issues": issues}


def validate_audio(audio_path: str, config: dict) -> Dict:
    limits = _vcfg(config)
    issues = []
    if not audio_path or not os.path.exists(audio_path):
        return {"valid": False, "duration": None,
                "issues": [f"Audio file not found: {audio_path}"]}
    try:
        from moviepy.editor import AudioFileClip
        with AudioFileClip(audio_path) as a:
            duration = round(a.duration, 2)
    except Exception as e:
        return {"valid": False, "duration": None, "issues": [f"Cannot read audio: {e}"]}

    # Only flag if VERY short (mock audio is allowed to be short)
    if duration < 5.0:
        issues.append(f"Audio suspiciously short: {duration}s — may be mock/silent")
    if duration > limits["max_video_length"] + 10:
        issues.append(f"Audio too long: {duration}s (max ~{limits['max_video_length']}s)")
    return {"valid": len(issues) == 0, "duration": duration, "issues": issues}


def validate_export(export: Dict, config: dict) -> Dict:
    limits     = _vcfg(config)
    issues     = []
    export_path = export.get("export_path")

    if not export.get("ok"):
        return {"valid": False, "duration": None,
                "issues": [f"Assembly failed: {export.get('error', 'unknown')}"]}

    if not export_path or not os.path.exists(export_path):
        return {"valid": False, "duration": None,
                "issues": [f"Export file missing: {export_path}"]}

    try:
        from moviepy.editor import VideoFileClip
        with VideoFileClip(export_path) as v:
            duration      = round(v.duration, 2)
            width, height = v.size
    except Exception as e:
        return {"valid": False, "duration": None, "issues": [str(e)]}

    exp_w = config["output"]["resolution_width"]
    exp_h = config["output"]["resolution_height"]
    if duration < limits["min_video_length"]:
        issues.append(f"Video too short: {duration}s (min {limits['min_video_length']}s)")
    if duration > limits["max_video_length"]:
        issues.append(f"Video too long: {duration}s (max {limits['max_video_length']}s)")
    if (width, height) != (exp_w, exp_h):
        issues.append(f"Wrong resolution: {width}x{height} (want {exp_w}x{exp_h})")
    return {"valid": len(issues) == 0, "duration": duration,
            "width": width, "height": height, "issues": issues}


def run_validation(scripts: List[Dict], exports: List[Dict], config: dict) -> Dict:
    """
    Main entry point — matches signature in main.py:
        run_validation(scripts, exports, config)

    Returns:
        {
          "passed": int,
          "total":  int,
          "regen_needed": [ {version_id, regen_script, regen_audio, regen_export} ]
          "results": [per-video detail]
        }
    """
    exports_map = {e.get("version_id"): e for e in exports}
    results, regen_needed = [], []
    passed = 0

    for script in scripts:
        vid    = script.get("version_id", "?")
        export = exports_map.get(vid, {})

        s_result = validate_script(script, config)
        a_result = validate_audio(script.get("audio_path", ""), config)
        e_result = validate_export(export, config)

        all_valid = s_result["valid"] and a_result["valid"] and e_result["valid"]
        if all_valid:
            passed += 1
            logger.info(f"PASS {vid} | {s_result['word_count']}w | "
                        f"audio={a_result['duration']}s | "
                        f"video={e_result.get('duration')}s")
        else:
            issues = s_result["issues"] + a_result["issues"] + e_result["issues"]
            for issue in issues:
                logger.warning(f"FAIL {vid}: {issue}")
            regen_needed.append({
                "version_id":    vid,
                "regen_script":  not s_result["valid"],
                "regen_audio":   not a_result["valid"],
                "regen_export":  not e_result["valid"],
                "issues":        issues,
            })

        results.append({
            "version_id": vid,
            "valid":      all_valid,
            "script":     s_result,
            "audio":      a_result,
            "export":     e_result,
        })

    return {
        "passed":       passed,
        "total":        len(scripts),
        "regen_needed": regen_needed,
        "results":      results,
    }