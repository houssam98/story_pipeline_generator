"""
Module: video_assembler.py
===========================
Fixes in this version:
  - duration key always correctly set in return dict (was 0.0)
  - Mild 1.1x speedup applied to video+audio (not aggressive, just snappier)
    Audio: atempo=1.1 (pitch-stable), Video: setpts=0.909*PTS
    Applied via ffmpeg as a post-process after moviepy composite
  - Videos over max_video_length are trimmed (not sped up beyond 1.1x)
  - Pattern interrupt at t=3s (zoom flash)
  - First subtitle locked to t=0

Mild speedup rationale:
  1.1x = 10% faster. A 30s video becomes 27s. A 35s becomes 32s.
  Voice stays natural — atempo preserves pitch perfectly.
  Audience perceives it as "energetic" not "rushed".
"""

import os
import logging
import subprocess
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

MILD_SPEED = 1.10   # 10% speedup — change here to adjust globally


def _fix_path(path: str) -> str:
    return os.path.abspath(path).replace("\\", "/")


def get_audio_duration(audio_path: str) -> float:
    from moviepy.editor import AudioFileClip
    try:
        with AudioFileClip(_fix_path(audio_path)) as a:
            return round(a.duration, 2)
    except Exception as e:
        logger.warning(f"Could not read audio duration: {e}")
        return 30.0


# ---------------------------------------------------------------------------
# Mild speedup via ffmpeg (post-process on final composite)
# ---------------------------------------------------------------------------
def _apply_mild_speedup(input_path: str, output_path: str, speed: float = MILD_SPEED) -> bool:
    """
    Apply mild speed increase to already-assembled video.
    speed=1.1 → 10% faster, pitch preserved via atempo.
    """
    vpts = round(1.0 / speed, 6)
    cmd  = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf",  f"setpts={vpts}*PTS",
        "-af",  f"atempo={speed}",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "256k",
        "-movflags", "+faststart",
        output_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        logger.error(f"Speedup failed:\n{r.stderr[-400:]}")
        return False
    logger.info(f"Applied {speed}x speedup: {os.path.basename(input_path)} → {os.path.basename(output_path)}")
    return True


# ---------------------------------------------------------------------------
# Pattern interrupt at t=3s
# ---------------------------------------------------------------------------
def _build_pattern_interrupt(video_clip, config: dict):
    try:
        import numpy as np
        from PIL import Image

        if not config.get("retention", {}).get("pattern_interrupt_enabled", True):
            return video_clip

        trigger_t  = config.get("retention", {}).get("pattern_interrupt_time", 3.0)
        zoom_peak  = 1.15
        ramp_dur   = 0.10
        hold_dur   = 0.15
        snap_dur   = 0.05
        effect_end = trigger_t + ramp_dur + hold_dur + snap_dur
        w, h       = video_clip.size

        def interrupt_effect(get_frame, t):
            frame = get_frame(t)
            if t < trigger_t or t > effect_end:
                return frame
            elapsed = t - trigger_t
            if elapsed <= ramp_dur:
                scale = 1.0 + (zoom_peak - 1.0) * (elapsed / ramp_dur)
            elif elapsed <= ramp_dur + hold_dur:
                scale = zoom_peak
            else:
                scale = zoom_peak - (zoom_peak - 1.0) * ((elapsed - ramp_dur - hold_dur) / snap_dur)
            scale = max(1.0, scale)
            img = Image.fromarray(frame).resize((int(w*scale), int(h*scale)), Image.LANCZOS)
            x1, y1 = (int(w*scale)-w)//2, (int(h*scale)-h)//2
            return np.array(img.crop((x1, y1, x1+w, y1+h)))

        return video_clip.fl(interrupt_effect, apply_to="video")
    except Exception as e:
        logger.warning(f"Pattern interrupt failed: {e}")
        return video_clip


# ---------------------------------------------------------------------------
# Hook overlay
# ---------------------------------------------------------------------------
def _build_hook_overlay(hook_text, config, video_width, video_height):
    try:
        from moviepy.editor import TextClip
        sub_cfg  = config.get("subtitles", {})
        duration = min(sub_cfg.get("hook_overlay_duration_seconds", 1.5), 1.5)
        fontsize = sub_cfg.get("hook_overlay_fontsize", 88)
        color    = sub_cfg.get("hook_overlay_color", "yellow")
        short    = " ".join(hook_text.split()[:10]).upper()
        return (
            TextClip(short, fontsize=fontsize, font="Impact",
                     color=color, stroke_color="black", stroke_width=4,
                     method="caption", size=(int(video_width * 0.90), None),
                     align="center")
            .set_start(0).set_duration(duration)
            .set_position(("center", int(video_height * 0.15)))
        )
    except Exception as e:
        logger.warning(f"Hook overlay failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Zoom pulse
# ---------------------------------------------------------------------------
def _apply_zoom_pulse(video_clip, config):
    try:
        import math, numpy as np
        from PIL import Image
        c_cfg    = config.get("clip", {})
        interval = c_cfg.get("zoom_pulse_interval_seconds", 4)
        amount   = c_cfg.get("zoom_pulse_scale", 1.03) - 1.0
        w, h     = video_clip.size

        def zoom_effect(get_frame, t):
            scale  = 1.0 + amount * abs(math.sin(math.pi * t / interval))
            frame  = get_frame(t)
            img    = Image.fromarray(frame)
            nw, nh = int(w * scale), int(h * scale)
            img    = img.resize((nw, nh), Image.LANCZOS)
            l, top = (nw-w)//2, (nh-h)//2
            return np.array(img.crop((l, top, l+w, top+h)))

        return video_clip.fl(zoom_effect, apply_to="video")
    except Exception as e:
        logger.warning(f"Zoom pulse failed: {e}")
        return video_clip


# ---------------------------------------------------------------------------
# Subtitle t=0 fix
# ---------------------------------------------------------------------------
def _fix_subtitle_start_times(subtitle_clips: list) -> list:
    if not subtitle_clips:
        return subtitle_clips
    try:
        earliest = min(c.start for c in subtitle_clips)
        if earliest <= 0.05:
            return subtitle_clips
        return [c.set_start(max(0.0, c.start - earliest)) for c in subtitle_clips]
    except Exception as e:
        logger.warning(f"Subtitle start fix failed: {e}")
        return subtitle_clips


# ---------------------------------------------------------------------------
# Main assembler
# ---------------------------------------------------------------------------
def assemble_video(
    clip_data: Dict,
    script_data: Dict,
    subtitle_data: Optional[Dict],
    config: dict,
    exports_dir: str = "exports",
    meme_data: Optional[Dict] = None,
    sfx_data: Optional[Dict] = None,
) -> Dict:
    from moviepy.editor import (
        VideoFileClip, AudioFileClip,
        CompositeVideoClip, CompositeAudioClip,
        concatenate_videoclips,
    )

    os.makedirs(exports_dir, exist_ok=True)

    version_id  = script_data["version_id"]
    clip_path   = clip_data.get("clip_path")
    audio_path  = script_data.get("audio_path")
    hook_text   = script_data.get("hook", "")
    out_w       = config["output"]["resolution_width"]
    out_h       = config["output"]["resolution_height"]
    fps         = config["output"]["fps"]
    max_dur     = config["output"].get("max_video_length", 60)  # safety ceiling only

    exports_dir  = _fix_path(exports_dir)
    raw_path     = f"{exports_dir}/{version_id}_raw.mp4"
    output_path  = f"{exports_dir}/{version_id}.mp4"
    temp_audio   = f"{exports_dir}/temp_audio_{version_id}.m4a"

    if clip_path:  clip_path  = _fix_path(clip_path)
    if audio_path: audio_path = _fix_path(audio_path)

    if not clip_path or not os.path.exists(clip_path):
        logger.error(f"Clip not found: {clip_path}")
        return {"version_id": version_id, "export_path": None, "duration": 0.0, "ok": False}
    if not audio_path or not os.path.exists(audio_path):
        logger.error(f"Audio not found: {audio_path}")
        return {"version_id": version_id, "export_path": None, "duration": 0.0, "ok": False}

    try:
        voiceover  = AudioFileClip(audio_path)
        actual_dur = round(voiceover.duration, 2)
        # Fix 4: video must cover the FULL audio — never shorter than audio
        # Subtitles are timed to full audio so video must match.
        # max_dur is only a sanity cap for truly runaway audio (>60s etc)
        clip_dur   = min(actual_dur, max_dur)
        voiceover  = voiceover.subclip(0, clip_dur)

        video = VideoFileClip(clip_path).resize((out_w, out_h))
        # Loop gameplay to fill the complete audio duration (not just 30s)
        if video.duration < clip_dur:
            loops = int(clip_dur / video.duration) + 2
            video = concatenate_videoclips([video] * loops)
        video = video.subclip(0, clip_dur)   # now exactly clip_dur = audio length

        video = _build_pattern_interrupt(video, config)
        video = _apply_zoom_pulse(video, config)

        # Audio mix
        sfx_clips = (sfx_data or {}).get("sfx_clips", [])
        if sfx_clips:
            try:
                mixed = CompositeAudioClip([voiceover] + sfx_clips).subclip(0, clip_dur)
                video = video.set_audio(mixed)
            except Exception as e:
                logger.warning(f"SFX mix failed: {e}")
                video = video.set_audio(voiceover)
        else:
            video = video.set_audio(voiceover)

        # Layers
        layers = [video]
        if subtitle_data and subtitle_data.get("subtitle_clips"):
            layers.extend(_fix_subtitle_start_times(subtitle_data["subtitle_clips"]))
        hook_clip = _build_hook_overlay(hook_text, config, out_w, out_h)
        if hook_clip:
            layers.append(hook_clip)
        meme_clips = (meme_data or {}).get("meme_clips", [])
        if meme_clips:
            layers.extend(meme_clips)

        final = CompositeVideoClip(layers, size=(out_w, out_h)).set_duration(clip_dur)

        # Write composite to raw path first
        bitrate = config["output"].get("video_bitrate", "12000k")
        final.write_videofile(
            raw_path, fps=fps,
            codec="libx264", audio_codec="aac",
            bitrate=bitrate,
            ffmpeg_params=["-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p"],
            temp_audiofile=temp_audio,
            remove_temp=True, verbose=False, logger=None,
        )
        video.close(); voiceover.close(); final.close()

        # ── Mild 1.1x speedup ────────────────────────────────────────────
        speed_ok = _apply_mild_speedup(raw_path, output_path, MILD_SPEED)
        if speed_ok:
            try:
                os.remove(raw_path)
            except Exception:
                pass
            final_dur = round(clip_dur / MILD_SPEED, 2)
            final_path = output_path
        else:
            # Speedup failed — use raw as final
            os.rename(raw_path, output_path)
            final_dur  = clip_dur
            final_path = output_path

        logger.info(
            f"Exported {version_id}: {final_path} "
            f"({actual_dur:.1f}s → {final_dur:.1f}s @ {MILD_SPEED}x)"
        )
        return {
            "version_id":  version_id,
            "export_path": final_path,
            "duration":    final_dur,        # ← correctly set now
            "speed":       MILD_SPEED if speed_ok else 1.0,
            "memes_used":  (meme_data or {}).get("memes_used", []),
            "sfx_used":    (sfx_data  or {}).get("sfx_used",   []),
            "ok":          True,
        }

    except Exception as e:
        logger.error(f"Assembly failed for {version_id}: {e}")
        # Clean up temp files
        for p in [raw_path, temp_audio]:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
        return {"version_id": version_id, "export_path": None,
                "duration": 0.0, "error": str(e), "ok": False}


def assemble_all_videos(
    clip_results, script_results, subtitle_results,
    config, exports_dir="exports",
    meme_results=None, sfx_results=None,
):
    clips_map = {c["version_id"]: c for c in clip_results}
    subs_map  = {s.get("version_id", ""): s for s in subtitle_results}
    meme_map  = {m.get("version_id", ""): m for m in (meme_results or [])}
    sfx_map   = {s.get("version_id", ""): s for s in (sfx_results  or [])}
    exports   = []
    for script in script_results:
        vid = script["version_id"]
        exports.append(assemble_video(
            clips_map.get(vid, {}), script,
            subs_map.get(vid), config, exports_dir,
            meme_data=meme_map.get(vid),
            sfx_data=sfx_map.get(vid),
        ))
    return exports