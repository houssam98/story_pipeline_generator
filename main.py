"""
main.py — Roblox Rants Pipeline (with Meme + SFX Engine)
==========================================================
Stages:
  1. Script generation      (Ollama / OpenAI)
  2. Voiceover              (ElevenLabs / mock WAV)
  3. Gameplay clips         (synced to audio duration)
  4. Subtitles + Emotions   (emotion tags passed downstream)
  5. Meme injection         (context-aware image overlays)
  6. SFX injection          (context-aware sound effects)
  7. Video assembly         (all layers composited)
  8. Uniquification         (ffmpeg transforms + metadata wipe)
  9. Validation             (word count, audio, video duration checks)
"""

import os, sys, json, argparse, logging
from typing import List

# Pillow 10+ compatibility — MUST be before any moviepy import
try:
    from PIL import Image
    if not hasattr(Image, "ANTIALIAS"):
        Image.ANTIALIAS = Image.LANCZOS
except ImportError:
    pass

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")

from modules.script_generator    import generate_scripts, save_scripts
from modules.voiceover_generator import generate_voiceovers
from modules.gameplay_randomizer import extract_all_clips
from modules.subtitle_generator  import generate_subtitles
from modules.meme_engine         import inject_memes, reset_used_memes
from modules.sfx_engine          import inject_sfx, reset_used_sfx
from modules.video_assembler     import assemble_all_videos, get_audio_duration
from modules.video_uniquifier    import uniquify_all
from modules.validator           import run_validation
from modules.caption_generator   import generate_all_captions, save_captions
from modules.output_logger       import write_log, print_summary


def load_config(config_path="config.json") -> dict:
    if not os.path.exists(config_path):
        logger.error(f"Config not found: {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_pipeline(
    gameplay_path: str,
    concept: str,
    config: dict,
    num_variations: int,
    mock_audio: bool = False,
    skip_uniquify: bool = False,
) -> None:

    # Reset meme/SFX trackers for this run
    reset_used_memes()
    reset_used_sfx()

    assets_dir  = config.get("assets_dir", "assets")
    out_w       = config["output"]["resolution_width"]
    out_h       = config["output"]["resolution_height"]
    exports_dir = config["output"]["exports_folder"]

    # ── Stage 1: Scripts ──────────────────────────────────────────────────
    logger.info(f"Stage 1/9 — Generating {num_variations} scripts...")
    scripts = generate_scripts(concept, config, n=num_variations)
    save_scripts(scripts, output_dir="scripts")

    # ── Stage 2: Voiceovers ───────────────────────────────────────────────
    logger.info("Stage 2/9 — Generating voiceovers...")
    scripts = generate_voiceovers(scripts, config, audio_dir="audio", mock=mock_audio)

    # ── Stage 3: Gameplay Clips ───────────────────────────────────────────
    logger.info("Stage 3/9 — Extracting gameplay clips...")
    clips = extract_all_clips(gameplay_path, scripts, config, output_dir="gameplay")

    # ── Stage 4: Subtitles + Emotion Detection ───────────────────────────
    logger.info("Stage 4/9 — Generating subtitles + detecting emotions...")
    subtitles = []
    for script in scripts:
        audio_path = script.get("audio_path")
        duration   = (
            get_audio_duration(audio_path)
            if audio_path and os.path.exists(audio_path)
            else config["clip"]["max_length_seconds"]
        )
        subtitles.append(generate_subtitles(
            script_data    = script,
            audio_duration = duration,
            config         = config,
            video_width    = out_w,
            video_height   = out_h,
        ))

    # ── Stage 4b: Refine captions with real emotion data ───────────────────
    logger.info("Stage 4b/9 — Refining captions with detected emotions...")
    for i, script in enumerate(scripts):
        script["emotion_summary"] = subtitles[i].get("emotion_summary", {})
    scripts = generate_all_captions(scripts, config)
    save_captions(scripts, exports_dir)

    # ── Stage 5+6: Meme + SFX Injection (SYNCED) ───────────────────────────
    # Compute shared trigger timestamps ONCE per video — both engines use the
    # exact same inject_ts so meme image and sound effect fire simultaneously.
    logger.info("Stage 5/9 — Computing shared emotion triggers...")
    logger.info("Stage 6/9 — Injecting synced meme overlays + sound effects...")

    from modules.meme_engine import compute_inject_timestamps
    meme_results = []
    sfx_results  = []

    for i, script in enumerate(scripts):
        sub_data     = subtitles[i]
        emotion_data = sub_data.get("emotion_data", [])
        vid          = script["version_id"]

        audio_path = script.get("audio_path")
        video_dur  = (
            get_audio_duration(audio_path)
            if audio_path and os.path.exists(audio_path)
            else config["clip"]["max_length_seconds"]
        )

        max_memes   = config.get("memes", {}).get("max_memes_per_video", 3)
        display_dur = config.get("memes", {}).get("meme_display_duration", 1.5)

        # ── Compute triggers ONCE — shared by both engines ────────────────
        shared_triggers = compute_inject_timestamps(
            emotion_data, video_dur, display_dur, max_memes
        )
        logger.info(
            f"{vid}: {len(shared_triggers)} shared trigger(s) at "
            f"{[round(t['inject_ts'],2) for t in shared_triggers]}"
        )

        # ── Memes (using shared triggers) ─────────────────────────────────
        meme_result = inject_memes(
            emotion_data      = emotion_data,
            video_w           = out_w,
            video_h           = out_h,
            video_duration    = video_dur,
            config            = config,
            assets_dir        = assets_dir,
            selected_triggers = shared_triggers,
        )
        meme_result["version_id"] = vid
        meme_results.append(meme_result)

        # ── SFX (using exact same shared triggers) ────────────────────────
        sfx_result = inject_sfx(
            emotion_data      = emotion_data,
            video_duration    = video_dur,
            config            = config,
            assets_dir        = assets_dir,
            selected_triggers = shared_triggers,
        )
        sfx_result["version_id"] = vid
        sfx_results.append(sfx_result)

    # ── Stage 7: Assembly ─────────────────────────────────────────────────
    logger.info("Stage 7/9 — Assembling videos...")
    exports = assemble_all_videos(
        clips, scripts, subtitles, config, exports_dir,
        meme_results=meme_results,
        sfx_results=sfx_results,
    )

    # ── Stage 8: Uniquification ───────────────────────────────────────────
    final_results = exports
    if not skip_uniquify:
        logger.info("Stage 8/9 — Uniquifying (transforms + metadata wipe)...")
        final_dir     = os.path.join(exports_dir, "final")
        final_results = uniquify_all(exports, config, final_dir)
    else:
        logger.info("Stage 8/9 — Skipped uniquification")

    # ── Stage 9: Validation ───────────────────────────────────────────────
    logger.info("Stage 9/9 — Validating outputs...")
    validation = run_validation(scripts, exports, config)

    write_log(scripts, clips, subtitles, exports, config["output"]["log_file"])
    print_summary(final_results)

    passed = validation["passed"]
    total  = len(exports)
    print(f"  🔍 Validation: {passed}/{total} passed")
    if validation.get("regen_needed"):
        for r in validation["regen_needed"]:
            flags = [k.replace("regen_","") for k,v in r.items() if k.startswith("regen_") and v]
            print(f"     ⚠️  {r['version_id']} → regen: {', '.join(flags)}")

    print(f"\n  📁 Upload-ready: {os.path.join(exports_dir, 'final')}\n")


def run_batch_pipeline(gameplay_path, concept, config,
                       batch_size=20, mock_audio=False, skip_uniquify=False):
    logger.info(f"Batch mode: {batch_size} videos")
    chunk_size, produced = 5, 0
    while produced < batch_size:
        chunk = min(chunk_size, batch_size - produced)
        run_pipeline(gameplay_path, concept, config, chunk, mock_audio, skip_uniquify)
        produced += chunk


def parse_args():
    p = argparse.ArgumentParser(description="Roblox Rants TikTok Pipeline")
    p.add_argument("--gameplay",      required=True)
    p.add_argument("--concept",       required=True)
    p.add_argument("--variations",    type=int, default=None)
    p.add_argument("--config",        default="config.json")
    p.add_argument("--mock-audio",    action="store_true")
    p.add_argument("--batch",         action="store_true")
    p.add_argument("--skip-uniquify", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    args   = parse_args()
    if not os.path.exists(args.gameplay):
        logger.error(f"Gameplay file not found: {args.gameplay}")
        sys.exit(1)
    config = load_config(args.config)
    if args.variations:
        config["pipeline"]["num_variations"] = args.variations
    num_variations = config["pipeline"]["num_variations"]

    if args.batch:
        run_batch_pipeline(
            args.gameplay, args.concept, config,
            config["pipeline"].get("batch_size", 20),
            args.mock_audio, args.skip_uniquify,
        )
    else:
        run_pipeline(
            args.gameplay, args.concept, config,
            num_variations, args.mock_audio, args.skip_uniquify,
        )
