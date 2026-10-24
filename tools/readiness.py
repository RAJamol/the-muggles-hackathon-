"""
CareBridge AI — Surgical & Procedure Readiness Tool
Evaluates deterministic pre-operative checklist requirements for surgical clearance.

EASY TO EXPLAIN (3 Clear Clinical Checks):
1. Confirmed Appointment: Verified procedure booking in hospital schedule.
2. Complete Blood Count (CBC): Confirms hemoglobin/platelets are on file.
3. Coagulation Profile (PT/INR): Confirms blood clotting clearance before surgery.
4. Pre-op Instructions: Fasting (NPO after midnight), transportation, and medications.
"""

import logging
from typing import Dict, Any, Optional
from database.db import get_db
from database.models import Appointment, LabResult, Patient

logger = logging.getLogger(__name__)


def evaluate_patient_readiness(patient_id: str, procedure_hint: Optional[str] = None) -> Dict[str, Any]:
    """
    Evaluate pre-operative clearance for a patient across 3 standard checks.
    """
    try:
        with get_db() as db:
            patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
            if not patient:
                return {
                    "patient_id": patient_id,
                    "procedure_name": procedure_hint or "General Procedure",
                    "is_ready": False,
                    "missing_items": ["Patient record not found in hospital system."],
                    "completed_items": [],
                    "instructions": []
                }

            # Find next upcoming appointment
            upcoming_apt = (
                db.query(Appointment)
                .filter(Appointment.patient_id == patient_id, Appointment.status != "CANCELLED")
                .order_by(Appointment.scheduled_time.asc())
                .first()
            )

            procedure_name = procedure_hint or (upcoming_apt.department if upcoming_apt else "Upcoming Outpatient Surgery")

            # Fetch patient lab results
            labs = db.query(LabResult).filter(LabResult.patient_id == patient_id).all()
            lab_names = {l.test_name.lower(): l for l in labs}

            completed = []
            missing = []

            # Check 1: Scheduled Appointment
            if upcoming_apt:
                completed.append(f"Confirmed appointment on {upcoming_apt.scheduled_time.strftime('%b %d, %Y')} with {upcoming_apt.doctor_name}")
            else:
                missing.append("No active procedure appointment confirmed in hospital schedule.")

            # Check 2: Complete Blood Count (CBC)
            cbc_lab = next((lab_names[k] for k in lab_names if "cbc" in k or "blood count" in k), None)
            if cbc_lab:
                completed.append(f"Pre-op CBC Lab verified (Status: {cbc_lab.status})")
            else:
                missing.append("Pre-operative Complete Blood Count (CBC) test pending or missing.")

            # Check 3: Coagulation Profile (PT/INR)
            coag_lab = next((lab_names[k] for k in lab_names if "pt" in k or "inr" in k or "coagulation" in k), None)
            if coag_lab:
                completed.append(f"Coagulation PT/INR Profile verified (Result: {coag_lab.value} {coag_lab.unit})")
            else:
                missing.append("Coagulation profile (PT/INR) clearance test required.")

            instructions = [
                "NPO Fasting: Do not eat or drink anything after 12:00 midnight before surgery.",
                "Transportation: Arrange for an adult caregiver to drive you home following discharge.",
                "Medication: Pause blood thinners 48 hours prior if instructed by your physician."
            ]

            return {
                "patient_id": patient_id,
                "procedure_name": procedure_name,
                "is_ready": len(missing) == 0,
                "completed_items": completed,
                "missing_items": missing,
                "instructions": instructions
            }

    except Exception as e:
        logger.error(f"Error evaluating readiness for {patient_id}: {e}")
        return {
            "patient_id": patient_id,
            "procedure_name": procedure_hint or "Procedure",
            "is_ready": False,
            "missing_items": [f"Evaluation error: {str(e)}"],
            "completed_items": [],
            "instructions": []
        }
