"""
Module: voiceover_generator.py
30-second pipeline. Returns actual audio duration.
If audio exceeds max_duration, nudges speed up to max_speed_override.
"""

import os, wave, struct, random, logging
from typing import Dict, List

logger = logging.getLogger(__name__)

ELEVENLABS_VOICE_MAP = {
    "rachel": "21m00Tcm4TlvDq8ikWAM", "adam":   "pNInz6obpgDQGcFmaJgB",
    "bella":  "EXAVITQu4vr4xnSDxMaL", "josh":   "TxGEqnHWrfWFTfGW9XjX",
    "elli":   "MF3mGyEYCl7XYWbV9V6O", "sam":    "yoZ06aMxZJJ28mfd3POQ",
    "nicole": "piTKgcLEGmPE4e6mEKli", "arnold": "VR6AewLTigWG4xSOukaG",
}


def get_audio_duration_seconds(path: str) -> float:
    """Return duration of any audio file via moviepy."""
    try:
        from moviepy.editor import AudioFileClip
        with AudioFileClip(path) as a:
            return round(a.duration, 2)
    except Exception as e:
        logger.warning(f"Could not read duration of {path}: {e}")
        return 0.0


def _mock_generate_audio(text, voice_id, speed, output_path):
    """Valid silent WAV sized to estimated speech duration."""
    try:
        import math
        word_count   = max(1, len(text.split()))
        duration_sec = max(5.0, word_count / (2.75 * speed))
        sample_rate  = 44100
        num_frames   = int(sample_rate * duration_sec)
        wav_path     = os.path.splitext(output_path)[0] + ".wav"
        with wave.open(wav_path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(struct.pack("<" + "h" * num_frames, *([0] * num_frames)))
        logger.warning(f"MOCK WAV ({duration_sec:.1f}s): {wav_path}")
        return wav_path
    except Exception as e:
        logger.error(f"Mock audio failed: {e}")
        return ""


def _elevenlabs_generate_audio(text, voice_id, speed, output_path, api_key):
    print(f"\napi key : {api_key}")
    try:
        import requests
        url     = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": api_key}
        payload = {
            "text": text,
            "model_id": "eleven_turbo_v2",
            "voice_settings": {
                "stability":        round(random.uniform(0.30, 0.55), 2),
                "similarity_boost": round(random.uniform(0.70, 0.90), 2),
                "style": 0.4, "use_speaker_boost": True,
            },
        }
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(r.content)
        logger.info(f"ElevenLabs audio: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"ElevenLabs error: {e}")
        return ""


def generate_voiceovers(scripts, config, audio_dir="audio", mock=False):
    """
    Generate voiceover for each script.
    If actual audio > max_duration_seconds, re-generates with increased speed.
    Adds 'audio_path', 'audio_duration', 'voice_name' to each script dict.
    """
    os.makedirs(audio_dir, exist_ok=True)

    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key and not mock:
        logger.warning("ELEVENLABS_API_KEY not set — switching to mock audio.")
        mock = True

    vo_cfg        = config["voiceover"]
    voice_names   = vo_cfg.get("voice_ids", list(ELEVENLABS_VOICE_MAP.keys()))
    speed_min     = vo_cfg.get("speed_min", 0.97)
    speed_max     = vo_cfg.get("speed_max", 1.03)
    max_speed     = vo_cfg.get("max_speed_override", 1.08)
    max_duration  = vo_cfg.get("max_duration_seconds", 35)
    output_fmt    = "wav" if mock else vo_cfg.get("output_format", "mp3")

    available = voice_names.copy()
    random.shuffle(available)
    updated = []

    for idx, script in enumerate(scripts):
        vid        = script["version_id"]
        voice_name = available[idx % len(available)]
        voice_id   = ELEVENLABS_VOICE_MAP.get(voice_name, voice_name)
        speed      = round(random.uniform(speed_min, speed_max), 3)
        out_path   = os.path.join(audio_dir, f"{vid}.{output_fmt}")

        actual_path = ""
        audio_duration = 0.0

        # First attempt
        if mock:
            actual_path = _mock_generate_audio(script["script"], voice_id, speed, out_path)
        else:
            actual_path = _elevenlabs_generate_audio(script["script"], voice_id, speed, out_path, api_key)

        if actual_path:
            audio_duration = get_audio_duration_seconds(actual_path)

            # If too long, nudge speed and regenerate (real API only)
            if audio_duration > max_duration and not mock:
                nudge_speed = min(max_speed, round(speed * (audio_duration / max_duration), 3))
                logger.warning(
                    f"{vid}: audio {audio_duration:.1f}s > {max_duration}s limit. "
                    f"Re-generating at speed {nudge_speed}x..."
                )
                # ElevenLabs doesn't have a speed param directly — we use ffmpeg to time-stretch
                stretched = _stretch_audio(actual_path, nudge_speed)
                if stretched:
                    actual_path    = stretched
                    audio_duration = get_audio_duration_seconds(actual_path)

        s = script.copy()
        s.update({
            "voice_name":     voice_name,
            "voice_id":       voice_id,
            "speed":          speed,
            "audio_path":     actual_path or None,
            "audio_duration": audio_duration,
            "audio_ok":       bool(actual_path),
        })
        updated.append(s)

    return updated


def _stretch_audio(input_path: str, speed: float) -> str:
    """Use ffmpeg atempo filter to speed up audio. Returns new path."""
    try:
        import subprocess
        out_path = input_path.replace(".mp3", f"_x{speed}.mp3")
        # atempo accepts 0.5–2.0; chain filters for values outside range
        atempo = f"atempo={min(2.0, speed)}"
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter:a", atempo,
            "-b:a", "128k", out_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return out_path
    except Exception as e:
        logger.error(f"Audio stretch failed: {e}")
        return ""