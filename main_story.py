"""
main_story.py — Story Pipeline
=====================================
Generates a complete 8-10 minute serialized drama story split into
45-second TikTok clips (Part 1, Part 2 … Part N).

HOW IT WORKS
-------------
1. story_generator.py  → writes a full story as N chapter scripts
                          each ~110-125 words (~45s voiced)
2. All remaining stages (voiceover, gameplay clips, subtitles, meme/SFX
   injection, assembly, uniquification, validation, captions) run on
   EACH CHAPTER using the EXISTING pipeline modules unchanged.
3. Exports folder contains:  part01_<ts>.mp4 … partN_<ts>.mp4
   plus captions_<ts>.txt with Part 1 / Part 2 … captions.

USAGE
------
  python main_story.py --gameplay path/to/video.mp4 --concept "he made the worst mistake in his file"
  python main_story.py --gameplay video.mp4 --concept "my dead friend came back from his death"
  python main_story.py --gameplay video.mp4 --concept "wa baraka wa barakaaaaaaa" --mock-audio
  python main_story.py --gameplay video.mp4 --concept "wa hassan" --skip-uniquify

OPTIONS
-------
  --gameplay        Path to background gameplay/footage video (required)
  --concept         Story concept in plain English (required)
  --config          Config file path (default: config_story.json)
  --mock-audio      Use silent WAV instead of ElevenLabs (for testing)
  --skip-uniquify   Skip the ffmpeg uniquification pass (faster for testing)
"""

import os
import sys
import json
import argparse
import logging
from typing import List

# Pillow 10+ compat — must be before any moviepy import
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
        logging.FileHandler("logs/story_pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main_story")

# ── Import all pipeline modules (unchanged from original) ──────────────────
from modules.story_generator     import generate_full_story, save_story_scripts
from modules.voiceover_generator import generate_voiceovers
from modules.gameplay_randomizer import extract_all_clips
from modules.subtitle_generator  import generate_subtitles
from modules.meme_engine         import inject_memes, reset_used_memes, compute_inject_timestamps
from modules.sfx_engine          import inject_sfx, reset_used_sfx
from modules.video_assembler     import assemble_all_videos, get_audio_duration
from modules.video_uniquifier    import uniquify_all
from modules.validator           import run_validation
from modules.caption_generator   import generate_all_captions, save_captions
from modules.output_logger       import write_log, print_summary


# ── Config ─────────────────────────────────────────────────────────────────

def load_config(path: str) -> dict:
    # Prefer config_story.json, fall back to config.json
    candidates = [path, "config_story.json", "config.json"]
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            logger.info(f"Loaded config: {p}")
            return cfg
    logger.error(f"No config file found. Tried: {candidates}")
    sys.exit(1)


# ── Pipeline ────────────────────────────────────────────────────────────────

def run_story_pipeline(
    gameplay_path: str,
    concept: str,
    config: dict,
    mock_audio: bool = False,
    skip_uniquify: bool = False,
) -> None:

    reset_used_memes()
    reset_used_sfx()

    assets_dir  = config.get("assets_dir", "assets")
    out_w       = config["output"]["resolution_width"]
    out_h       = config["output"]["resolution_height"]
    exports_dir = config["output"]["exports_folder"]

    # ── Stage 1: Generate full story as chapter scripts ───────────────────
    logger.info("=" * 55)
    logger.info(f"Stage 1 — Generating story for concept: '{concept}'")
    chapters = generate_full_story(concept, config)
    if not chapters:
        logger.error("Story generation failed — aborting.")
        sys.exit(1)

    logger.info(f"  → {len(chapters)} chapters | ~{sum(c['estimated_duration_seconds'] for c in chapters)/60:.1f} min")
    save_story_scripts(chapters, output_dir="scripts")

    # ── Stage 2: Voiceovers ───────────────────────────────────────────────
    logger.info("Stage 2 — Generating voiceovers…")
    chapters = generate_voiceovers(chapters, config, audio_dir="audio", mock=mock_audio)

    # ── Stage 3: Gameplay clips ───────────────────────────────────────────
    logger.info("Stage 3 — Extracting gameplay clips…")
    clips = extract_all_clips(gameplay_path, chapters, config, output_dir="gameplay")

    # ── Stage 4: Subtitles + emotions ────────────────────────────────────
    logger.info("Stage 4 — Generating subtitles + detecting emotions…")
    subtitles = []
    for ch in chapters:
        audio_path = ch.get("audio_path")
        duration   = (
            get_audio_duration(audio_path)
            if audio_path and os.path.exists(audio_path)
            else config["clip"]["max_length_seconds"]
        )
        subtitles.append(generate_subtitles(
            script_data    = ch,
            audio_duration = duration,
            config         = config,
            video_width    = out_w,
            video_height   = out_h,
        ))

    # ── Stage 4b: TikTok captions (Part 1 / Part 2 aware) ────────────────
    logger.info("Stage 4b — Generating TikTok captions…")
    for i, ch in enumerate(chapters):
        ch["emotion_summary"] = subtitles[i].get("emotion_summary", {})
    chapters = _add_part_labels(chapters)          # inject "Part 1 of N" context
    chapters = generate_all_captions(chapters, config)
    save_captions(chapters, exports_dir)

    # ── Stage 5+6: Synced meme + SFX injection ───────────────────────────
    logger.info("Stage 5/6 — Synced meme + SFX injection…")
    meme_results, sfx_results = [], []

    for i, ch in enumerate(chapters):
        sub_data     = subtitles[i]
        emotion_data = sub_data.get("emotion_data", [])
        vid          = ch["version_id"]

        audio_path = ch.get("audio_path")
        video_dur  = (
            get_audio_duration(audio_path)
            if audio_path and os.path.exists(audio_path)
            else config["clip"]["max_length_seconds"]
        )

        max_memes   = config.get("memes", {}).get("max_memes_per_video", 2)
        display_dur = config.get("memes", {}).get("meme_display_duration", 1.5)

        shared_triggers = compute_inject_timestamps(
            emotion_data, video_dur, display_dur, max_memes
        )

        meme_result = inject_memes(
            emotion_data=emotion_data, video_w=out_w, video_h=out_h,
            video_duration=video_dur, config=config,
            assets_dir=assets_dir, selected_triggers=shared_triggers,
        )
        meme_result["version_id"] = vid
        meme_results.append(meme_result)

        sfx_result = inject_sfx(
            emotion_data=emotion_data, video_duration=video_dur,
            config=config, assets_dir=assets_dir,
            selected_triggers=shared_triggers,
        )
        sfx_result["version_id"] = vid
        sfx_results.append(sfx_result)

    # ── Stage 7: Video assembly ───────────────────────────────────────────
    logger.info("Stage 7 — Assembling videos…")
    exports = assemble_all_videos(
        clips, chapters, subtitles, config, exports_dir,
        meme_results=meme_results,
        sfx_results=sfx_results,
    )

    # ── Stage 8: Uniquification ───────────────────────────────────────────
    final_results = exports
    if not skip_uniquify:
        logger.info("Stage 8 — Uniquifying…")
        final_dir     = os.path.join(exports_dir, "final")
        final_results = uniquify_all(exports, config, final_dir)
    else:
        logger.info("Stage 8 — Skipped uniquification")

    # ── Stage 9: Validation ───────────────────────────────────────────────
    logger.info("Stage 9 — Validating…")
    validation = run_validation(chapters, exports, config)

    write_log(chapters, clips, subtitles, exports, config["output"]["log_file"])
    print_summary(final_results)

    passed = validation["passed"]
    total  = len(exports)
    print(f"\n  🔍 Validation: {passed}/{total} parts passed")
    if validation.get("regen_needed"):
        for r in validation["regen_needed"]:
            flags = [k.replace("regen_", "") for k, v in r.items() if k.startswith("regen_") and v]
            print(f"     ⚠️  {r['version_id']} → regen: {', '.join(flags)}")

    _print_story_summary(chapters, final_results)
    print(f"\n  📁 Upload-ready parts: {os.path.join(exports_dir, 'final')}\n")


# ── Helpers ─────────────────────────────────────────────────────────────────

def _add_part_labels(chapters: List[dict]) -> List[dict]:
    """
    Inject Part X of Y context into each chapter's hook field so the
    caption generator can produce "Part 1 of 12" style captions.
    """
    total = len(chapters)
    for ch in chapters:
        num    = ch.get("chapter_num", 1)
        prefix = f"Part {num} of {total}"
        ch["part_label"] = prefix
        # Caption generator uses 'hook' for its prompt — prepend part label
        ch["hook"] = f"[{prefix}] " + ch.get("hook", "")
    return chapters


def _print_story_summary(chapters: List[dict], exports: List[dict]) -> None:
    story_title = chapters[0].get("story_title", "Story") if chapters else "Story"
    ok_exports  = [e for e in exports if e.get("ok")]
    total_dur   = sum(e.get("duration", 0) for e in ok_exports)

    print("\n" + "=" * 55)
    print(f"  📖  {story_title}")
    print(f"  🎬  {len(ok_exports)} parts  |  ~{total_dur/60:.1f} min total")
    print("=" * 55)
    for ch in chapters:
        vid  = ch["version_id"]
        exp  = next((e for e in exports if e.get("version_id") == vid), {})
        dur  = exp.get("duration", 0)
        ok   = "✅" if exp.get("ok") else "❌"
        print(f"  {ok}  Part {ch['chapter_num']:02d} — {ch['chapter_title'][:40]:<40} {dur:.1f}s")
    print("=" * 55)


# ── CLI ─────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description=" Story TikTok Pipeline")
    p.add_argument("--gameplay",      required=True,  help="Background video file")
    p.add_argument("--concept",       required=True,  help="Story concept in plain English")
    p.add_argument("--config",        default="config_story.json")
    p.add_argument("--mock-audio",    action="store_true", help="Silent WAV (no ElevenLabs)")
    p.add_argument("--skip-uniquify", action="store_true", help="Skip uniquification pass")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if not os.path.exists(args.gameplay):
        logger.error(f"Gameplay file not found: {args.gameplay}")
        sys.exit(1)

    config = load_config(args.config)
    run_story_pipeline(
        gameplay_path = args.gameplay,
        concept       = args.concept,
        config        = config,
        mock_audio    = args.mock_audio,
        skip_uniquify = args.skip_uniquify,
    )
