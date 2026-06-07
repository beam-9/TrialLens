from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9-]{1,}")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in WORD_RE.findall(text)]


def chunk_text(text: str, max_words: int = 92) -> list[str]:
    words = normalize(text).split()
    if not words:
        return []
    chunks = []
    for start in range(0, len(words), max_words):
        chunks.append(" ".join(words[start : start + max_words]))
    return chunks


def stable_embedding(text: str, dims: int = 64) -> list[float]:
    vector = [0.0] * dims
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:2], "big") % dims
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[idx] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def lexical_score(query: str, text: str) -> float:
    query_terms = Counter(tokenize(query))
    text_terms = Counter(tokenize(text))
    if not query_terms or not text_terms:
        return 0.0
    overlap = sum(min(count, text_terms[term]) for term, count in query_terms.items())
    return overlap / max(sum(query_terms.values()), 1)

