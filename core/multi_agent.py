"""
CareBridge AI — LangGraph Multi-Agent Architecture 
.


1. HospitalAgentState: Shared data passed between agents (query, patient_id, citations).
2. Supervisor Node: Uses ChatGroq with structured output to route to the best specialist.
3. Specialist Nodes:
   - doc_rag: Hospital policies & visiting hours RAG.
   - appointment: Upcoming visits & safe rescheduling preview.
   - lab_readiness: Verified blood tests & surgery readiness checklist.
   - insurance: Prior-authorization rules & estimated copays.
   - refusal: Emergency medical safety guardrail.
4. Synthesis Node: Combines findings into an empathetic, grounded response.
5. StateGraph: Wires nodes and conditional edges together into a compiled workflow.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Literal, TypedDict
from pydantic import BaseModel, Field

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END

import config
from core.hospital_tools import (
    search_hospital_policies,
    get_patient_appointments,
    preview_appointment_reschedule,
    get_patient_lab_results,
    check_surgery_readiness,
    check_insurance_preauth
)

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# 1. State Definition (What data flows through the LangGraph)
# -------------------------------------------------------------------------
class HospitalAgentState(TypedDict):
    """The shared state passed through every node in the graph."""
    query: str
    patient_id: Optional[str]
    user_role: str
    trace_id: str
    next_agent: str
    supervisor_reasoning: str
    agent_output: str
    citations: List[Dict[str, Any]]
    action_proposal: Optional[Dict[str, Any]]
    requires_confirmation: bool
    answer_type: str
    final_response: str


# -------------------------------------------------------------------------
# 2. Initialize Groq LLM (Ultra-fast LPU inference)
# -------------------------------------------------------------------------
def get_groq_llm(temperature: float = 0.0) -> ChatGroq:
    """Helper to initialize the ChatGroq model."""
    return ChatGroq(
        api_key=config.GROQ_API_KEY,
        model_name=config.GROQ_MODEL,
        temperature=temperature
    )


# -------------------------------------------------------------------------
# 3. Supervisor Node (Routes query to the right specialist)
# -------------------------------------------------------------------------
class SupervisorRoute(BaseModel):
    """LangChain structured output schema for the supervisor router."""
    target_agent: Literal["doc_rag", "appointment", "lab_readiness", "insurance", "refusal"] = Field(
        description="The chosen specialized agent to handle the user query."
    )
    reasoning: str = Field(description="Brief reason for selecting this agent.")


SUPERVISOR_SYSTEM_PROMPT = """You are the Lead Hospital Supervisor Agent for Metro General Hospital.
Select the single best specialized agent to handle the user's message:

- "doc_rag": Hospital rules, visiting hours, parking, discharge timing, visitor guidelines.
- "appointment": Viewing upcoming doctor visits or requesting to reschedule an appointment.
- "lab_readiness": Laboratory blood tests (CBC, BMP, lipids) or pre-operative surgery readiness clearance.
- "insurance": Procedure prior-authorization rules, CPT codes, and estimated copays.
- "refusal": Medical emergencies, diagnosis requests ("do I have a stroke", "what medicine to take"), prescriptions.
"""

def supervisor_node(state: HospitalAgentState) -> Dict[str, Any]:
    """Supervisor LLM analyzes the query and picks the best specialist agent."""
    query = state.get("query", "")
    try:
        llm = get_groq_llm(temperature=0.0)
        router_llm = llm.with_structured_output(SupervisorRoute)
        decision = router_llm.invoke([
            SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
            HumanMessage(content=f"User Role: {state.get('user_role')}\nQuery: {query}")
        ])
        return {
            "next_agent": decision.target_agent,
            "supervisor_reasoning": decision.reasoning
        }
    except Exception as e:
        logger.warning(f"Supervisor structured routing fallback: {e}")
        # Simple keyword fallback if API fails
        q = query.lower()
        if any(w in q for w in ["diagnose", "chest pain", "stroke", "medicine", "prescription"]):
            return {"next_agent": "refusal", "supervisor_reasoning": "Clinical emergency safety fallback."}
        if any(w in q for w in ["appointment", "doctor visit", "reschedule"]):
            return {"next_agent": "appointment", "supervisor_reasoning": "Appointment lookup fallback."}
        if any(w in q for w in ["lab", "blood test", "cbc", "surgery", "ready"]):
            return {"next_agent": "lab_readiness", "supervisor_reasoning": "Clinical lab/readiness fallback."}
        if any(w in q for w in ["insurance", "prior auth", "pre-auth", "copay"]):
            return {"next_agent": "insurance", "supervisor_reasoning": "Insurance rule fallback."}
        return {"next_agent": "doc_rag", "supervisor_reasoning": "Hospital policy fallback."}


# -------------------------------------------------------------------------
# 4. Document RAG Node (Searches policies and extracts citations)
# -------------------------------------------------------------------------
def doc_rag_node(state: HospitalAgentState) -> Dict[str, Any]:
    """Specialized LLM Agent that searches policies and extracts grounded citations."""
    query = state.get("query", "")
    
    # 1. Call LangChain vector search tool
    tool_raw = search_hospital_policies.invoke({"query": query})
    try:
        citations = json.loads(tool_raw) if tool_raw.startswith("[") else []
    except Exception:
        citations = []

    # 2. Reason over retrieved excerpts with Groq
    if citations:
        context = "\n\n".join([f"[{c['title']} - {c['section']}]: {c['snippet']}" for c in citations])
        prompt = [
            SystemMessage(content="You are the Hospital Policy Specialist. Answer the question strictly using the provided hospital excerpts. Cite the document title and section."),
            HumanMessage(content=f"Question: {query}\n\nExcerpts:\n{context}")
        ]
        output = get_groq_llm().invoke(prompt).content.strip()
    else:
        output = "No matching hospital policy or guideline was found in authorized hospital documents."

    return {
        "agent_output": output,
        "citations": citations,
        "answer_type": "retrieved_fact" if citations else "not_found"
    }


# -------------------------------------------------------------------------
# 5. Appointment Node (Upcoming visits & safe 2-step reschedule)
# -------------------------------------------------------------------------
def appointment_node(state: HospitalAgentState) -> Dict[str, Any]:
    """Specialized LLM Agent that views visits and prepares safe reschedule proposals."""
    query = state.get("query", "")
    patient_id = state.get("patient_id") or "PAT-001"
    is_reschedule = any(k in query.lower() for k in ["reschedule", "change", "move", "postpone"])

    if is_reschedule:
        # Step 1 of 2: Generate preview without modifying database
        preview_raw = preview_appointment_reschedule.invoke({"patient_id": patient_id})
        try:
            preview = json.loads(preview_raw)
        except Exception:
            preview = {}

        req_confirm = "error" not in preview
        pending_payload = {
            "type": "confirm_reschedule",
            "appointment_id": preview.get("appointment_id"),
            "new_time_iso": preview.get("proposed_time_iso")
        } if req_confirm else None

        prompt = [
            SystemMessage(content="You are the Appointment Specialist. Explain the proposed reschedule clearly to the patient and state that confirmation is required."),
            HumanMessage(content=f"Query: {query}\nReschedule Proposal: {json.dumps(preview)}")
        ]
        output = get_groq_llm().invoke(prompt).content.strip()

        return {
            "agent_output": output,
            "action_proposal": pending_payload,
            "requires_confirmation": req_confirm,
            "answer_type": "calculated"
        }
    else:
        # View upcoming appointments
        apts_raw = get_patient_appointments.invoke({"patient_id": patient_id})
        prompt = [
            SystemMessage(content="You are the Appointment Specialist. Summarize the patient's upcoming hospital appointments clearly."),
            HumanMessage(content=f"Query: {query}\nAppointments Data: {apts_raw}")
        ]
        output = get_groq_llm().invoke(prompt).content.strip()

        return {
            "agent_output": output,
            "action_proposal": None,
            "requires_confirmation": False,
            "answer_type": "calculated"
        }


# -------------------------------------------------------------------------
# 6. Lab & Readiness Node (Lab results & surgery checklist)
# -------------------------------------------------------------------------
def lab_readiness_node(state: HospitalAgentState) -> Dict[str, Any]:
    """Specialized LLM Agent for verified lab results and surgical clearance."""
    query = state.get("query", "")
    patient_id = state.get("patient_id") or "PAT-001"
    is_surgery = any(k in query.lower() for k in ["surgery", "ready", "readiness", "clearance", "cleared", "pre-op"])

    if is_surgery:
        data_raw = check_surgery_readiness.invoke({"patient_id": patient_id, "procedure_name": query})
    else:
        data_raw = get_patient_lab_results.invoke({"patient_id": patient_id, "test_name": query})

    prompt = [
        SystemMessage(content="You are the Clinical Lab & Pre-Op Specialist. Provide a clear, reassuring summary based strictly on the record. Do NOT formulate clinical medical diagnoses."),
        HumanMessage(content=f"Query: {query}\nClinical Record: {data_raw}")
    ]
    output = get_groq_llm().invoke(prompt).content.strip()

    return {
        "agent_output": output,
        "answer_type": "calculated"
    }


# -------------------------------------------------------------------------
# 7. Insurance Pre-Auth Node (CPT codes, prior-auth & copays)
# -------------------------------------------------------------------------
def insurance_node(state: HospitalAgentState) -> Dict[str, Any]:
    """Specialized LLM Agent for prior-authorizations, CPT codes, and copays."""
    query = state.get("query", "")
    rule_raw = check_insurance_preauth.invoke({"procedure_name": query})

    prompt = [
        SystemMessage(content="You are the Insurance & Prior-Authorization Specialist. Explain whether prior-auth is required, in-network rules, and copay clearly."),
        HumanMessage(content=f"Query: {query}\nInsurance Rule Data: {rule_raw}")
    ]
    output = get_groq_llm().invoke(prompt).content.strip()

    return {
        "agent_output": output,
        "answer_type": "calculated"
    }


# -------------------------------------------------------------------------
# 8. Safety Refusal Node (Guardrail against emergency advice)
# -------------------------------------------------------------------------
def refusal_node(state: HospitalAgentState) -> Dict[str, Any]:
    """Safety guardrail for emergency clinical questions or diagnostic requests."""
    msg = (
        "⚠️ **Clinical Scope Notice**:\n\n"
        "CareBridge AI can assist with hospital policies, appointments, lab results, "
        "and insurance rules. We cannot provide clinical diagnoses or emergency medical advice.\n\n"
        "If you are experiencing a medical emergency, please call **911** immediately or go to the nearest Emergency Room."
    )
    return {
        "final_response": msg,
        "answer_type": "refused"
    }


# -------------------------------------------------------------------------
# 9. Final Synthesis Node (Empathetic patient response)
# -------------------------------------------------------------------------
def synthesis_node(state: HospitalAgentState) -> Dict[str, Any]:
    """Final LLM Synthesizer produces the compassionate, grounded patient response."""
    query = state.get("query", "")
    output = state.get("agent_output", "")
    citations = state.get("citations", [])

    prompt = [
        SystemMessage(content="You are CareBridge AI, the compassionate hospital assistant. Format a warm, professional response based strictly on the findings and citations provided."),
        HumanMessage(content=f"User Query: {query}\nFindings:\n{output}\nCitations:\n{json.dumps(citations)}")
    ]
    try:
        final_text = get_groq_llm(temperature=0.1).invoke(prompt).content.strip()
    except Exception:
        final_text = output

    return {"final_response": final_text}


# -------------------------------------------------------------------------
# 10. LangGraph Assembly: Wire Nodes & Edges
# -------------------------------------------------------------------------
def build_carebridge_langgraph():
    """Create and compile the LangGraph StateGraph workflow."""
    workflow = StateGraph(HospitalAgentState)

    # 1. Add all nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("doc_rag", doc_rag_node)
    workflow.add_node("appointment", appointment_node)
    workflow.add_node("lab_readiness", lab_readiness_node)
    workflow.add_node("insurance", insurance_node)
    workflow.add_node("refusal", refusal_node)
    workflow.add_node("synthesis", synthesis_node)

    # 2. Add edges: START -> Supervisor -> Specialist -> Synthesis -> END
    workflow.add_edge(START, "supervisor")

    # Conditional edge routes from supervisor to the chosen agent
    workflow.add_conditional_edges("supervisor", lambda state: state.get("next_agent", "doc_rag"))

    # All sub-agents pass findings to synthesis
    workflow.add_edge("doc_rag", "synthesis")
    workflow.add_edge("appointment", "synthesis")
    workflow.add_edge("lab_readiness", "synthesis")
    workflow.add_edge("insurance", "synthesis")

    # End nodes
    workflow.add_edge("refusal", END)
    workflow.add_edge("synthesis", END)

    return workflow.compile()


# Compiled application ready for execution
carebridge_app = build_carebridge_langgraph()
