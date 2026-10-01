"""
Module: subtitle_generator.py
================================
Style overhaul:
  - 2 words per group (modern TikTok pacing)
  - Arial-Bold font, size 88-96
  - 4px black stroke — readable on any background
  - Emotion-aware color: white/yellow/red per emotion
  - Position at 75% vertical — below face area
  - Audio-aligned timing via ffmpeg silencedetect
"""

import re
import os
import random
import logging
import subprocess
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

# Emotion → subtitle color
EMOTION_COLORS = {
    "romantic":   "#FF88CC",   # pink — butterflies/love
    "heartbreak": "#AA44FF",   # purple — broken/betrayal
    "tension":    "#FF8800",   # orange — dread/confrontation
    "crying":     "#88CCFF",   # same as sadness
    "awkward":    "#AAAAAA",   # grey — crickets/silence
    "shock":   "#FFFFFF",
    "hype":    "#FFFF00",
    "rage":    "#FF4444",
    "sadness": "#88CCFF",
    "cringe":  "#FF88FF",
    "neutral": "#FFFFFF",
}


# ---------------------------------------------------------------------------
# Audio alignment via ffmpeg silencedetect
# ---------------------------------------------------------------------------
def _get_real_word_timestamps(audio_path: str, script_text: str) -> List[Tuple[str, float]]:
    try:
        dur_cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                   "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
        dur_r    = subprocess.run(dur_cmd, capture_output=True, text=True, timeout=15)
        duration = float(dur_r.stdout.strip())

        sil_cmd = ["ffmpeg", "-i", audio_path,
                   "-af", "silencedetect=noise=-32dB:d=0.12", "-f", "null", "-"]
        sil_r   = subprocess.run(sil_cmd, capture_output=True, text=True, timeout=30)
        stderr  = sil_r.stderr

        sil_starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", stderr)]
        sil_ends   = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", stderr)]

        speech_segs, cursor = [], 0.0
        for ss, se in zip(sil_starts, sil_ends):
            if ss > cursor + 0.05:
                speech_segs.append((cursor, ss))
            cursor = se
        if cursor < duration - 0.05:
            speech_segs.append((cursor, duration))
        if not speech_segs:
            return []

        clean = re.sub(r"\[.*?\]", "", script_text).strip()
        words = clean.split()
        if not words:
            return []

        total_speech = sum(e - s for s, e in speech_segs)
        wps = len(words) / max(total_speech, 0.1)

        word_times, w_idx = [], 0
        for seg_s, seg_e in speech_segs:
            seg_dur   = seg_e - seg_s
            seg_words = max(1, round(seg_dur * wps))
            for i in range(seg_words):
                if w_idx >= len(words): break
                t = seg_s + (i / seg_words) * seg_dur
                word_times.append((words[w_idx], round(t, 3)))
                w_idx += 1
            if w_idx >= len(words): break
        while w_idx < len(words):
            word_times.append((words[w_idx], round(duration - 0.3, 3)))
            w_idx += 1

        logger.info(f"Audio alignment: {len(speech_segs)} speech segs, {len(word_times)} words timed")
        return word_times

    except Exception as e:
        logger.warning(f"Audio alignment failed ({e}) — falling back to proportional")
        return []


def _timings_from_word_timestamps(
    word_times: List[Tuple[str, float]],
    words_per_group: int,
    audio_duration: float,
) -> List[Tuple[float, float, str]]:
    timings, i = [], 0
    while i < len(word_times):
        chunk = word_times[i: i + words_per_group]
        text  = " ".join(w for w, _ in chunk)
        start = chunk[0][1]
        end   = word_times[i + words_per_group][1] if i + words_per_group < len(word_times) else audio_duration
        end   = min(end, audio_duration)
        if end > start:
            timings.append((round(start, 3), round(end, 3), text))
        i += words_per_group
    return timings


def _timings_proportional(groups, audio_duration):
    total = sum(len(g.split()) for g in groups)
    out, cur = [], 0.0
    for g in groups:
        wc  = len(g.split())
        dur = max(0.2, (wc / total) * audio_duration)
        s, e = round(cur, 3), round(min(cur + dur, audio_duration), 3)
        out.append((s, e, g))
        cur = e
    return out


def _group_words(text: str, n: int) -> List[str]:
    text  = re.sub(r"\[.*?\]", "", text).strip()
    words = text.split()
    out, i = [], 0
    while i < len(words):
        out.append(" ".join(words[i:i + n]))
        i += n
    return out


# ---------------------------------------------------------------------------
# Subtitle clip builder — modern TikTok style
# ---------------------------------------------------------------------------
def _get_emotion_color(text: str, emotion_data: List[Dict]) -> str:
    """Match this subtitle group to an emotion and return its color."""
    text_words = set(re.sub(r"[^\w]", "", w.lower()) for w in text.split())
    for entry in emotion_data:
        if entry.get("emotion", "neutral") == "neutral":
            continue
        entry_words = set(re.sub(r"[^\w]", "", w.lower()) for w in entry.get("sentence", "").split())
        if text_words & entry_words:
            return EMOTION_COLORS.get(entry["emotion"], "#FFFFFF")
    return "#FFFFFF"


def _build_subtitle_clips(
    timings: List[Tuple[float, float, str]],
    preset: dict,
    video_width: int,
    video_height: int,
    emotion_data: Optional[List[Dict]] = None,
) -> List:
    from moviepy.editor import TextClip
    clips = []
    pos_y = int(video_height * preset.get("position_y_ratio", 0.75))

    for start, end, text in timings:
        dur = end - start
        if dur <= 0:
            continue

        # Color: emotion-aware if data available, else preset color
        color = preset.get("color", "white")
        if emotion_data:
            ec = _get_emotion_color(text, emotion_data)
            if ec != "#FFFFFF":
                color = ec

        try:
            clip = (
                TextClip(
                    text.upper(),
                    fontsize    = preset.get("fontsize", 88),
                    font        = preset.get("font", "Arial-Bold"),
                    color       = color,
                    stroke_color= preset.get("stroke_color", "black"),
                    stroke_width= preset.get("stroke_width", 4),
                    method      = "caption",
                    size        = (int(video_width * 0.88), None),
                    align       = "center",
                    kerning     = -1,   # tighter letter spacing — modern look
                    interline   = -4,   # tighter line height
                )
                .set_start(start)
                .set_duration(dur)
                .set_position(("center", pos_y))
            )
            clips.append(clip)
        except Exception:
            # Fallback: simpler TextClip without advanced params
            try:
                clip = (
                    TextClip(
                        text.upper(),
                        fontsize    = preset.get("fontsize", 88),
                        font        = "Impact",
                        color       = "white",
                        stroke_color= "black",
                        stroke_width= 4,
                        method      = "caption",
                        size        = (int(video_width * 0.88), None),
                        align       = "center",
                    )
                    .set_start(start)
                    .set_duration(dur)
                    .set_position(("center", pos_y))
                )
                clips.append(clip)
            except Exception as e2:
                logger.warning(f"TextClip failed '{text[:25]}': {e2}")
    return clips


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def generate_subtitles(
    script_data: Dict,
    audio_duration: float,
    config: dict,
    video_width: int  = 1080,
    video_height: int = 1920,
) -> Dict:
    from modules.emotion_detector import detect_emotions, align_emotions_to_subtitles

    sub_cfg     = config["subtitles"]
    presets     = sub_cfg.get("presets", {})
    preset_name = (
        "hype" if random.random() > 0.6 and "hype" in presets
        else sub_cfg.get("active_preset", "default")
    )
    preset          = presets.get(preset_name, presets.get("default", {}))
    words_per_group = preset.get("words_per_group", 2)
    pos_y_ratio     = sub_cfg.get("subtitle_position_y_ratio", 0.75)
    preset["position_y_ratio"] = pos_y_ratio

    audio_path  = script_data.get("audio_path", "")
    script_text = script_data["script"]

    # Real audio timing
    timings = []
    method  = "proportional"
    if audio_path and os.path.exists(audio_path):
        word_times = _get_real_word_timestamps(audio_path, script_text)
        if word_times:
            timings = _timings_from_word_timestamps(word_times, words_per_group, audio_duration)
            method  = "audio-aligned"

    if not timings:
        groups  = _group_words(script_text, words_per_group)
        timings = _timings_proportional(groups, audio_duration)

    # Detect emotions first so subtitle builder can color-code
    model        = config.get("script", {}).get("ollama_model", "gpt-oss:120b-cloud")
    emotion_data = detect_emotions(script_text, model=model)
    emotion_data = align_emotions_to_subtitles(emotion_data, timings)

    sub_clips = _build_subtitle_clips(timings, preset, video_width, video_height, emotion_data)

    emotion_counts = {}
    for e in emotion_data:
        emotion_counts[e["emotion"]] = emotion_counts.get(e["emotion"], 0) + 1

    logger.info(
        f"Subtitles {script_data['version_id']}: "
        f"{len(timings)} groups [{method}] preset='{preset_name}' "
        f"emotions={emotion_counts}"
    )
    return {
        "version_id":      script_data["version_id"],
        "subtitle_clips":  sub_clips,
        "timings":         timings,
        "preset_used":     preset_name,
        "timing_method":   method,
        "group_count":     len(timings),
        "emotion_data":    emotion_data,
        "emotion_summary": emotion_counts,
    }