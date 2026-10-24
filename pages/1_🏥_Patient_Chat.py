import streamlit as st
from core.auth import enforce_page_access
from core.models import UserRole, AnswerType
from core.orchestrator import CareBridgeOrchestrator

st.set_page_config(page_title="Patient Chat — CareBridge AI", page_icon="🏥", layout="wide")

# Role Guard: Patient, Staff, and Admin can access Patient Chat
session = enforce_page_access("Patient Chat", allowed_roles=[UserRole.PATIENT, UserRole.STAFF, UserRole.ADMIN])

st.title("🏥 Patient Services Assistant")
st.caption(f"Authenticated as **{session.name}** (`{session.role.value.upper()}` | Patient ID: `{session.patient_id or 'Staff Context'}`)")

# Sample Prompt Chips
st.markdown("**Suggested Quick Inquiries:**")
col1, col2, col3, col4 = st.columns(4)
query_to_send = None

with col1:
    if st.button("🕒 ICU Visiting Hours"):
        query_to_send = "What are the visiting hours for the Intensive Care Unit (ICU)?"
with col2:
    if st.button("📅 My Upcoming Appointment"):
        query_to_send = "When is my next scheduled appointment?"
with col3:
    if st.button("🧪 Recent Lab Results"):
        query_to_send = "Can you show me my recent verified lab results?"
with col4:
    if st.button("🛡️ Knee Surgery Pre-Auth"):
        query_to_send = "Does knee arthroscopy require insurance prior authorization?"

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display conversation history
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        # Display response metadata if available
        if "meta" in msg:
            meta = msg["meta"]
            
            badge_color = {
                "retrieved_fact": "blue",
                "calculated": "green",
                "action_completed": "purple",
                "clarification_needed": "orange",
                "not_found": "gray",
                "refused": "red",
                "conflict_flagged": "violet"
            }.get(meta.get("answer_type", ""), "blue")
            
            st.caption(
                f":{badge_color}[● {meta.get('answer_type', '').upper()}] | "
                f"Trace ID: `{meta.get('trace_id', '')}`"
            )

            # Groq Multi-Agent Supervisor Trace
            target_agent = meta.get("target_agent")
            supervisor_reasoning = meta.get("supervisor_reasoning")
            if target_agent:
                with st.expander(f"⚡ Groq Supervisor Agent Routing: `{target_agent}`"):
                    st.markdown(f"**Delegated Sub-Agent:** `{target_agent}`")
                    if supervisor_reasoning:
                        st.markdown(f"**Groq Planning Rationale:** *{supervisor_reasoning}*")

            # Display Grounded Citations
            citations = meta.get("citations", [])
            if citations:
                with st.expander(f"📚 Grounded Citations ({len(citations)} verified sources)"):
                    for c in citations:
                        st.markdown(f"**{c.get('title')}** (`{c.get('source_id')}`, {c.get('version')})")
                        if c.get("section"):
                            st.caption(f"Section: *{c.get('section')}* | Similarity: {c.get('similarity_score', 0):.2f}")
                        st.info(f"\"{c.get('text_snippet')}\"")

        # Two-step Confirmation UI for Pending Write Actions
        if msg.get("requires_confirmation") and msg.get("pending_payload"):
            payload = msg["pending_payload"]
            st.warning("⚠️ **Explicit User Confirmation Required**")
            col_conf_1, col_conf_2 = st.columns([1, 4])
            with col_conf_1:
                if st.button("✅ Confirm Reschedule", key=f"confirm_{idx}", type="primary"):
                    orchestrator = CareBridgeOrchestrator()
                    with st.spinner("Executing update in hospital database..."):
                        confirm_res = orchestrator.process_request(
                            query="Confirmed reschedule",
                            session=session,
                            confirmation_action=payload
                        )
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": confirm_res.text,
                            "meta": {
                                "answer_type": confirm_res.answer_type.value,
                                "trace_id": confirm_res.trace_id
                            }
                        })
                        msg["requires_confirmation"] = False
                        st.rerun()

# User Input Box
chat_input = st.chat_input("Ask a question about visiting rules, your appointments, lab results, or hospital policies...")
actual_input = query_to_send or chat_input

if actual_input:
    st.session_state.messages.append({"role": "user", "content": actual_input})
    with st.chat_message("user"):
        st.markdown(actual_input)

    orchestrator = CareBridgeOrchestrator()
    with st.chat_message("assistant"):
        with st.spinner("CareBridge AI is reviewing hospital records and grounded SOPs..."):
            response = orchestrator.process_request(
                query=actual_input,
                session=session,
                chat_history=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[:-1]]
            )

            st.markdown(response.text)

            msg_data = {
                "role": "assistant",
                "content": response.text,
                "requires_confirmation": response.requires_confirmation,
                "pending_payload": response.pending_action_payload,
                "meta": {
                    "answer_type": response.answer_type.value,
                    "trace_id": response.trace_id,
                    "target_agent": (response.action_details or {}).get("target_agent"),
                    "supervisor_reasoning": (response.action_details or {}).get("supervisor_reasoning"),
                    "citations": [c.dict() for c in response.citations]
                }
            }
            st.session_state.messages.append(msg_data)
            st.rerun()
