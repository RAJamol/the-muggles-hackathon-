"""
CareBridge AI — Laboratory Results Tool
Retrieves verified diagnostic blood tests (CBC, BMP, lipid panel) for a patient.

EASY TO EXPLAIN:
1. Queries verified lab results strictly filtered by the authenticated patient ID.
2. Supports filtering by test name (e.g., "CBC", "Platelet", "Glucose").
"""

import logging
from typing import List, Dict, Any, Optional
from database.db import get_db
from database.models import LabResult

logger = logging.getLogger(__name__)


def get_patient_lab_results(
    patient_id: str,
    test_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieve verified laboratory results for the authorized patient."""
    try:
        with get_db() as db:
            query = db.query(LabResult).filter(LabResult.patient_id == patient_id)
            if test_filter:
                query = query.filter(LabResult.test_name.ilike(f"%{test_filter}%"))

            labs = query.order_by(LabResult.result_date.desc()).all()
            return [
                {
                    "lab_id": l.lab_id,
                    "patient_id": l.patient_id,
                    "test_name": l.test_name,
                    "value": l.value,
                    "unit": l.unit,
                    "reference_range": l.reference_range,
                    "status": l.status,
                    "result_date": l.result_date.strftime("%b %d, %Y"),
                    "physician_notes": l.physician_notes or ""
                }
                for l in labs
            ]
    except Exception as e:
        logger.error(f"Error fetching lab results for patient {patient_id}: {e}")
        return []
