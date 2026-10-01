"""
Module: emotion_detector.py
============================
Rewritten for the Teen Story Pipeline.

Previous version used Roblox-specific keywords ("1 hp", "clutch", "admin abuse",
"scammer") — none of which appear in love/dating stories, causing the emotion
detector to return "neutral" for almost every sentence and SFX to never fire.

This version uses two parallel keyword banks:
  STORY_TRIGGERS  — romance/dating/teen drama (new, primary for story pipeline)
  GAME_TRIGGERS   — original Roblox keywords (kept so main.py still works)

Emotion → SFX folder mapping (new emotions added for story pipeline):
  shock      → assets/sfx/shock/         (gasp, vine boom, record scratch)
  hype       → assets/sfx/hype/          (air horn, sparkle, smooth transition)
  rage       → assets/sfx/rage/          (buzzer, angry buzz, table slam)
  sadness    → assets/sfx/sadness/       (aww, sad trombone, violin)
  cringe     → assets/sfx/cringe/        (bruh, oof, yikes)
  romantic   → assets/sfx/romantic/      (piano hit, heartbeat, notification, sparkle)
  heartbreak → assets/sfx/heartbreak/    (glass shatter, deep thud, sad piano)
  awkward    → assets/sfx/awkward/       (crickets, buzzer, trombone)
  crying     → assets/sfx/crying/        (sob, sniff, piano cry)
  tension    → assets/sfx/tension/       (suspense sting, heartbeat fast, dramatic hit)
"""

import re
import json
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


# ── Story / Teen Drama keyword bank ──────────────────────────────────────────

STORY_TRIGGERS = {
    "romantic": [
        # butterflies / first feelings
        "butterflies", "heart racing", "i like him", "i like her",
        "i have a crush", "so cute", "he smiled at me", "she smiled at me",
        "he texted me", "she texted me", "he asked me out", "she asked me out",
        "first kiss", "holding hands", "he looked at me", "she looked at me",
        "i couldn't stop smiling", "my heart", "i felt something",
        "he's perfect", "she's perfect", "i think i'm falling",
        "he noticed me", "she noticed me", "our song", "he remembered",
        "she remembered", "he showed up", "she showed up",
        "asked me to prom", "asked me to homecoming", "slow dance",
        "he told me he liked me", "she told me she liked me",
        "love you", "i love him", "i love her", "i fell for",
        # date / relationship
        "first date", "our date", "he took me", "she took me",
        "we were talking every night", "we became official",
    ],

    "heartbreak": [
        # breakup / betrayal
        "broke up", "he broke up", "she broke up", "we broke up",
        "he cheated", "she cheated", "cheating on me", "he was cheating",
        "she was cheating", "he lied", "she lied", "he was talking to",
        "she was talking to", "he kissed", "she kissed", "behind my back",
        "he blocked me", "she blocked me", "he ghosted", "she ghosted",
        "he stopped texting", "she stopped texting", "he left", "she left",
        "he moved on", "she moved on", "with someone else",
        "i found out", "i saw the texts", "i saw them together",
        "he chose her", "she chose him", "i wasn't enough",
        "he never cared", "she never cared", "it was never real",
        "he used me", "she used me", "i was just a backup",
        "he deleted me", "she deleted me", "he unfollowed me",
    ],

    "tension": [
        # confrontation / approaching drama
        "about to confront", "i confronted", "we need to talk",
        "he said we need to talk", "she said we need to talk",
        "something felt wrong", "something was off", "my stomach dropped",
        "i had a bad feeling", "i was shaking", "my hands were shaking",
        "i couldn't breathe", "my heart sank", "i felt sick",
        "i was scared", "i was terrified", "what if", "i don't know what to do",
        "he was acting different", "she was acting different",
        "he wasn't answering", "she wasn't answering",
        "he was online but", "she was online but",
        "the last text was", "he read it and", "she read it and",
        "i waited", "he never replied", "she never replied",
        "i saw his location", "i saw her location", "he was there",
    ],

    "shock": [
        # plot twist / reveal moments
        "i can't believe", "i couldn't believe", "no way",
        "wait what", "are you serious", "i was shaking",
        "my jaw dropped", "i froze", "i couldn't process",
        "that's when i found out", "that's when i saw",
        "turns out", "it turns out", "i never knew",
        "he told me the truth", "she told me the truth",
        "he admitted", "she admitted", "he confessed", "she confessed",
        "the truth was", "i found the texts", "i found out the truth",
        "she told me everything", "he told me everything",
        "i didn't know", "i had no idea", "i couldn't have known",
        "literally shaking", "i'm dead", "not real", "unbelievable",
    ],

    "sadness": [
        # crying / grief / loneliness
        "i cried", "i was crying", "i couldn't stop crying",
        "i cried myself to sleep", "i cried all night",
        "i was devastated", "i was heartbroken", "i felt empty",
        "i miss him", "i miss her", "i still miss",
        "i deleted everything", "i deleted his number", "i deleted her number",
        "i deleted our photos", "i couldn't look at",
        "alone in my room", "alone in my car", "i sat in my car",
        "i turned off my phone", "i didn't eat", "i couldn't sleep",
        "i lost my best friend", "my heart was broken",
        "nothing felt real", "everything reminded me of him",
        "everything reminded me of her", "it hurt so much",
        "so sad", "i'm sad", "it hurts", "i'm hurting",
    ],

    "cringe": [
        # embarrassing / awkward moments
        "so embarrassing", "i was so embarrassed", "everyone saw",
        "everyone was watching", "in front of everyone",
        "he laughed at me", "she laughed at me", "they were laughing",
        "i said the wrong thing", "i did the wrong thing",
        "autocorrect", "i sent it to the wrong person",
        "i accidentally", "i tripped", "i spilled",
        "he rejected me in front of", "she rejected me in front of",
        "the whole school knew", "it went around the school",
        "i wanted to disappear", "i wanted to die of embarrassment",
        "so cringe", "bruh moment", "awkward",
    ],

    "hype": [
        # positive / confident / glow-up moments
        "he came back", "she came back", "he apologized", "she apologized",
        "he finally admitted", "she finally admitted",
        "i moved on", "i was over it", "i was doing better",
        "i glowed up", "i stopped caring", "i deleted his number",
        "i met someone new", "i realized my worth",
        "i'm so over it", "and honestly", "not gonna lie i'm good",
        "we made up", "we got back together", "he chose me",
        "she chose me", "he came to my door", "she came to my door",
        "best day of my life", "honestly thriving",
        "let's go", "insane", "comeback",
    ],

    "awkward": [
        "so awkward", "awkward silence", "it was awkward",
        "he didn't say anything", "she didn't say anything",
        "the silence was", "nobody said anything",
        "i didn't know what to say", "he didn't know what to say",
        "she didn't know what to say", "we just stood there",
        "it got weird", "things got weird",
        "weird energy", "weird vibe", "off", "different",
        "crickets", "nobody responded",
    ],

    "crying": [
        # intense crying specific
        "sobbing", "i was sobbing", "ugly crying", "i couldn't stop",
        "tears wouldn't stop", "bawling", "i was bawling",
        "cried in the bathroom", "cried in my car",
        "called my mom crying", "called my best friend crying",
        "i broke down", "i completely broke down",
        "i lost it", "that's when i lost it",
    ],

    # ── Keep Roblox keywords so main.py still works ──────────────────────────
    "rage": [
        "toxic", "worst teammate", "worst player", "cheater", "hacker",
        "scammer", "unfair", "i hate", "ruined", "reported",
        "admin abuse", "literally trolling", "targeting me",
        # story rage additions
        "how could you", "how dare you", "i hate him", "i hate her",
        "he made me feel", "she made me feel", "that's not fair",
        "i was so angry", "i was furious", "i couldn't believe he",
        "i couldn't believe she",
    ],
}


# Original Roblox single-word fallbacks — kept intact
SINGLE_WORD_TRIGGERS = {
    "shock":      ["bro", "wait", "seriously", "actually", "omg", "literally"],
    "rage":       ["reported", "banned", "trolled", "griefed", "furious", "angry"],
    "hype":       ["won", "amazing", "perfect", "destroyed", "clutched", "finally"],
    "sadness":    ["cried", "hurt", "devastated", "gutted", "miss", "alone"],
    "cringe":     ["oof", "yikes", "cursed", "painful", "bruh", "awkward"],
    "romantic":   ["crush", "like", "love", "cute", "date", "kiss", "prom"],
    "heartbreak": ["cheated", "lied", "blocked", "ghosted", "left", "broke"],
    "tension":    ["shaking", "scared", "nervous", "sick", "dread", "fear"],
    "crying":     ["sobbing", "bawling", "tears", "crying", "broke"],
    "awkward":    ["silence", "weird", "different", "off", "strange"],
}


def _keyword_detect(sentence: str) -> str | None:
    lower = sentence.lower()
    # Multi-word phrases first (more specific)
    for emotion, triggers in STORY_TRIGGERS.items():
        for t in triggers:
            if t in lower:
                return emotion
    # Single-word fallbacks
    words = set(re.findall(r"\b\w+\b", lower))
    for emotion, kws in SINGLE_WORD_TRIGGERS.items():
        if words & set(kws):
            return emotion
    return None


# ── Ollama semantic detection ─────────────────────────────────────────────────

OLLAMA_SYSTEM = """\
You are an emotion classifier for short-form teen drama video content.
Classify the emotional tone of a sentence into exactly one of:
shock, hype, rage, sadness, cringe, romantic, heartbreak, tension, crying, awkward, neutral

Definitions:
- romantic   : love, crush, butterflies, first kiss, sweet/cute moments
- heartbreak : betrayal, cheating, breakup, ghosting, being left
- tension    : confrontation building, bad feeling, something about to go wrong
- crying     : intense crying, sobbing, breaking down
- awkward    : silence, weird energy, embarrassing moment
- shock      : unexpected reveal, disbelief, plot twist
- sadness    : grief, missing someone, loneliness, hurt
- rage       : anger, fury, unfairness, betrayal anger
- hype       : confidence, glow-up, moving on, good moment
- cringe     : embarrassing, awkward, self-conscious

Respond with ONLY the emotion word. Nothing else."""


def _ollama_detect(sentence: str, model: str) -> str:
    try:
        from ollama import Client
        response = ""
        for part in Client().chat(
            model,
            messages=[
                {"role": "system", "content": OLLAMA_SYSTEM},
                {"role": "user",   "content": f'Classify: "{sentence}"'},
            ],
            stream=True,
        ):
            response += part["message"]["content"]
        result = response.strip().lower().split()[0] if response.strip() else "neutral"
        valid  = {
            "shock", "hype", "rage", "sadness", "cringe", "neutral",
            "romantic", "heartbreak", "tension", "crying", "awkward",
        }
        return result if result in valid else "neutral"
    except Exception as e:
        logger.debug(f"Ollama emotion detect: {e}")
        return "neutral"


# ── Sentence splitter ─────────────────────────────────────────────────────────

def _split_sentences(text: str) -> List[str]:
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?…])\s+", text)
    result = []
    for s in sentences:
        for part in re.split(r"\.\.\.", s):
            if part.strip():
                result.append(part.strip())
    return result


# ── Main detection ────────────────────────────────────────────────────────────

def detect_emotions(script_text: str, model: str = "gpt-oss:120b-cloud") -> List[Dict]:
    """
    Detect emotions per sentence.
    Uses keyword matching first, then Ollama for ambiguous sentences.
    Returns list of dicts: sentence, emotion, timestamp, detection_method.
    """
    sentences = _split_sentences(script_text)
    pre_results, ambiguous_indices = [], []
    cursor = 0.0

    for sentence in sentences:
        if not sentence:
            continue
        wc      = len(sentence.split())
        emotion = _keyword_detect(sentence)
        pre_results.append({
            "sentence":          sentence,
            "emotion":           emotion or "neutral",
            "timestamp":         round(cursor, 2),
            "timestamp_is_real": False,
            "words":             wc,
            "detection_method":  "keyword" if emotion else "pending",
        })
        if emotion is None:
            ambiguous_indices.append(len(pre_results) - 1)
        cursor += wc / 2.6   # 2.6 wps for slower teen narration voice

    # Batch Ollama calls for ambiguous sentences
    if ambiguous_indices:
        logger.info(f"Sending {len(ambiguous_indices)} sentences to Ollama for emotion detection")
        for idx in ambiguous_indices:
            sentence = pre_results[idx]["sentence"]
            emotion  = _ollama_detect(sentence, model)
            pre_results[idx]["emotion"]          = emotion
            pre_results[idx]["detection_method"] = "ollama"

    counts    = {}
    kw_count  = ai_count = 0
    for r in pre_results:
        counts[r["emotion"]] = counts.get(r["emotion"], 0) + 1
        if r["detection_method"] == "keyword":
            kw_count += 1
        elif r["detection_method"] == "ollama":
            ai_count += 1

    logger.info(
        f"Emotions: {counts} [keyword={kw_count} ollama={ai_count}]"
    )
    return pre_results


# ── Real-timestamp alignment (unchanged) ─────────────────────────────────────

def align_emotions_to_subtitles(
    emotion_data: List[Dict],
    timings: List[Tuple[float, float, str]],
) -> List[Dict]:
    if not timings:
        return emotion_data
    updated = []
    for entry in emotion_data:
        if entry["emotion"] == "neutral":
            updated.append(entry)
            continue
        sentence_words = set(
            re.sub(r"[^\w]", "", w.lower()) for w in entry["sentence"].split()
        )
        best_ts, best_score = entry["timestamp"], 0
        for start, end, sub_text in timings:
            sub_words = set(re.sub(r"[^\w]", "", w.lower()) for w in sub_text.split())
            overlap   = len(sentence_words & sub_words)
            if overlap > best_score:
                best_score = overlap
                best_ts    = start
        e                      = entry.copy()
        e["timestamp"]         = round(best_ts, 3)
        e["timestamp_is_real"] = best_score > 0
        updated.append(e)
    real = sum(1 for e in updated if e.get("timestamp_is_real"))
    logger.info(f"Timestamp alignment: {real}/{len(updated)} matched")
    return updated
