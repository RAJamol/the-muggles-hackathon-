"""
CareBridge AI — Main Orchestrator Bridge
Connects the Streamlit web interface to the LangGraph Multi-Agent workflow.

FOR INTERVIEWS & SUPERVISORS:
1. Receives the user question from the Streamlit UI.
2. Checks patient boundary permissions (Server-Side Security).
3. Executes the compiled LangGraph workflow (carebridge_app.invoke).
4. Records an audit trail log for HIPAA compliance.
5. Returns a StructuredResponse with text, citations, and metadata.
"""

import logging
from typing import Dict, Any, List, Optional
from core.models import UserSession, StructuredResponse, AnswerType, Citation
from core.audit import generate_trace_id, log_audit_event
from core.auth import enforce_patient_access
from core.multi_agent import carebridge_app, HospitalAgentState
from core.hospital_tools import confirm_appointment_reschedule

logger = logging.getLogger(__name__)


class CareBridgeOrchestrator:
    """
    Main Orchestrator bridging the Streamlit UI to the LangGraph Multi-Agent Graph.
    """

    def __init__(self):
        # The compiled LangGraph StateGraph instance
        self.app = carebridge_app

    def process_request(
        self,
        query: str,
        session: UserSession,
        target_patient_id: Optional[str] = None,
        confirmation_action: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> StructuredResponse:
        """Process a user query through the multi-agent workflow."""
        trace_id = generate_trace_id()

        # Step 1: Security Guard — Ensure users only view their authorized patient data
        try:
            effective_patient_id = enforce_patient_access(session, target_patient_id)
        except PermissionError:
            log_audit_event(
                trace_id=trace_id,
                user_id=session.user_id,
                user_role=session.role.value,
                query=query,
                intent="unauthorized_access",
                tools_invoked=[],
                answer_type=AnswerType.REFUSED,
                response_summary="Access blocked: Patient boundary violation."
            )
            return StructuredResponse(
                trace_id=trace_id,
                answer_type=AnswerType.REFUSED,
                text="Access denied: You are not authorized to view or modify records for this patient.",
                confidence=1.0
            )

        # Step 2: Handle Two-Step Confirmation Action (e.g., user clicked "Confirm Reschedule")
        if confirmation_action and confirmation_action.get("type") == "confirm_reschedule":
            confirm_appointment_reschedule.invoke({
                "patient_id": effective_patient_id,
                "appointment_id": confirmation_action.get("appointment_id"),
                "new_time_iso": confirmation_action.get("new_time_iso")
            })
            
            final_text = (
                "✅ **Appointment Rescheduled Successfully**\n\n"
                "Your appointment has been officially updated in the hospital scheduling system. "
                "A confirmation notice has been sent to your registered contact details."
            )
            log_audit_event(
                trace_id=trace_id,
                user_id=session.user_id,
                user_role=session.role.value,
                query="Confirm Reschedule Action",
                intent="confirm_reschedule",
                tools_invoked=["confirm_appointment_reschedule"],
                answer_type=AnswerType.ACTION_COMPLETED,
                response_summary=final_text,
                patient_id=effective_patient_id
            )
            return StructuredResponse(
                trace_id=trace_id,
                answer_type=AnswerType.ACTION_COMPLETED,
                text=final_text
            )

        # Step 3: Package initial state for LangGraph
        initial_state: HospitalAgentState = {
            "query": query,
            "patient_id": effective_patient_id,
            "user_role": session.role.value,
            "trace_id": trace_id,
            "next_agent": "",
            "supervisor_reasoning": "",
            "agent_output": "",
            "citations": [],
            "action_proposal": None,
            "requires_confirmation": False,
            "answer_type": "retrieved_fact",
            "final_response": ""
        }

        # Step 4: Run the LangGraph Multi-Agent Workflow
        final_state = self.app.invoke(initial_state)

        # Step 5: Format response for Streamlit UI
        next_agent = final_state.get("next_agent", "doc_rag")
        final_text = final_state.get("final_response", "")
        raw_citations = final_state.get("citations", [])

        citations = [
            Citation(
                source_id="POL-METRO-001",
                title=c.get("title", "Hospital Guidelines"),
                section=c.get("section", "General"),
                text_snippet=c.get("snippet", ""),
                similarity_score=c.get("similarity", 0.0)
            ) for c in raw_citations
        ]

        raw_type = final_state.get("answer_type", "retrieved_fact")
        try:
            answer_type = AnswerType(raw_type)
        except Exception:
            answer_type = AnswerType.RETRIEVED_FACT

        # Step 6: Log HIPAA audit event
        log_audit_event(
            trace_id=trace_id,
            user_id=session.user_id,
            user_role=session.role.value,
            query=query,
            intent=f"langgraph_{next_agent}",
            tools_invoked=[f"LangGraph.{next_agent}_node"],
            answer_type=answer_type,
            response_summary=final_text[:300],
            patient_id=effective_patient_id
        )

        return StructuredResponse(
            trace_id=trace_id,
            answer_type=answer_type,
            text=final_text,
            citations=citations,
            action_details={
                "target_agent": next_agent,
                "next_agent": next_agent,
                "supervisor_reasoning": final_state.get("supervisor_reasoning")
            },
            requires_confirmation=final_state.get("requires_confirmation", False),
            pending_action_payload=final_state.get("action_proposal"),
            confidence=1.0
        )


# Aliases for backwards compatibility
GroqSupervisorAgent = CareBridgeOrchestrator
GrokSupervisorAgent = CareBridgeOrchestrator
