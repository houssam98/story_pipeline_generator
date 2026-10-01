"""
Module: caption_generator.py
==============================
Generates a high-quality, series-optimized TikTok caption for each story part
and saves it as an INDIVIDUAL file: exports/captions/part01_caption.txt etc.

Caption anatomy (what makes a story series caption viral):
──────────────────────────────────────────────────────────
LINE 1  Part label          "Part 1 of 12 🧵"
LINE 2  Story title         "She Found Out He Was Texting Her Best Friend"
LINE 3  (blank)
LINE 4  Hook sentence       The single most dramatic line from this chapter
LINE 5  Teaser              What's unresolved / what's coming (no spoilers)
LINE 6  (blank)
LINE 7  CTA                 Context-aware call to action
LINE 8  (blank)
LINE 9  Hashtags            15-20 tags, mix of series + chapter-specific

Part 1 CTA:  "comment 'part 2' if you want to know what happens 🫶"
Mid-story:   "drop your prediction below 👇" or "wait for part X 😭"
Final part:  "share if this hit different 💔" or "tell me your reaction 👇"

Each file is named: exports/captions/part01_caption.txt
All parts also combined into: exports/captions/all_captions.txt
"""

import os
import re
import json
import logging
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


# ── Prompts ────────────────────────────────────────────────────────────────

SYSTEM = """\
You are a TikTok growth strategist who writes viral captions for serialized teen drama series.
Your captions are known for: maximum saves, floods of comments, and massive "Part 2" demand.
Always respond in JSON only. No preamble, no markdown, no explanation."""


TEMPLATE = """\
Write a TikTok caption for this chapter of a serialized teen story.

== STORY INFO ==
Story title:   {story_title}
Part:          {part_num} of {total_parts}
Chapter title: {chapter_title}
Chapter type:  {chapter_type}
Dominant emotion: {emotions}
Cliffhanger:   {cliffhanger}

== SCRIPT PREVIEW (first 300 chars) ==
{script_preview}

== RULES ==
- hook_line: the single most emotionally gripping sentence from this chapter (verbatim or paraphrased, max 130 chars)
- teaser: what's left unresolved — create FOMO without spoiling (max 100 chars)
- cta:
    Part 1  → "comment 'part 2' if you want to know what happens 🫶"
    Parts 2–(N-1) → prediction question OR cliffhanger reaction ask
    Final part → "share if this hit different 💔" or "tell me your reaction 👇"
- hashtags: 15 to 20 tags. Include:
    Always: storylime, storytime, teenromance, dramatiktok, relatable, fyp, foryou
    Emotion-based: add 3-4 based on dominant emotion
      romantic → lovestory, firstlove, crush, romance
      heartbreak → heartbroken, breakup, cheating, betrayal
      tension → drama, thattension, plottwist
      sadness → sadstory, emotional, crying
      shock → plottwist, omg, notexpecting
      cringe → cringe, awkward, embarrassing
    Chapter-specific: 2-3 more based on what happens in this chapter

Return ONLY this JSON (nothing else):
{{
  "hook_line": "...",
  "teaser": "...",
  "cta": "...",
  "hashtags": ["tag1", "tag2", ...]
}}"""


# ── AI caller ──────────────────────────────────────────────────────────────

def _call_ai(prompt: str, model: str) -> str | None:
    try:
        from ollama import Client
        response = ""
        for part in Client().chat(
            model,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            stream=True,
        ):
            response += part["message"]["content"]
        return response.strip() or None
    except Exception as e:
        logger.warning(f"Ollama caption: {e}")
    # OpenAI fallback
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        try:
            import openai
            r = openai.OpenAI(api_key=key).chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.9, max_tokens=500,
            )
            return r.choices[0].message.content.strip()
        except Exception as e2:
            logger.warning(f"OpenAI caption: {e2}")
    return None


def _parse(raw: str) -> dict | None:
    try:
        raw   = re.sub(r"```json|```", "", raw).strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            if "hook_line" in data and "hashtags" in data:
                return data
    except Exception as e:
        logger.warning(f"Caption parse: {e}")
    return None


# ── Fallback ───────────────────────────────────────────────────────────────

EMOTION_HASHTAGS = {
    "romantic":   ["lovestory", "firstlove", "crush", "romance"],
    "heartbreak": ["heartbroken", "breakup", "cheating", "betrayal"],
    "tension":    ["drama", "plottwist", "thattension"],
    "sadness":    ["sadstory", "emotional", "crying"],
    "shock":      ["plottwist", "omg", "cantbelieve"],
    "cringe":     ["cringe", "awkward", "embarrassing"],
    "crying":     ["crying", "emotional", "relatable"],
    "hype":       ["glowup", "movingon", "maincharacter"],
    "rage":       ["angry", "unfair", "howdare"],
    "awkward":    ["awkward", "silentmoment", "thetension"],
}

BASE_TAGS = [
    "storylime", "storytime", "teenromance", "dramatiktok",
    "relatable", "fyp", "foryou", "teendrama",
]


def _fallback(chapter: dict, total_parts: int) -> dict:
    part_num  = chapter.get("chapter_num", 1)
    emotions  = chapter.get("emotion_summary", {})
    dominant  = max(emotions, key=emotions.get) if emotions else "neutral"
    cliffhang = chapter.get("cliffhanger", "")
    hook      = chapter.get("script", "").split(".")[0][:130]

    if part_num == 1:
        cta = "comment 'part 2' if you want to know what happens 🫶"
    elif part_num >= total_parts:
        cta = "share if this hit different 💔"
    else:
        cta = "drop your prediction below 👇"

    tags = BASE_TAGS + EMOTION_HASHTAGS.get(dominant, [])

    return {
        "hook_line": hook,
        "teaser":    cliffhang[:100] if cliffhang else "you are NOT ready for what comes next.",
        "cta":       cta,
        "hashtags":  tags[:18],
    }


# ── Caption formatter ──────────────────────────────────────────────────────

def _format(data: dict, chapter: dict, total_parts: int) -> str:
    part_num    = chapter.get("chapter_num", 1)
    story_title = chapter.get("story_title", "her story")
    ch_title    = chapter.get("chapter_title", "")

    # Normalize hashtags — ensure # prefix, remove dupes
    seen, tags = set(), []
    for t in data.get("hashtags", []):
        clean = t.strip().lstrip("#").lower().replace(" ", "")
        if clean and clean not in seen:
            seen.add(clean)
            tags.append(f"#{clean}")

    # Part label with emoji that changes based on chapter type
    type_emoji = {
        "hook":         "🔥", "setup":       "👀", "spark":        "✨",
        "date":         "💫", "complication":"😬", "confrontation":"😤",
        "fallout":      "💔", "low_point":   "😭", "turn":         "🌅",
        "resolution":   "🫶", "reflection":  "💭", "epilogue":     "🎬",
    }
    emoji = type_emoji.get(chapter.get("chapter_type", ""), "🧵")

    lines = [
        f"Part {part_num} of {total_parts} {emoji}",
        f"",
        f"🎬 {story_title}",
        f"",
        data.get("hook_line", "").strip(),
        f"",
        data.get("teaser", "").strip(),
        f"",
        f"👇 {data.get('cta', '').strip()}",
        f"",
        " ".join(tags),
    ]
    return "\n".join(lines)


# ── Per-part file saver ────────────────────────────────────────────────────

def _save_individual(chapter: dict, caption_text: str, output_dir: str) -> str:
    """Save one caption as its own file: part01_caption.txt"""
    part_num = chapter.get("chapter_num", 1)
    vid      = chapter.get("version_id", f"part{part_num:02d}")
    filename = f"part{part_num:02d}_caption.txt"
    filepath = os.path.join(output_dir, filename)

    story_title = chapter.get("story_title", "")
    ch_title    = chapter.get("chapter_title", "")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"{'─'*50}\n")
        f.write(f"  📖 {story_title}\n")
        f.write(f"  Part {part_num} — {ch_title}\n")
        f.write(f"  Video file: {vid}.mp4\n")
        f.write(f"{'─'*50}\n\n")
        f.write(caption_text)
        f.write("\n")

    return filepath


# ── Public API ─────────────────────────────────────────────────────────────

def generate_caption(script_data: dict, config: dict, total_parts: int = 1) -> dict:
    """Generate a caption for one chapter. Returns updated script_data."""
    model       = config.get("script", {}).get("ollama_model", "gpt-oss:120b-cloud")
    part_num    = script_data.get("chapter_num", 1)
    story_title = script_data.get("story_title", "her story")
    ch_title    = script_data.get("chapter_title", "")
    ch_type     = script_data.get("chapter_type", "")
    cliffhang   = script_data.get("cliffhanger", "")
    emotions    = script_data.get("emotion_summary", {})
    script_text = script_data.get("script", "")

    # Strip part-label injection from hook before using in caption
    hook = script_data.get("hook", "")
    hook = re.sub(r"\[Part \d+ of \d+\]\s*", "", hook).strip()

    dominant_emotion = (
        max(emotions, key=emotions.get) if emotions else "neutral"
    )
    script_preview = script_text[:300].rsplit(" ", 1)[0] + "..."

    prompt = TEMPLATE.format(
        story_title   = story_title,
        part_num      = part_num,
        total_parts   = total_parts,
        chapter_title = ch_title,
        chapter_type  = ch_type,
        emotions      = dominant_emotion,
        cliffhanger   = cliffhang[:120] if cliffhang else "unknown",
        script_preview= script_preview,
    )

    raw    = _call_ai(prompt, model)
    parsed = _parse(raw) if raw else None

    if not parsed:
        logger.warning(f"Caption AI failed for {script_data['version_id']} — using fallback")
        parsed = _fallback(script_data, total_parts)

    caption_full = _format(parsed, script_data, total_parts)

    script_data["caption"]      = parsed.get("hook_line", "")
    script_data["teaser"]       = parsed.get("teaser", "")
    script_data["hashtags"]     = parsed.get("hashtags", [])
    script_data["cta"]          = parsed.get("cta", "")
    script_data["caption_full"] = caption_full

    logger.info(
        f"Caption Part {part_num}: \"{parsed.get('hook_line','')[:55]}...\""
    )
    return script_data


def generate_all_captions(scripts: List[Dict], config: dict) -> List[Dict]:
    total = len(scripts)
    return [generate_caption(s, config, total_parts=total) for s in scripts]


def save_captions(scripts: List[Dict], output_dir: str = "exports") -> str:
    """
    Save captions:
      1. Individual file per part: exports/captions/part01_caption.txt
      2. Combined file:            exports/captions/all_captions.txt
    Returns path to combined file.
    """
    captions_dir = os.path.join(output_dir, "captions")
    os.makedirs(captions_dir, exist_ok=True)

    individual_paths = []
    for script in scripts:
        caption_text = script.get("caption_full", "No caption generated.")
        path = _save_individual(script, caption_text, captions_dir)
        individual_paths.append(path)

    # Combined file
    ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
    combined    = os.path.join(captions_dir, f"all_captions_{ts}.txt")
    story_title = scripts[0].get("story_title", "Story") if scripts else "Story"
    total       = len(scripts)

    with open(combined, "w", encoding="utf-8") as f:
        f.write(f"{'═'*55}\n")
        f.write(f"  📖 {story_title}\n")
        f.write(f"  {total} parts — generated {ts}\n")
        f.write(f"  Individual files: exports/captions/part01_caption.txt … part{total:02d}_caption.txt\n")
        f.write(f"{'═'*55}\n\n")

        for i, (script, path) in enumerate(zip(scripts, individual_paths)):
            part_num = script.get("chapter_num", i + 1)
            ch_title = script.get("chapter_title", "")
            caption  = script.get("caption_full", "")
            f.write(f"\n{'─'*55}\n")
            f.write(f"  Part {part_num:02d} — {ch_title}\n")
            f.write(f"{'─'*55}\n\n")
            f.write(caption + "\n")

    logger.info(
        f"Captions saved:\n"
        f"  Individual: {captions_dir}/part01_caption.txt … part{total:02d}_caption.txt\n"
        f"  Combined:   {combined}"
    )
    return combined
