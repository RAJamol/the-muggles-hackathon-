"""
CareBridge AI — Insurance Pre-Authorization Tool
Checks if a procedure or CPT code requires insurance prior-authorization,
in-network restrictions, and estimated patient copays.

"""

import logging
from typing import Optional, Dict, Any, List
from database.db import get_db
from database.models import InsuranceRule

logger = logging.getLogger(__name__)


def check_procedure_preauth(procedure_query: str) -> Optional[Dict[str, Any]]:
    """Check prior-authorization rule by CPT code or procedure keyword."""
    clean_query = procedure_query.strip().lower()
    try:
        with get_db() as db:
            rules: List[InsuranceRule] = db.query(InsuranceRule).all()

            # 1. Match on CPT Code (e.g., "29881")
            for r in rules:
                if r.procedure_code.lower() == clean_query:
                    return _format_rule(r)

            # 2. Match on Procedure Name or Substring (e.g., "knee", "mri", "colonoscopy")
            for r in rules:
                name = r.procedure_name.lower()
                if clean_query in name or name in clean_query:
                    return _format_rule(r)

            # 3. Match any prominent keyword (words > 3 letters)
            keywords = [w for w in clean_query.split() if len(w) > 3]
            for r in rules:
                name = r.procedure_name.lower()
                if any(kw in name for kw in keywords):
                    return _format_rule(r)

            return None
    except Exception as e:
        logger.error(f"Error checking insurance rule for {procedure_query}: {e}")
        return None


def get_all_preauth_rules() -> List[Dict[str, Any]]:
    """Return all insurance pre-authorization rules for staff view."""
    try:
        with get_db() as db:
            rules = db.query(InsuranceRule).all()
            return [_format_rule(r) for r in rules]
    except Exception as e:
        logger.error(f"Error fetching insurance rules: {e}")
        return []


def _format_rule(r: InsuranceRule) -> Dict[str, Any]:
    """Helper to convert database row to clean dictionary."""
    return {
        "procedure_code": r.procedure_code,
        "procedure_name": r.procedure_name,
        "requires_preauth": r.requires_preauth,
        "in_network_only": r.in_network_only,
        "estimated_copay": r.estimated_copay,
        "criteria": r.criteria or "Standard clinical necessity documentation required.",
        "notes": r.notes or ""
    }
