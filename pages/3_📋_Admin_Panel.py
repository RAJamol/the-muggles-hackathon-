import streamlit as st
import tempfile
from pathlib import Path
from core.auth import enforce_page_access
from core.models import UserRole
from database.db import get_db
from database.models import PolicyDocument, PolicyChunk
from tools.document_ingestion import ingest_policy_document
import config

st.set_page_config(page_title="Admin Panel — CareBridge AI", page_icon="📋", layout="wide")

# Role Guard: ONLY ADMIN can view and ingest policies
session = enforce_page_access("Admin Panel", allowed_roles=[UserRole.ADMIN])

st.title("📋 Hospital Policy & SOP Ingestion Panel")
st.caption("Upload hospital standard operating procedures (PDF, Markdown, TXT) with automatic vector indexing.")

# Ingestion Form
st.subheader("📤 Ingest New Hospital Policy / SOP")

col1, col2 = st.columns(2)
with col1:
    doc_code = st.text_input("Document Identifier Code (e.g. POL-EMR-004):", value="POL-NEW-001")
    title = st.text_input("Document Title:", value="Emergency Triage & Escalation Guidelines")
with col2:
    version = st.text_input("Version Tag:", value="v1.0")
    uploaded_file = st.file_uploader("Upload Policy File (.pdf, .md, .txt):", type=["pdf", "md", "txt"])

if st.button("🚀 Ingest & Index in Database", type="primary", disabled=not uploaded_file):
    with st.spinner("Parsing document with PyPDF, generating Hugging Face embeddings, and storing in PostgreSQL..."):
        suffix = Path(uploaded_file.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(uploaded_file.getbuffer())
            tmp_path = Path(tmp_file.name)

        res = ingest_policy_document(
            file_path=tmp_path,
            doc_code=doc_code.strip(),
            title=title.strip(),
            version=version.strip()
        )

        if res.get("success"):
            st.success(
                f"✅ **Policy Successfully Ingested!**\n\n"
                f"- **Doc Code**: `{res['doc_code']}`\n"
                f"- **Title**: {res['title']}\n"
                f"- **Version**: `{res['version']}`\n"
                f"- **Vectorized Chunks**: {res['chunks_count']} records indexed."
            )
        else:
            st.error(f"Ingestion failed: {res.get('error')}")

st.divider()

# Existing Policies Overview
st.subheader("📚 Active Hospital Policies & Vector Chunks")

try:
    with get_db() as db:
        docs = db.query(PolicyDocument).order_by(PolicyDocument.uploaded_at.desc()).all()
        if docs:
            table_data = []
            for d in docs:
                chunk_count = db.query(PolicyChunk).filter(PolicyChunk.document_id == d.id).count()
                table_data.append({
                    "Doc Code": d.doc_code,
                    "Title": d.title,
                    "Version": d.version,
                    "Active": "🟢 Yes" if d.is_active else "⚪ Inactive",
                    "Indexed Chunks": chunk_count,
                    "Uploaded At": d.uploaded_at.strftime("%Y-%m-%d %H:%M UTC")
                })
            st.dataframe(table_data, use_container_width=True)
        else:
            st.info("No policy documents found in PostgreSQL. Run the database seed from the home page to load standard hospital SOPs.")
except Exception as e:
    st.error(f"Could not load policy records: {e}")
