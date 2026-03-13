"""
Generate clickbait / hook text for thumbnails from video transcript.
Scans the transcript for the most engaging, controversial, or emotional phrase.
"""
import re

# Words/phrases that signal an interesting hook moment (Indonesian)
_HOOK_SIGNALS_ID = [
    # Surprise / shock
    "gak nyangka", "nggak nyangka", "ternyata", "serius", "beneran", "asli",
    "gila", "parah", "anjir", "waduh", "astaga",
    # Controversy / drama
    "gagap", "marah", "nangis", "berantem", "putus", "selingkuh", "bohong",
    "dihujat", "dibully", "toxic", "masalah", "skandal",
    # Strong emotion
    "sedih", "kecewa", "takut", "malu", "bangga", "bahagia", "sakit",
    "capek", "stress", "depresi", "trauma",
    # Revelation / confession
    "rahasia", "cerita", "pengakuan", "jujur", "sebenernya", "padahal",
    "tapi emang", "bukan gitu",
    # Questions that hook
    "kenapa", "gimana", "kok bisa", "masa",
    # Engagement bait
    "viral", "pertama kali", "belum pernah",
    "akhirnya", "terpaksa",
]

# Scoring weights
_QUESTION_BONUS = 3
_EXCLAIM_BONUS = 2
_HOOK_WORD_BONUS = 5
_SHORT_PENALTY = -2   # Too short = not interesting
_LONG_PENALTY = -1    # Too long = bad for thumbnail


def _score_sentence(sentence: str) -> int:
    """Score a sentence by how 'hook-worthy' it is."""
    s = sentence.strip().lower()
    if not s or len(s) < 5:
        return -10

    score = 0

    # Questions are naturally hook-worthy
    if "?" in sentence:
        score += _QUESTION_BONUS

    # Exclamations signal emotion
    if "!" in sentence:
        score += _EXCLAIM_BONUS

    # Check for hook signal words
    for signal in _HOOK_SIGNALS_ID:
        if signal in s:
            score += _HOOK_WORD_BONUS

    # Prefer medium-length sentences (good for thumbnails)
    word_count = len(s.split())
    if word_count < 3:
        score += _SHORT_PENALTY
    elif word_count > 10:
        score += _LONG_PENALTY

    # Bonus for sentences with strong personal statements
    if any(w in s.split() for w in ["gue", "gw", "saya", "aku", "gua"]):
        score += 1

    return score


def _extract_sentences_from_transcript(transcript: str) -> list[str]:
    """Split transcript into individual sentences/phrases."""
    parts = re.split(r'[.!?]+', transcript)
    result = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part.split()) > 12:
            sub = [s.strip() for s in part.split(",") if s.strip()]
            result.extend(sub)
        else:
            result.append(part)
    return result


def _extract_topic(transcript: str) -> str:
    """
    When no strong hook is found, extract the main topic/subject
    of the video from the first few sentences.
    Looks for names, proper nouns, or the subject being discussed.
    """
    sentences = _extract_sentences_from_transcript(transcript)
    if not sentences:
        return ""

    # Combine first 3 sentences — the intro usually names the topic
    intro = " ".join(sentences[:3]).upper()
    words = intro.split()

    # Look for patterns like "NGOBROL DENGAN X" or "KETEMU X"
    topic_triggers = ["DENGAN", "SAMA", "BARENG", "TENTANG", "SOAL"]
    for i, w in enumerate(words):
        if w in topic_triggers and i + 1 < len(words):
            # Grab the next 2-3 words as the topic
            topic_words = words[i+1:i+4]
            # Filter out filler words
            topic_words = [tw for tw in topic_words if tw not in
                          {"YA", "NIH", "SIH", "TUH", "YANG", "DAN", "SO", "INI", "ITU"}]
            if topic_words:
                return " ".join(topic_words)

    return ""


def _make_hook_punchy(sentence: str) -> str:
    """
    Clean up and shorten a hook sentence to be punchy.
    Remove filler words from start, keep the core message.
    """
    text = sentence.strip().upper()

    # Remove common filler prefixes
    filler_prefixes = [
        "TAPI ", "JADI ", "TERUS ", "NAH ", "YA ", "DAN ",
        "SOALNYA ", "MAKANYA ", "KAYAK ", "YANG ",
    ]
    for prefix in filler_prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):]

    words = text.split()
    # Cap at 6 words for thumbnail readability
    if len(words) > 6:
        words = words[:6]

    return " ".join(words)


def generate_hook_text(transcript: str, language: str = "id") -> str:
    """
    Find the most hook-worthy phrase from the transcript and
    return it as short, punchy thumbnail text.
    """
    if not transcript or not transcript.strip():
        return "MUST WATCH"

    sentences = _extract_sentences_from_transcript(transcript)
    if not sentences:
        return "MUST WATCH"

    # Score each sentence
    scored = [(s, _score_sentence(s)) for s in sentences]
    scored.sort(key=lambda x: x[1], reverse=True)

    best_sentence = scored[0][0]
    best_score = scored[0][1]

    # If no strong hook found (score <= 1), use the topic instead
    if best_score <= 1:
        topic = _extract_topic(transcript)
        if topic:
            hook = f"NGOBROL {topic}"
        else:
            # Fall back to first meaningful sentence
            hook = _make_hook_punchy(best_sentence)
    else:
        hook = _make_hook_punchy(best_sentence)

    # Add contextual emoji based on content
    hook_lower = hook.lower()
    if any(w in hook_lower for w in ["gagap", "marah", "berantem", "dihujat", "nangis"]):
        hook = f"{hook} !!"
    elif any(w in hook_lower for w in ["rahasia", "ternyata", "sebenernya", "padahal"]):
        hook = f"{hook} !?"
    elif any(w in hook_lower for w in ["gila", "parah", "viral"]):
        hook = f"{hook} !!"

    # Final length safety
    if len(hook) > 45:
        words = hook.split()
        hook = " ".join(words[:6])

    print(f"[hook] Best sentence (score={best_score}): {best_sentence}")
    print(f"[hook] Final hook text: {hook}")
    return hook
