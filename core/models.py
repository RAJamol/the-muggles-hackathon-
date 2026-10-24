from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class AnswerType(str, Enum):
    RETRIEVED_FACT = "retrieved_fact"
    CALCULATED = "calculated"
    ACTION_COMPLETED = "action_completed"
    CLARIFICATION_NEEDED = "clarification_needed"
    NOT_FOUND = "not_found"
    REFUSED = "refused"
    CONFLICT_FLAGGED = "conflict_flagged"

class UserRole(str, Enum):
    PATIENT = "patient"
    STAFF = "staff"
    ADMIN = "admin"

class UserSession(BaseModel):
    user_id: str
    name: str
    role: UserRole
    patient_id: Optional[str] = None  # Server-side patient binding

class Citation(BaseModel):
    source_id: str
    title: str
    section: Optional[str] = None
    version: str = "v1.0"
    text_snippet: str
    similarity_score: Optional[float] = None

class StructuredResponse(BaseModel):
    trace_id: str
    answer_type: AnswerType
    text: str
    citations: List[Citation] = Field(default_factory=list)
    action_details: Optional[Dict[str, Any]] = None
    requires_confirmation: bool = False
    pending_action_payload: Optional[Dict[str, Any]] = None
    confidence: float = 1.0

# Entities
class PatientRecord(BaseModel):
    patient_id: str
    full_name: str
    date_of_birth: str
    phone: str
    insurance_provider: str
    insurance_policy_number: str
    assigned_doctor: str

class AppointmentRecord(BaseModel):
    appointment_id: str
    patient_id: str
    department: str
    doctor_name: str
    scheduled_time: datetime
    status: str = "SCHEDULED"  # SCHEDULED, COMPLETED, CANCELLED, RESCHEDULED
    reason: Optional[str] = None

class LabResultRecord(BaseModel):
    lab_id: str
    patient_id: str
    test_name: str
    value: str
    unit: str
    reference_range: str
    status: str  # NORMAL, ABNORMAL, CRITICAL, PENDING
    result_date: datetime
    physician_notes: Optional[str] = None

class ReadinessCheckResult(BaseModel):
    patient_id: str
    procedure_name: str
    is_ready: bool
    missing_items: List[str] = Field(default_factory=list)
    completed_items: List[str] = Field(default_factory=list)
    instructions: List[str] = Field(default_factory=list)

class AuditLogEntry(BaseModel):
    trace_id: str
    user_id: str
    user_role: str
    patient_id: Optional[str] = None
    query: str
    intent: str
    tools_invoked: List[str] = Field(default_factory=list)
    answer_type: AnswerType
    response_summary: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
