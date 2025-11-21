from typing import List, Dict, Any, Tuple
import re
from difflib import SequenceMatcher


def _chunk_text(text: str, min_words: int = 25, max_words: int = 40) -> List[str]:
    words = re.findall(r"\w+", text)
    chunks = []
    i = 0
    while i < len(words):
        size = min(max_words, max(min_words, len(words) - i))
        chunk = " ".join(words[i : i + size])
        if chunk:
            chunks.append(chunk)
        i += size
    return chunks


def _search_chunk(chunk: str, max_results: int = 3) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    try:
        from duckduckgo_search import DDGS  # type: ignore
        with DDGS() as ddgs:
            for r in ddgs.text(chunk, max_results=max_results):
                results.append({"title": r.get("title"), "body": r.get("body"), "href": r.get("href")})
    except Exception:
        # No dependency or search failed; return empty results
        pass
    return results


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def check_plagiarism(text: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Check for potential plagiarism by querying chunks and comparing snippets.

    Returns a summary plus a list of per-chunk findings. If web search is
    unavailable, the summary reflects limited confidence.
    """
    chunks = _chunk_text(text)
    findings: List[Dict[str, Any]] = []
    similarities: List[float] = []
    for chunk in chunks:
        search_results = _search_chunk(chunk)
        top_sim = 0.0
        best_match = None
        for r in search_results:
            candidate = (r.get("body") or "") + " " + (r.get("title") or "")
            sim = _similarity(chunk, candidate)
            if sim > top_sim:
                top_sim = sim
                best_match = r
        similarities.append(top_sim)
        findings.append({"chunk": chunk[:200], "similarity": top_sim, "best_match": best_match})

    avg_sim = sum(similarities) / len(similarities) if similarities else 0.0
    high_sim_count = sum(1 for s in similarities if s >= 0.85)

    summary = {
        "avg_similarity": round(avg_sim, 3),
        "high_similarity_chunks": high_sim_count,
        "likely_plagiarized": high_sim_count >= max(1, len(chunks) // 6),
        "confidence": "limited" if not findings or all(not f.get("best_match") for f in findings) else "moderate",
    }
    return summary, findings