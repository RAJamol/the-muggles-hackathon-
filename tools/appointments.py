"""
CareBridge AI — Appointment Management Tool
Queries upcoming doctor visits and provides safe 2-step appointment rescheduling.


"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from database.db import get_db
from database.models import Appointment

logger = logging.getLogger(__name__)


def get_patient_appointments(patient_id: str) -> List[Dict[str, Any]]:
    """Retrieve all upcoming appointments for the patient."""
    try:
        with get_db() as db:
            apts = (
                db.query(Appointment)
                .filter(Appointment.patient_id == patient_id)
                .order_by(Appointment.scheduled_time.asc())
                .all()
            )
            return [
                {
                    "appointment_id": a.appointment_id,
                    "patient_id": a.patient_id,
                    "department": a.department,
                    "doctor_name": a.doctor_name,
                    "scheduled_time": a.scheduled_time.strftime("%A, %b %d, %Y at %I:%M %p"),
                    "scheduled_time_raw": a.scheduled_time.isoformat(),
                    "status": a.status,
                    "reason": a.reason or ""
                }
                for a in apts
            ]
    except Exception as e:
        logger.error(f"Error fetching appointments for patient {patient_id}: {e}")
        return []


def preview_reschedule(
    patient_id: str,
    appointment_id: Optional[str] = None,
    new_time: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Generate an uncommitted reschedule preview (Step 1 of 2).
    Requires explicit user confirmation before any database modification.
    """
    apts = get_patient_appointments(patient_id)
    if not apts:
        return {"error": "No appointments found to reschedule."}

    # Select target appointment
    target = None
    if appointment_id:
        target = next((a for a in apts if a["appointment_id"] == appointment_id), None)
    if not target:
        target = apts[0]

    # Propose new date: 2 days later at 10:00 AM if not specified
    if not new_time:
        current_dt = datetime.fromisoformat(target["scheduled_time_raw"])
        new_time = (current_dt + timedelta(days=2)).replace(hour=10, minute=0, second=0)

    return {
        "appointment_id": target["appointment_id"],
        "doctor_name": target["doctor_name"],
        "department": target["department"],
        "current_time": target["scheduled_time"],
        "proposed_time": new_time.strftime("%A, %b %d, %Y at %I:%M %p"),
        "proposed_time_iso": new_time.isoformat(),
        "requires_confirmation": True
    }


def execute_reschedule(
    patient_id: str,
    appointment_id: str,
    new_time_iso: str
) -> Dict[str, Any]:
    """
    Commit the rescheduling change in the database after user confirmation (Step 2 of 2).
    """
    try:
        new_dt = datetime.fromisoformat(new_time_iso)
        with get_db() as db:
            apt = (
                db.query(Appointment)
                .filter(
                    Appointment.appointment_id == appointment_id,
                    Appointment.patient_id == patient_id
                )
                .first()
            )
            if not apt:
                return {
                    "success": False,
                    "error": f"Appointment {appointment_id} not found for this patient."
                }

            old_time = apt.scheduled_time.strftime("%A, %b %d, %Y at %I:%M %p")
            apt.scheduled_time = new_dt
            apt.status = "RESCHEDULED"
            db.commit()

            return {
                "success": True,
                "appointment_id": appointment_id,
                "department": apt.department,
                "doctor_name": apt.doctor_name,
                "previous_time": old_time,
                "new_time": new_dt.strftime("%A, %b %d, %Y at %I:%M %p")
            }
    except Exception as e:
        logger.error(f"Failed to execute reschedule: {e}")
        return {"success": False, "error": str(e)}
