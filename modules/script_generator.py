"""
Module: script_generator.py
============================
Complete script architecture rewrite.

The old approach: give AI a structure + word count → AI ignores word count every time.
The new approach: give AI a FILLED TEMPLATE with exact sentence slots.
                  Each slot has a max word count enforced per sentence, not total.
                  AI fills slots — can't overrun because each slot is capped.

Script DNA (what makes viewers stay past 3 seconds):
  - Second 0-2:  CONFLICT ALREADY IN PROGRESS. No setup. No intro.
                 Viewer feels like they walked into a conversation mid-scream.
  - Second 2-5:  ONE detail that makes it personal and specific.
                 "3 weeks", "my best friend", "500 Robux" — numbers anchor reality.
  - Second 5-12: Escalation. Each sentence raises the stakes by one level.
                 Think: bad → worse → unbelievable.
  - Second 12-20: The single worst moment. ONE sentence. Spoken slowly.
                  This is the sentence the viewer came for.
  - Second 20-27: Emotional aftermath + comment bait question.
                  "Would you have done the same?" forces a mental answer → comment.

Sentence structure rules:
  - Every sentence: 4-8 words. Short = fast = addictive.
  - No "and", "but", "so", "because" connecting clauses. Period after every thought.
  - Verbs carry sentences: stole, lied, deleted, blocked, laughed, watched, said.
  - Numbers are mandatory: 3 days, 10,000 Robux, 6 hours, 2 years.
"""

import os
import json
import re
import random
import logging
from typing import List, Dict, Optional
from datetime import datetime

from ollama import Client

logger           = logging.getLogger(__name__)
_ollama_client   = Client()


# ---------------------------------------------------------------------------
# Model caller
# ---------------------------------------------------------------------------
def _call_model(messages: List[Dict], model: str) -> Optional[str]:
    response = ""
    try:
        for part in _ollama_client.chat(model, messages=messages, stream=True):
            response += part["message"]["content"]
    except Exception as e:
        logger.warning(f"Ollama [{model}]: {e}")
        return None
    return response.strip() or None


def _openai_fallback(messages: List[Dict]) -> Optional[str]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        import openai
        r = openai.OpenAI(api_key=api_key).chat.completions.create(
            model="gpt-4o-mini", messages=messages,
            temperature=0.92, max_tokens=400,
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI fallback: {e}")
        return None


def _estimate_seconds(text: str) -> float:
    return round(len(text.split()) / 2.75, 1)


# ---------------------------------------------------------------------------
# Hook generation — viral first-line formula
# ---------------------------------------------------------------------------
HOOK_SYSTEM = """You write the FIRST LINE of viral Roblox TikTok videos.
This single sentence must make someone stop scrolling in 1.5 seconds.

The formula that works:
  [WHO did it] + [WHAT they did] + [SPECIFIC number/detail] + [one word reaction]

The psychology: specificity = credibility = emotional investment.
"He stole Robux" → 0 reaction.
"He stole 10,000 Robux while I slept." → viewer thinks "how? why? what happened next?"

MANDATORY RULES — break any of these and the hook fails:
1. Past tense. Already happened. The viewer is arriving AFTER the explosion.
2. Open with the BETRAYER or the ACTION — never with "I".
   WRONG: "I got betrayed by my best friend"
   RIGHT: "My best friend of 2 years wiped my entire island. Gone."
3. One specific number or time reference. Always.
4. Last word must be a SINGLE devastation word: GONE. DELETED. NOTHING. BLOCKED. DONE. OVER. BETRAYED. LAUGHED.
5. 8-13 words MAXIMUM. Count them.
6. Zero filler: no "so", "basically", "literally", "honestly", "actually".

Return ONLY valid JSON array of strings. No markdown. No explanation."""


def generate_hooks_with_ai(concept: str, n: int, model: str) -> List[str]:
    messages = [
        {"role": "system", "content": HOOK_SYSTEM},
        {"role": "user",   "content":
            f"Concept: \"{concept}\"\n"
            f"Write {n} hooks. Each must use a DIFFERENT opening word and a DIFFERENT specific detail.\n"
            f"Vary the emotional angle: betrayal, humiliation, rage, devastation, disbelief.\n"
            f"Return ONLY a JSON array of {n} strings."
        },
    ]
    raw = _call_model(messages, model) or _openai_fallback(messages) or ""
    try:
        raw  = re.sub(r"```json|```", "", raw).strip()
        s, e = raw.find("["), raw.rfind("]") + 1
        if s >= 0 and e > s:
            hooks = json.loads(raw[s:e])
            banned = ("so ", "okay", "today", "let me", "you won't",
                      "i'm going", "in this", "i want", "have you")
            valid = [
                h for h in hooks
                if isinstance(h, str)
                and not h.lower().startswith(banned)
                and 6 <= len(h.split()) <= 15
            ]
            logger.info(f"Hooks: {len(valid)}/{len(hooks)} passed validation")
            return valid
    except Exception as ex:
        logger.warning(f"Hook parse failed: {ex}")
    return []


# ---------------------------------------------------------------------------
# Script generation — slot-based template (beats word count drift)
# ---------------------------------------------------------------------------
SCRIPT_SYSTEM = """You write 30-second TikTok voiceover scripts for a Roblox Rants channel.
You are a 15-year-old who just experienced something genuinely devastating in Roblox.
You are not performing — you are venting to your phone camera at 11pm.

VOICE RULES (non-negotiable):
- Short sentences. 4-8 words each. Full stop. No joining with "and/but/so".
- Real teenager language: "Not gonna lie", "I can't", "Bro", "Fr", "I'm done"
- Emotion builds sentence by sentence. Start at 7/10 anger. End at 10/10.
- ONE specific number per section minimum. Numbers make it real.
- Never say "I'm going to tell you" or "In this video" or "Like and subscribe".
- Never explain what Roblox is. Viewer already knows.

SCRIPT STRUCTURE — fill each section exactly:
[HOOK]     → The hook sentence given to you. Use it VERBATIM. Do not add to it.
[CONTEXT]  → 2 sentences max. Who. What. When. Numbers.
[ESCALATE] → 3 sentences. Each one worse than the last. Build dread.
[PEAK]     → 1 sentence. The single worst moment. This is why they watched.
[REACTION] → 2 sentences. Emotional aftermath. End with a question to viewers.

HARD WORD LIMITS (the AI will be penalized for exceeding these):
- HOOK:     already provided
- CONTEXT:  10-16 words total across both sentences  
- ESCALATE: 18-26 words total across three sentences
- PEAK:     6-10 words. One sentence only.
- REACTION: 10-16 words total. Must end with a "?" question.

TOTAL TARGET: 75-95 words including the hook.

OUTPUT FORMAT — return ONLY the 5 labeled sections, exactly like this:
[HOOK] <hook text>
[CONTEXT] <context text>
[ESCALATE] <escalation text>
[PEAK] <peak moment>
[REACTION] <reaction + question>

Nothing before [HOOK]. Nothing after [REACTION]. No other text."""


SCRIPT_EXAMPLES = """EXAMPLE OUTPUT (study this format):
[HOOK] My admin of 3 months wiped my entire city. 5,000 parts. GONE.
[CONTEXT] I built that city for 6 weeks. He had 1 minute of admin power.
[ESCALATE] He started with my spawn point. Then the houses. Then the entire downtown. I watched every single block disappear. He was laughing in voice chat the whole time.
[PEAK] He said "it was just a prank bro" and left the server.
[REACTION] I sat there for 20 minutes not moving. Have you ever lost something you can never get back?

Notice: hook is cold and specific. Context is fast. Escalation builds dread sentence by sentence. Peak is devastating and short. Reaction ends with a question."""


def _parse_sections(raw: str) -> Optional[Dict[str, str]]:
    """Extract the 5 labeled sections from model output."""
    sections = {}
    tags     = ["HOOK", "CONTEXT", "ESCALATE", "PEAK", "REACTION"]
    for i, tag in enumerate(tags):
        pattern     = rf"\[{tag}\](.*?)(?=\[{tags[i+1]}\]|\Z)" if i < len(tags)-1 else rf"\[{tag}\](.*)"
        match       = re.search(pattern, raw, re.DOTALL | re.IGNORECASE)
        if match:
            sections[tag] = match.group(1).strip()
    return sections if len(sections) == 5 else None


def _enforce_word_limits(sections: Dict[str, str]) -> Dict[str, str]:
    """Hard-trim each section to its word limit if over."""
    limits = {
        "CONTEXT":  16,
        "ESCALATE": 28,
        "PEAK":     10,
        "REACTION": 18,
    }
    cleaned = dict(sections)
    for key, limit in limits.items():
        if key in cleaned:
            words = cleaned[key].split()
            if len(words) > limit:
                # Trim at sentence boundary if possible
                trimmed = " ".join(words[:limit])
                # Try to end at a period
                last_period = max(trimmed.rfind("."), trimmed.rfind("!"), trimmed.rfind("?"))
                if last_period > len(trimmed) * 0.6:
                    trimmed = trimmed[:last_period + 1]
                cleaned[key] = trimmed
    return cleaned


def _assemble_script(sections: Dict[str, str]) -> str:
    """Combine sections into a single flowing script string."""
    return " ".join([
        sections["HOOK"],
        sections["CONTEXT"],
        sections["ESCALATE"],
        sections["PEAK"],
        sections["REACTION"],
    ])


def _single_script(concept: str, hook: str, config: dict,
                   model: str, version_id: str) -> Dict:
    max_retries = 3
    text = backend = None
    best_result = None

    messages = [
        {"role": "system",  "content": SCRIPT_SYSTEM},
        {"role": "user",    "content": SCRIPT_EXAMPLES},
        {"role": "assistant","content": "Understood. I will follow that exact format."},
        {"role": "user",    "content":
            f"Write a script for this concept: \"{concept}\"\n"
            f"Use this hook VERBATIM as [HOOK]: \"{hook}\"\n"
            f"Return the 5 sections in the exact format shown. Nothing else."
        },
    ]

    for attempt in range(max_retries):
        raw     = _call_model(messages, model)
        backend = f"ollama/{model}"

        if raw is None:
            logger.warning(f"{version_id} attempt {attempt+1}: Ollama None — trying OpenAI")
            raw     = _openai_fallback(messages)
            backend = "openai/gpt-4o-mini"

        if raw is None:
            logger.error(f"{version_id}: All backends failed attempt {attempt+1}")
            continue

        # Try to parse sections
        sections = _parse_sections(raw)

        if sections:
            # Force hook to be exactly the provided hook
            sections["HOOK"] = hook
            # Enforce per-section word limits
            sections = _enforce_word_limits(sections)
            text     = _assemble_script(sections)
            wc       = len(text.split())
            est      = _estimate_seconds(text)

            # Keep the best result even if slightly over
            if best_result is None or wc < best_result["word_count"]:
                best_result = {
                    "script":     text,
                    "word_count": wc,
                    "est_duration": est,
                    "backend":    backend,
                    "attempts":   attempt + 1,
                    "sections":   sections,
                }

            if 70 <= wc <= 100:
                logger.info(f"{version_id} OK attempt {attempt+1}: {wc}w ~{est}s [{backend}]")
                return best_result

            logger.warning(f"{version_id} retry {attempt+1}: {wc}w ~{est}s (target 70-100w)")
        else:
            # Fallback: model didn't use template — try to use raw text if it's reasonable
            raw_clean = raw.strip()
            wc        = len(raw_clean.split())
            if 60 <= wc <= 120:
                est = _estimate_seconds(raw_clean)
                logger.warning(f"{version_id} attempt {attempt+1}: no sections found, using raw ({wc}w)")
                if best_result is None:
                    best_result = {
                        "script": raw_clean, "word_count": wc,
                        "est_duration": est, "backend": backend, "attempts": attempt + 1,
                    }
            else:
                logger.warning(f"{version_id} attempt {attempt+1}: parse failed, raw={wc}w")

    if best_result:
        logger.warning(f"{version_id}: Best-effort {best_result['word_count']}w ~{best_result['est_duration']}s")
        return best_result

    # Hard fallback — guaranteed short
    fallback = (
        f"{hook} "
        "I built that for weeks. They had power for one day. "
        "Every single piece. Gone in 30 seconds. "
        "They laughed about it. "
        "I don't even know what to say. Have you ever had this happen to you?"
    )
    return {
        "script": fallback, "word_count": len(fallback.split()),
        "est_duration": _estimate_seconds(fallback), "backend": "fallback", "attempts": max_retries,
    }


def generate_scripts(concept: str, config: dict, n: int = None) -> List[Dict]:
    n     = n or config["pipeline"]["num_variations"]
    model = config["script"].get("ollama_model", "gpt-oss:120b-cloud")

    ai_hooks     = generate_hooks_with_ai(concept, n, model)
    config_hooks = config.get("hooks_bank", [])
    random.shuffle(config_hooks)
    hooks = (ai_hooks + config_hooks)[:n]
    while len(hooks) < n:
        hooks.append(
            f"My admin deleted {random.randint(2,8)} weeks of work. "
            f"{random.randint(1000,9999)} parts. GONE."
        )

    results, timestamp = [], datetime.now().strftime("%Y%m%d_%H%M%S")
    intensity          = config["script"].get("intensity_level", 3)

    for i, hook in enumerate(hooks):
        version_id = f"v{i+1:02d}_{timestamp}"
        result     = _single_script(concept, hook, config, model, version_id)
        results.append({
            "version_id":                 version_id,
            "hook":                       hook,
            "script":                     result["script"],
            "word_count":                 result["word_count"],
            "estimated_duration_seconds": result["est_duration"],
            "intensity_level":            intensity,
            "backend":                    result["backend"],
            "attempts":                   result["attempts"],
        })

    return results


def save_scripts(scripts: List[Dict], output_dir: str = "scripts") -> str:
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath  = os.path.join(output_dir, f"scripts_{timestamp}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(scripts, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(scripts)} scripts → {filepath}")
    return filepath