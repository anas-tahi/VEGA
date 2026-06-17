"""
rag.py — Retrieval-Augmented Generation for Vega.

Uses TF-IDF keyword similarity to retrieve the most relevant knowledge
files for any query — no API calls, no embeddings, fully local.

How to add knowledge:
    Create a .txt file in memory/knowledge/
    e.g. memory/knowledge/university.txt
    Content is loaded automatically — no code changes needed.
"""

from __future__ import annotations
import math
import re
import sys
from collections import Counter
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


KNOWLEDGE_DIR = get_base_dir() / "memory" / "knowledge"


# ---------------------------------------------------------------------------
# TF-IDF helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split into words."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _tf(tokens: list[str]) -> dict[str, float]:
    """Term frequency: count / total."""
    total = len(tokens) or 1
    counts = Counter(tokens)
    return {t: c / total for t, c in counts.items()}


def _idf(docs: list[list[str]]) -> dict[str, float]:
    """Inverse document frequency across all docs."""
    N = len(docs) or 1
    df: dict[str, int] = {}
    for doc in docs:
        for term in set(doc):
            df[term] = df.get(term, 0) + 1
    return {term: math.log((N + 1) / (freq + 1)) + 1 for term, freq in df.items()}


def _score(query_tokens: list[str], doc_tokens: list[str], idf: dict[str, float]) -> float:
    """Cosine-style TF-IDF score between query and document."""
    if not query_tokens or not doc_tokens:
        return 0.0
    doc_tf = _tf(doc_tokens)
    score = 0.0
    for term in query_tokens:
        if term in doc_tf:
            score += idf.get(term, 1.0) * doc_tf[term]
    return score


# ---------------------------------------------------------------------------
# Document loading
# ---------------------------------------------------------------------------

def _load_all_docs() -> list[dict]:
    """Load all .txt knowledge files."""
    docs = []
    if not KNOWLEDGE_DIR.exists():
        return docs
    for f in sorted(KNOWLEDGE_DIR.glob("*.txt")):
        try:
            content = f.read_text(encoding="utf-8").strip()
            if content:
                docs.append({"name": f.stem, "content": content})
        except Exception:
            pass
    return docs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve(query: str = "", max_chars: int = 2000, top_k: int = 4) -> str:
    """
    Retrieve the most relevant knowledge docs for the given query.
    Falls back to full retrieval if query is empty.
    Returns a formatted string ready for system prompt injection.
    """
    docs = _load_all_docs()
    if not docs:
        return ""

    if not query.strip():
        # No query — just dump all until limit (original behavior)
        sections, total = [], 0
        for doc in docs:
            chunk = f"[{doc['name'].upper().replace('_', ' ')}]\n{doc['content']}"
            if total + len(chunk) > max_chars:
                break
            sections.append(chunk)
            total += len(chunk)
    else:
        # TF-IDF ranking
        query_tokens = _tokenize(query)
        all_tokens   = [_tokenize(d["content"]) for d in docs]
        idf          = _idf(all_tokens)

        scored = [
            (doc, _score(query_tokens, tokens, idf))
            for doc, tokens in zip(docs, all_tokens)
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Take top_k relevant, but always include profile + preferences
        ALWAYS_INCLUDE = {"anas_profile", "preferences"}
        seen, sections, total = set(), [], 0

        for doc, score in scored:
            if len(sections) >= top_k and doc["name"] not in ALWAYS_INCLUDE:
                break
            if doc["name"] in seen:
                continue
            chunk = f"[{doc['name'].upper().replace('_', ' ')}]\n{doc['content']}"
            if total + len(chunk) > max_chars:
                break
            sections.append(chunk)
            seen.add(doc["name"])
            total += len(chunk)

        # Ensure always-include docs are present
        for doc in docs:
            if doc["name"] in ALWAYS_INCLUDE and doc["name"] not in seen:
                chunk = f"[{doc['name'].upper().replace('_', ' ')}]\n{doc['content']}"
                if total + len(chunk) <= max_chars:
                    sections.append(chunk)
                    total += len(chunk)

    if not sections:
        return ""

    return "[PERSONAL KNOWLEDGE BASE]\n" + "\n\n".join(sections) + "\n\n"


def save_knowledge(topic: str, content: str) -> bool:
    """Save or update a knowledge entry from a conversation."""
    try:
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = topic.lower().replace(" ", "_")[:50]
        path = KNOWLEDGE_DIR / f"{safe_name}.txt"
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        if content not in existing:
            with open(path, "a", encoding="utf-8") as f:
                if existing:
                    f.write("\n")
                f.write(content)
        return True
    except Exception as e:
        print(f"[RAG] ⚠️ save failed: {e}")
        return False
