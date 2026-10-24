import datetime
import json
from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, ForeignKey, Integer, Float, Index
)
from sqlalchemy.orm import declarative_base, relationship
import config

Base = declarative_base()

# Resilient pgvector column support:
# If pgvector is installed and available, use native Vector.
# If not installed or vanilla Postgres without C-extension, use Text/JSON to avoid crash.
HAS_PGVECTOR = False
try:
    from pgvector.sqlalchemy import Vector
    EmbeddingColumnType = Vector(config.EMBEDDING_DIM)
    HAS_PGVECTOR = True
except (ImportError, Exception):
    EmbeddingColumnType = Text  # Fallback: store embedding as JSON-serialized list

class AppUser(Base):
    __tablename__ = "app_users"

    login_id = Column(String(50), primary_key=True, index=True)
    password_hash = Column(String(100), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(30), nullable=False)  # 'patient', 'staff', 'admin'
    patient_id = Column(String(50), nullable=True)  # bound patient ID if role is patient

class Patient(Base):
    __tablename__ = "patients"

    patient_id = Column(String(50), primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    date_of_birth = Column(String(20), nullable=False)
    phone = Column(String(20), nullable=False)
    insurance_provider = Column(String(100), nullable=False)
    insurance_policy_number = Column(String(50), nullable=False)
    assigned_doctor = Column(String(100), nullable=False)

    appointments = relationship("Appointment", back_populates="patient", cascade="all, delete-orphan")
    lab_results = relationship("LabResult", back_populates="patient", cascade="all, delete-orphan")

class Appointment(Base):
    __tablename__ = "appointments"

    appointment_id = Column(String(50), primary_key=True, index=True)
    patient_id = Column(String(50), ForeignKey("patients.patient_id"), nullable=False, index=True)
    department = Column(String(100), nullable=False)
    doctor_name = Column(String(100), nullable=False)
    scheduled_time = Column(DateTime, nullable=False)
    status = Column(String(30), default="SCHEDULED", nullable=False)
    reason = Column(Text, nullable=True)

    patient = relationship("Patient", back_populates="appointments")

class LabResult(Base):
    __tablename__ = "lab_results"

    lab_id = Column(String(50), primary_key=True, index=True)
    patient_id = Column(String(50), ForeignKey("patients.patient_id"), nullable=False, index=True)
    test_name = Column(String(100), nullable=False, index=True)
    value = Column(String(50), nullable=False)
    unit = Column(String(20), nullable=False)
    reference_range = Column(String(50), nullable=False)
    status = Column(String(30), nullable=False)
    result_date = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    physician_notes = Column(Text, nullable=True)

    patient = relationship("Patient", back_populates="lab_results")

class InsuranceRule(Base):
    __tablename__ = "insurance_rules"

    procedure_code = Column(String(50), primary_key=True, index=True)
    procedure_name = Column(String(150), nullable=False)
    requires_preauth = Column(Boolean, default=False, nullable=False)
    in_network_only = Column(Boolean, default=True, nullable=False)
    estimated_copay = Column(Float, default=0.0, nullable=False)
    criteria = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_code = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    version = Column(String(20), nullable=False, default="v1.0")
    is_active = Column(Boolean, default=True, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    file_path = Column(String(500), nullable=True)

    chunks = relationship("PolicyChunk", back_populates="document", cascade="all, delete-orphan")

class PolicyChunk(Base):
    __tablename__ = "policy_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("policy_documents.id"), nullable=False)
    doc_code = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    section = Column(String(150), nullable=True)
    version = Column(String(20), nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(EmbeddingColumnType, nullable=True)

    document = relationship("PolicyDocument", back_populates="chunks")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trace_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(100), nullable=False)
    user_role = Column(String(50), nullable=False)
    patient_id = Column(String(50), nullable=True, index=True)
    query = Column(Text, nullable=False)
    intent = Column(String(100), nullable=False)
    tools_invoked = Column(String(255), nullable=True)
    answer_type = Column(String(50), nullable=False)
    response_summary = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
