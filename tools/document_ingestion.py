"""
CareBridge AI — Document Ingestion (Beginner-Friendly RAG)
Loads hospital documents, splits them with LangChain, and saves them to the database.


"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from database.db import get_db
from database.models import PolicyDocument, PolicyChunk, HAS_PGVECTOR
from tools.knowledge_search import embed_text

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Step 1: Read text from file
# -------------------------------------------------------------------------
def read_file_text(file_path: Path) -> str:
    """Read plain text from PDF, Markdown, or text file."""
    if file_path.suffix.lower() == ".pdf":
        reader = PdfReader(str(file_path))
        return "\n".join([page.extract_text() or "" for page in reader.pages])
    return file_path.read_text(encoding="utf-8", errors="ignore")


# -------------------------------------------------------------------------
# Step 2: Save chunks to database
# -------------------------------------------------------------------------
def save_to_database(
    doc_code: str,
    title: str,
    version: str,
    file_path: str,
    chunks: List[str],
    embeddings: List[List[float]]
):
    """Save document and its vector chunks to the database."""
    with get_db() as db:
        # Create the parent document record
        doc = PolicyDocument(
            doc_code=doc_code,
            title=title,
            version=version,
            is_active=True,
            file_path=file_path
        )
        db.add(doc)
        db.flush()

        # Add each chunk with its vector embedding
        for text, emb in zip(chunks, embeddings):
            # First line of chunk is used as the section title
            section = text.split("\n")[0].replace("#", "").strip()[:50] or "General"
            
            chunk = PolicyChunk(
                document_id=doc.id,
                doc_code=doc_code,
                title=title,
                section=section,
                version=version,
                chunk_text=text,
                embedding=emb if HAS_PGVECTOR else json.dumps(emb)
            )
            db.add(chunk)

        db.commit()


# -------------------------------------------------------------------------
# Step 3: Main Ingestion Function (Clean & 10 lines)
# -------------------------------------------------------------------------
def ingest_policy_document(
    file_path: Path,
    doc_code: str,
    title: str,
    version: str = "v1.0"
) -> Dict[str, Any]:
    """Ingest a policy document: Read -> Chunk with LangChain -> Embed -> Save."""
    try:
        # 1. Read file
        raw_text = read_file_text(file_path)
        if not raw_text.strip():
            return {"success": False, "error": "Document contains no readable text."}

        # 2. Chunk text with LangChain
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = splitter.split_text(raw_text)

        # 3. Embed chunks into vectors
        embeddings = [embed_text(chunk) for chunk in chunks]

        # 4. Save to database
        save_to_database(doc_code, title, version, str(file_path), chunks, embeddings)

        logger.info(f"Successfully ingested {len(chunks)} chunks for {doc_code}")
        return {
            "success": True,
            "doc_code": doc_code,
            "title": title,
            "version": version,
            "chunks_count": len(chunks)
        }

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        return {"success": False, "error": str(e)}
