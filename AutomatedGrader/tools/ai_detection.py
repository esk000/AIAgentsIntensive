from typing import Dict, Any
import math
import re
from collections import Counter


def _entropy(tokens):
    counts = Counter(tokens)
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return -sum((c / total) * math.log(c / total + 1e-12) for c in counts.values())


def detect_ai_generated(text: str) -> Dict[str, Any]:
    """Heuristic detection of AI-generated text.

    Signals considered:
    - Token entropy (lower can indicate uniform phrasing)
    - Sentence length variance (very uniform lengths can indicate AI)
    - Repetitive phrases and n-gram reuse
    - Stopword ratio
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

    score = 0.0
    score += 1.0 if entropy < 3.0 else 0.0
    score += 1.0 if var_len < 30 else 0.0
    score += 1.0 if repetitive_trigrams >= 5 else 0.0
    score += 1.0 if stop_ratio > 0.55 else 0.0

    risk_levels = {0: "low", 1: "low", 2: "moderate", 3: "high", 4: "high"}
    return {
        "entropy": round(entropy, 3),
        "avg_sentence_len": round(avg_len, 2),
        "var_sentence_len": round(var_len, 2),
        "repetitive_trigrams": repetitive_trigrams,
        "stopword_ratio": round(stop_ratio, 3),
        "risk": risk_levels[int(score)],
        "likely_ai": score >= 3.0,
    }