"""Optional research-note retrieval.

The default backend is a small deterministic lexical index so the project can
run without a vector database. A Qdrant adapter can be added behind the same
interface once embeddings and metadata policy have been reviewed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    text: str
    source: str
    tags: tuple[str, ...] = ()


class KnowledgeBase:
    def search(self, query: str, limit: int = 5) -> list[KnowledgeChunk]:
        raise NotImplementedError


class LocalKnowledgeBase(KnowledgeBase):
    def __init__(self, root: str | Path = "knowledge"):
        self.root = Path(root)
        self._chunks = self._load()

    def _load(self) -> list[KnowledgeChunk]:
        if not self.root.exists():
            return []
        chunks: list[KnowledgeChunk] = []
        for path in sorted(self.root.rglob("*.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for index, part in enumerate(re.split(r"\n{2,}", text)):
                cleaned = part.strip()
                if cleaned:
                    chunks.append(
                        KnowledgeChunk(
                            chunk_id=f"{path}:{index}",
                            text=cleaned,
                            source=str(path),
                        )
                    )
        return chunks

    def search(self, query: str, limit: int = 5) -> list[KnowledgeChunk]:
        terms = {term.lower() for term in re.findall(r"[a-zA-Z0-9_-]{3,}", query)}
        scored: list[tuple[int, KnowledgeChunk]] = []
        for chunk in self._chunks:
            haystack = chunk.text.lower()
            score = sum(haystack.count(term) for term in terms)
            if score:
                scored.append((score, chunk))
        scored.sort(key=lambda item: (-item[0], item[1].chunk_id))
        return [chunk for _, chunk in scored[:limit]]


def retrieve_context(
    query: str, root: str | Path = "knowledge", limit: int = 5
) -> list[dict[str, str]]:
    return [
        {"chunk_id": item.chunk_id, "source": item.source, "text": item.text}
        for item in LocalKnowledgeBase(root).search(query, limit=limit)
    ]


def qdrant_design_notes() -> dict[str, str]:
    """Return the contract for a future Qdrant implementation.

    Keeping this as a data contract avoids making the core project depend on a
    running vector database. Metadata must include case-independent source,
    language, CWE family, confidence and provenance URL.
    """

    return {
        "collection": "patch2proof_research_notes",
        "required_metadata": "source, published_at, language, cwe, tags, content_hash",
        "retrieval_rule": "retrieved notes inform hypotheses but never count as runtime evidence",
    }
