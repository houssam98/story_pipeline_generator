"""
Module: story_generator.py
===========================
Generates a complete 8-10 minute serialized teen story (love, dating,
relationships, heartbreak) and breaks it into per-chapter scripts that
each run ~45 seconds when voiced.

How it plugs into the existing pipeline
----------------------------------------
generate_full_story() returns a list of chapter dicts that each look
EXACTLY like the script dicts generate_scripts() produces in the
original pipeline.  main_story.py passes them straight into
generate_voiceovers(), extract_all_clips(), generate_subtitles() etc.
with ZERO changes to those modules.

Chapter word target
--------------------
45 seconds of natural speech ≈ 110-125 words (at ~2.6 wps).
Each chapter is a self-contained scene that ends on unresolved tension
(cliffhanger) to drive "Part 2 / Part 3 …" watch-through.

Story structure (10-13 chapters)
----------------------------------
Ch 01  HOOK          – Drop into peak drama in medias res.
Ch 02  SETUP         – Who she is, who he is, how they met.
Ch 03  SPARK         – The first moment everything felt different.
Ch 04  FIRST DATE    – What happened, why it mattered.
Ch 05  COMPLICATION  – Something starts to go wrong.
Ch 06  CONFRONTATION – She finds out / things blow up.
Ch 07  FALLOUT       – Aftermath. Crying in the car. Texts.
Ch 08  LOW POINT     – The worst moment. Alone.
Ch 09  TURN          – Something shifts. A new choice.
Ch 10  RESOLUTION    – What actually happened at the end.
Ch 11  REFLECTION    – What she learned. (optional)
Ch 12  EPILOGUE      – Where they are now. (optional)

Voice DNA  — "bestie telling you tea at 1am"
---------------------------------------------
- First person, female narrator, 16-17 yrs old
- Present-tense retelling: "so he walks up and he goes …"
- Specific details: real names, a school, a song, a date
- Short punchy sentences mixed with breathless run-ons
- Ends each chapter on maximum tension / open question
"""

import os
import re
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime

from ollama import Client

logger  = logging.getLogger(__name__)
_client = Client()


# ── Shared model caller ────────────────────────────────────────────────────

def _call(messages: List[Dict], model: str, max_tok: int = 800) -> Optional[str]:
    out = ""
    try:
        for part in _client.chat(model, messages=messages, stream=True):
            out += part["message"]["content"]
    except Exception as e:
        logger.warning(f"Ollama {model}: {e}")
        return None
    return out.strip() or None


def _openai(messages: List[Dict], max_tok: int = 800) -> Optional[str]:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    try:
        import openai
        r = openai.OpenAI(api_key=key).chat.completions.create(
            model="gpt-4o-mini", messages=messages,
            temperature=0.93, max_tokens=max_tok,
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI: {e}")
        return None


# ── Stage 1: Story Outline ─────────────────────────────────────────────────

OUTLINE_SYSTEM = """\
You are a master storyteller who writes viral serialized teen drama for TikTok.
Stories are real-feeling, emotionally charged, and structured for maximum "Part 2" engagement.

THEMES: first love, secret crush, cheating boyfriend, toxic relationship,
friend-to-lover, getting cheated on, jealous ex, love triangle, long-distance,
second chances, being ghosted, situationships, homecoming drama.

RULES:
- Characters feel real. Use common teen names (Emma, Zoe, Jake, Tyler, Liam, Madison, Ava, Ethan).
- Settings feel real: school hallway, someone's car, homecoming, Snapchat DMs, a party, the parking lot.
- The narrator is sympathetic but not perfect. The love interest is complex, not a cartoon villain.
- Every chapter must end on an unresolved tension that forces the viewer to watch the next part.
- Chapters 1-13. No fewer than 10, no more than 13.

Return ONLY valid JSON, no markdown, no explanation:
{
  "title": "dramatic 5-8 word story title",
  "narrator": "first name only (female)",
  "love_interest": "first name only",
  "best_friend": "first name only (optional)",
  "setting": "one sentence: school name, grade, city feel",
  "theme": "one of: first_love|cheating|friend_to_lover|toxic|jealousy|ghosted|second_chance|love_triangle",
  "chapters": [
    {
      "num": 1,
      "title": "short dramatic chapter title",
      "type": "hook|setup|spark|date|complication|confrontation|fallout|low_point|turn|resolution|reflection|epilogue",
      "scene": "one sentence: where are they, what just happened",
      "beats": ["event 1", "event 2", "event 3"],
      "cliffhanger": "one sentence of unresolved tension that ends this chapter",
      "emotion": "shock|hype|sadness|rage|cringe|neutral"
    }
  ]
}"""


def _generate_outline(concept: str, model: str) -> Optional[Dict]:
    msgs = [
        {"role": "system", "content": OUTLINE_SYSTEM},
        {"role": "user",   "content":
            f'Create a teen drama story outline for this concept: "{concept}"\n'
            f"10-13 chapters. Cliffhanger at the end of EVERY chapter.\n"
            f"Return ONLY the JSON."},
    ]
    for attempt in range(3):
        raw = _call(msgs, model, 2000) or _openai(msgs, 2000)
        if not raw:
            continue
        try:
            raw  = re.sub(r"```json|```", "", raw).strip()
            s, e = raw.find("{"), raw.rfind("}") + 1
            if s >= 0 and e > s:
                data = json.loads(raw[s:e])
                if "chapters" in data and len(data["chapters"]) >= 8:
                    logger.info(
                        f"Outline OK: '{data['title']}' "
                        f"— {len(data['chapters'])} chapters"
                    )
                    return data
        except Exception as ex:
            logger.warning(f"Outline parse attempt {attempt+1}: {ex}")
    return None


# ── Stage 2: Per-chapter script ────────────────────────────────────────────

CHAPTER_SYSTEM = """\
You write one chapter of a serialized teen drama story for TikTok.
The narrator is a teenage girl (16-17) talking to her phone camera like she's
telling her best friend the most insane thing that just happened.

VOICE:
- "So basically", "not gonna lie", "I literally", "and I'm like", "fr fr", "no cap"
- Mix short punchy sentences with long breathless run-ons (mirrors real storytelling)
- Present-tense retelling: "so he walks up to me and goes..."
- Drop specific details: what time, what song, what they texted, what they wore
- Emotions build sentence by sentence — never flat, never calm for long

TARGET: 110-125 words EXACTLY. This is ~45 seconds of spoken audio.

FORMAT: Return ONLY the narration text. No chapter number, no title, no labels.
Start speaking immediately. End on maximum unresolved tension."""


def _generate_chapter(
    outline: Dict,
    chapter: Dict,
    prev_summary: str,
    model: str,
) -> Optional[str]:
    narrator   = outline.get("narrator", "she")
    love_int   = outline.get("love_interest", "he")
    best_friend= outline.get("best_friend", "her best friend")
    setting    = outline.get("setting", "high school")
    ch_num     = chapter["num"]
    beats      = "\n".join(f"  - {b}" for b in chapter.get("beats", []))
    cliffhang  = chapter.get("cliffhanger", "")
    scene      = chapter.get("scene", "")

    context = f"""\
Story: "{outline['title']}"
Narrator: {narrator} (teen girl, 16-17)
Love interest: {love_int}
Best friend: {best_friend}
Setting: {setting}
Chapter {ch_num} — "{chapter['title']}" ({chapter['type']})
Scene: {scene}

Beats to cover:
{beats}

This chapter MUST end on this unresolved tension:
"{cliffhang}"

Previous chapter recap: {prev_summary or "This is the first chapter."}"""

    msgs = [
        {"role": "system",    "content": CHAPTER_SYSTEM},
        {"role": "user",      "content": context},
        {"role": "assistant", "content": ""},
        {"role": "user",      "content":
            "Write the chapter narration now. 110-125 words. "
            "Start immediately. End on peak tension. No labels."},
    ]

    best = None
    for attempt in range(3):
        raw = _call(msgs, model, 400) or _openai(msgs, 400)
        if not raw:
            continue
        raw = raw.strip()
        wc  = len(raw.split())
        if 90 <= wc <= 160:
            # Hard-trim if over 130 words at a sentence boundary
            if wc > 130:
                words     = raw.split()
                trimmed   = " ".join(words[:130])
                last_stop = max(trimmed.rfind("."), trimmed.rfind("!"), trimmed.rfind("?"))
                if last_stop > len(trimmed) * 0.7:
                    raw = trimmed[:last_stop + 1]
            logger.info(f"Ch{ch_num:02d}: {len(raw.split())}w ✓ (attempt {attempt+1})")
            return raw
        # Keep best-effort in case all attempts are off-count
        if best is None or abs(wc - 118) < abs(len(best.split()) - 118):
            best = raw
        logger.warning(f"Ch{ch_num:02d} attempt {attempt+1}: {wc}w (target 110-125)")

    return best  # return closest result even if not perfect


def _summarize(text: str, ch_num: int) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return f"Ch{ch_num:02d}: " + " ".join(sentences[:2])


# ── Public entry point ─────────────────────────────────────────────────────

def generate_full_story(concept: str, config: dict) -> Optional[List[Dict]]:
    """
    Generate a complete serialized story and return a list of chapter
    script-dicts in the EXACT format that the existing pipeline modules
    expect (same keys as generate_scripts() output).

    Returns None on total failure.
    """
    model = config["script"].get("ollama_model", "gpt-oss:120b-cloud")

    # ── Outline ─────────────────────────────────────────────────────────
    logger.info(f"Generating story outline for concept: '{concept}'")
    outline = _generate_outline(concept, model)
    if not outline:
        logger.error("Outline generation failed")
        return None

    chapters_meta = outline["chapters"]
    timestamp     = datetime.now().strftime("%Y%m%d_%H%M%S")
    prev_summary  = ""
    results       = []

    logger.info(f"Writing {len(chapters_meta)} chapter scripts…")

    for ch_meta in chapters_meta:
        ch_num = ch_meta["num"]
        script = _generate_chapter(outline, ch_meta, prev_summary, model)

        if not script:
            logger.warning(f"Ch{ch_num:02d}: generation failed — using placeholder")
            script = (
                f"And that's when everything changed. I couldn't process what was happening. "
                f"My phone was in my hand and I just stared at it. "
                f"I didn't know what to say. I didn't know what to do. "
                f"All I knew was that nothing was ever going to be the same again. "
                f"Stay for the next part. You are not ready."
            )

        wc         = len(script.split())
        version_id = f"part{ch_num:02d}_{timestamp}"
        prev_summary = _summarize(script, ch_num)

        results.append({
            # ── Keys expected by all downstream pipeline modules ──────────
            "version_id":                  version_id,
            "script":                      script,
            "hook":                        script.split(".")[0].strip() + ".",
            "word_count":                  wc,
            "estimated_duration_seconds":  round(wc / 2.6, 1),
            "intensity_level":             config["script"].get("intensity_level", 4),
            "backend":                     "ollama",
            "attempts":                    1,
            # ── Story-specific metadata ───────────────────────────────────
            "chapter_num":    ch_num,
            "chapter_title":  ch_meta["title"],
            "chapter_type":   ch_meta["type"],
            "emotion":        ch_meta.get("emotion", "neutral"),
            "cliffhanger":    ch_meta.get("cliffhanger", ""),
            "story_title":    outline["title"],
            "concept":        concept,
        })

    total_dur = sum(c["estimated_duration_seconds"] for c in results)
    logger.info(
        f"Story ready: '{outline['title']}' | "
        f"{len(results)} parts | ~{total_dur/60:.1f} min total"
    )
    return results


def save_story_scripts(chapters: List[Dict], output_dir: str = "scripts") -> str:
    """Save all chapter scripts as a single JSON file."""
    os.makedirs(output_dir, exist_ok=True)
    ts       = chapters[0]["version_id"].split("_", 1)[1] if chapters else datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"story_{ts}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(chapters, f, indent=2, ensure_ascii=False)
    logger.info(f"Story scripts saved → {filepath}")
    return filepath
