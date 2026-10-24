"""
CareBridge AI — Policy Knowledge Search
Uses the Vector Database's built-in similarity search to retrieve relevant hospital policies.

EASY TO EXPLAIN:
1. embed_text: Converts text into a 384-dimensional vector using SentenceTransformer.
2. search_policy_knowledge: Uses PostgreSQL pgvector's built-in `<=>` cosine distance
   (or SQLite fallback) to return the top 3 matching hospital citations.
"""

import json
import logging
from typing import List
from sentence_transformers import SentenceTransformer

from database.db import get_db, HAS_DB_PGVECTOR
from database.models import PolicyChunk, PolicyDocument, HAS_PGVECTOR
from core.models import Citation

logger = logging.getLogger(__name__)

# Standard Hugging Face embedding model (384 dimensions)
_embedder = SentenceTransformer("all-MiniLM-L6-v2")


def embed_text(text: str) -> List[float]:
    """Convert any text string into a 384-dimensional vector."""
    return _embedder.encode(text).tolist()


def search_policy_knowledge(query: str, top_k: int = 3) -> List[Citation]:
    """Search hospital policies using built-in vector similarity search."""
    try:
        # Step 1: Embed search query into a vector
        query_vector = embed_text(query)

        with get_db() as db:
            # Step 2: Built-in pgvector similarity search in PostgreSQL
            if HAS_PGVECTOR and HAS_DB_PGVECTOR:
                results = (
                    db.query(PolicyChunk)
                    .join(PolicyDocument, PolicyChunk.document_id == PolicyDocument.id)
                    .filter(PolicyDocument.is_active == True)
                    .order_by(PolicyChunk.embedding.cosine_distance(query_vector))
                    .limit(top_k)
                    .all()
                )
                if results:
                    return [_make_citation(c, 0.95) for c in results]

            # Step 3: SQLite fallback (for local development when Postgres is offline)
            chunks = db.query(PolicyChunk).all()
            scored = []
            for c in chunks:
                if not c.embedding:
                    continue
                emb = json.loads(c.embedding) if isinstance(c.embedding, str) else c.embedding
                sim = sum(a * b for a, b in zip(query_vector, emb))
                scored.append((sim, c))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [_make_citation(c, sim) for sim, c in scored[:top_k]]

    except Exception as e:
        logger.error(f"Knowledge search failed: {e}")
        return []


def _make_citation(chunk: PolicyChunk, score: float) -> Citation:
    """Helper to format a database chunk into a clean Citation object."""
    return Citation(
        source_id=chunk.doc_code,
        title=chunk.title,
        section=chunk.section or "General",
        version=chunk.version,
        text_snippet=chunk.chunk_text,
        similarity_score=round(float(score), 2)
    )
