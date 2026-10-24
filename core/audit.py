import logging
import uuid
from typing import List, Optional
from datetime import datetime
from database.db import get_db
from database.models import AuditLog
from core.models import AnswerType, AuditLogEntry

logger = logging.getLogger(__name__)

def generate_trace_id() -> str:
    """Generate a unique audit trace ID."""
    return f"trace_{uuid.uuid4().hex[:12]}"

def log_audit_event(
    trace_id: str,
    user_id: str,
    user_role: str,
    query: str,
    intent: str,
    tools_invoked: List[str],
    answer_type: AnswerType,
    response_summary: str,
    patient_id: Optional[str] = None
) -> None:
    """Persist an audit trail record directly to PostgreSQL."""
    try:
        with get_db() as db:
            log_record = AuditLog(
                trace_id=trace_id,
                user_id=user_id,
                user_role=user_role,
                patient_id=patient_id,
                query=query,
                intent=intent,
                tools_invoked=",".join(tools_invoked) if tools_invoked else "none",
                answer_type=answer_type.value if isinstance(answer_type, AnswerType) else str(answer_type),
                response_summary=response_summary[:1000],  # Bound summary length
                timestamp=datetime.utcnow()
            )
            db.add(log_record)
        logger.info(f"Audit log recorded: {trace_id} [{answer_type}]")
    except Exception as e:
        logger.error(f"Failed to record audit log for trace {trace_id}: {e}")

def get_recent_audit_logs(limit: int = 50, patient_id: Optional[str] = None) -> List[AuditLogEntry]:
    """Retrieve audit events from PostgreSQL, ordered newest first."""
    try:
        with get_db() as db:
            query = db.query(AuditLog)
            if patient_id:
                query = query.filter(AuditLog.patient_id == patient_id)
            records = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
            
            entries = []
            for r in records:
                tools = r.tools_invoked.split(",") if r.tools_invoked and r.tools_invoked != "none" else []
                entries.append(AuditLogEntry(
                    trace_id=r.trace_id,
                    user_id=r.user_id,
                    user_role=r.user_role,
                    patient_id=r.patient_id,
                    query=r.query,
                    intent=r.intent,
                    tools_invoked=tools,
                    answer_type=AnswerType(r.answer_type) if r.answer_type in [e.value for e in AnswerType] else AnswerType.RETRIEVED_FACT,
                    response_summary=r.response_summary,
                    timestamp=r.timestamp
                ))
            return entries
    except Exception as e:
        logger.error(f"Failed to fetch audit logs: {e}")
        return []
