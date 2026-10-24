"""

"""

import json
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool

# Internal database access functions
from tools.knowledge_search import search_policy_knowledge
from tools.appointments import get_patient_appointments as _get_apts
from tools.appointments import preview_reschedule as _preview_reschedule
from tools.appointments import execute_reschedule as _confirm_reschedule
from tools.lab_results import get_patient_lab_results as _get_labs
from tools.readiness import evaluate_patient_readiness as _eval_readiness
from tools.insurance import check_procedure_preauth as _check_preauth
from tools.insurance import get_all_preauth_rules as _get_all_rules


# -------------------------------------------------------------------------
# 1. Document RAG Tool
# -------------------------------------------------------------------------
@tool
def search_hospital_policies(query: str) -> str:
    """Search hospital operational policies, ICU visiting hours, parking rules, discharge rules, and SOPs using vector embeddings."""
    citations = search_policy_knowledge(query, top_k=3)
    if not citations:
        return "No relevant hospital policies found."
    results = []
    for c in citations:
        results.append({
            "title": c.title,
            "section": c.section or "General",
            "snippet": c.text_snippet,
            "similarity": c.similarity_score or 0.0
        })
    return json.dumps(results, indent=2)


# -------------------------------------------------------------------------
# 2. Appointment Scheduling Tools
# -------------------------------------------------------------------------
@tool
def get_patient_appointments(patient_id: str) -> str:
    """Retrieve all upcoming scheduled appointments for a patient by their patient ID."""
    apts = _get_apts(patient_id)
    if not apts:
        return f"No scheduled appointments found for patient {patient_id}."
    return json.dumps(apts, indent=2, default=str)


@tool
def preview_appointment_reschedule(patient_id: str, appointment_id: Optional[str] = None) -> str:
    """Generate a preview of an appointment reschedule, showing doctor availability and proposed new date/time."""
    preview = _preview_reschedule(patient_id=patient_id, appointment_id=appointment_id)
    return json.dumps(preview, indent=2, default=str)


@tool
def confirm_appointment_reschedule(patient_id: str, appointment_id: str, new_time_iso: str) -> str:
    """Confirm and execute the appointment reschedule in the hospital database."""
    res = _confirm_reschedule(patient_id=patient_id, appointment_id=appointment_id, new_time_iso=new_time_iso)
    return json.dumps(res, indent=2, default=str)


# -------------------------------------------------------------------------
# 3. Lab Results & Surgical Readiness Tools
# -------------------------------------------------------------------------
@tool
def get_patient_lab_results(patient_id: str, test_name: Optional[str] = None) -> str:
    """Retrieve verified laboratory test results (e.g. CBC, BMP, lipid panel) for a patient."""
    labs = _get_labs(patient_id=patient_id, test_filter=test_name)
    if not labs:
        return f"No recent verified lab results found for patient {patient_id}."
    return json.dumps(labs, indent=2, default=str)


@tool
def check_surgery_readiness(patient_id: str, procedure_name: Optional[str] = None) -> str:
    """Check if patient has completed all pre-operative clearance requirements (NPO fasting, blood tests, consent form)."""
    readiness = _eval_readiness(patient_id=patient_id, procedure_hint=procedure_name)
    return json.dumps(readiness, indent=2, default=str)


# -------------------------------------------------------------------------
# 4. Insurance Pre-Authorization Tool
# -------------------------------------------------------------------------
@tool
def check_insurance_preauth(procedure_name: str) -> str:
    """Check if a surgical procedure or diagnostic scan requires insurance prior-authorization, copay estimate, or clinical criteria."""
    rule = _check_preauth(procedure_name)
    if not rule:
        return f"No specific pre-authorization rule found for procedure: {procedure_name}."
    return json.dumps(rule, indent=2, default=str)


# Export list of all tools
HOSPITAL_TOOLS = [
    search_hospital_policies,
    get_patient_appointments,
    preview_appointment_reschedule,
    confirm_appointment_reschedule,
    get_patient_lab_results,
    check_surgery_readiness,
    check_insurance_preauth
]
