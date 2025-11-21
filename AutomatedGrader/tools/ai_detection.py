from typing import Dict, Any
import math
import re
from collections import Counter
import os


def _entropy(tokens):
    counts = Counter(tokens)
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return -sum((c / total) * math.log(c / total + 1e-12) for c in counts.values())


def detect_ai_generated(text: str) -> Dict[str, Any]:
    """Heuristic detection of AI-generated text.

    WARNING: This is a simple heuristic classifier, NOT a production-grade ML model.
    False positives are common for formulaic writing (reports, legal docs, etc.).
    
    Signals considered:
    - Token entropy (lower can indicate uniform phrasing)
    - Sentence length variance (very uniform lengths can indicate AI)
    - Repetitive phrases and n-gram reuse
    - Stopword ratio
    - Type-token ratio (lower can suggest repetition)
    - Presence of template-like headings (e.g., Causes/Effects/Solutions/Conclusion)
    - Transitional phrase density (e.g., moreover, additionally, in conclusion)
    """
    sentences = re.split(r"[.!?]+\s*", text.strip())
    sentences = [s for s in sentences if s]
    words = re.findall(r"\w+", text.lower())
    entropy = _entropy(words)

    lengths = [len(re.findall(r"\w+", s)) for s in sentences]
    avg_len = sum(lengths) / len(lengths) if lengths else 0.0
    var_len = (sum((l - avg_len) ** 2 for l in lengths) / len(lengths)) if lengths else 0.0

    # n-gram repetition
    trigrams = [" ".join(words[i : i + 3]) for i in range(max(0, len(words) - 2))]
    trigram_counts = Counter(trigrams)
    repetitive_trigrams = sum(1 for c in trigram_counts.values() if c >= 3)

    stopwords = set(
        "a an the and or but if on in at by for with to from of as is are was were be been being".split()
    )
    stop_ratio = sum(1 for w in words if w in stopwords) / (len(words) or 1)

    # Additional signals
    unique_words = set(words)
    ttr = (len(unique_words) / (len(words) or 1)) if words else 0.0

    headings_keywords = {"causes", "effects", "solutions", "conclusion"}
    headings_hits = sum(1 for kw in headings_keywords if kw in {w.lower() for w in unique_words})

    transitional_phrases = [
        "moreover", "additionally", "in conclusion", "overall", "for example", "for instance",
        "on the other hand", "furthermore", "however"
    ]
    tp_count = sum(len(re.findall(r"\b" + re.escape(tp) + r"\b", text.lower())) for tp in transitional_phrases)

    # Strict mode can be enabled via env var to increase sensitivity
    strict = os.getenv("AI_DETECT_STRICT", "false").lower() in {"1", "true", "yes"}

    score = 0.0
    score += 1.0 if entropy < (3.2 if strict else 3.0) else 0.0
    score += 1.0 if var_len < (36 if strict else 30) else 0.0
    score += 1.0 if repetitive_trigrams >= (4 if strict else 5) else 0.0
    score += 1.0 if stop_ratio > (0.52 if strict else 0.55) else 0.0
    score += 1.0 if ttr < (0.36 if strict else 0.33) else 0.0
    score += 1.0 if headings_hits >= (2 if strict else 3) else 0.0
    score += 1.0 if tp_count >= (4 if strict else 5) else 0.0

    # Map combined score to risk; clamp to max known bucket
    s_int = int(score)
    if s_int <= 1:
        risk = "low"
    elif s_int <= 3:
        risk = "moderate"
    else:
        risk = "high"
    return {
        "entropy": round(entropy, 3),
        "avg_sentence_len": round(avg_len, 2),
        "var_sentence_len": round(var_len, 2),
        "repetitive_trigrams": repetitive_trigrams,
        "stopword_ratio": round(stop_ratio, 3),
        "type_token_ratio": round(ttr, 3),
        "headings_hits": headings_hits,
        "transitional_count": tp_count,
        "strict": strict,
        "risk": risk,
        "likely_ai": score >= (2.0 if strict else 3.0),
        "disclaimer": "Heuristic-only; not ML-based. False positives common for formulaic writing.",
    }