import streamlit as st
from core.auth import enforce_page_access
from core.models import UserRole, AnswerType
from core.audit import get_recent_audit_logs

st.set_page_config(page_title="Audit Trail Viewer — CareBridge AI", page_icon="🔍", layout="wide")

# Role Guard: Only STAFF and ADMIN can view full audit logs
session = enforce_page_access("Audit Viewer", allowed_roles=[UserRole.STAFF, UserRole.ADMIN])

st.title("🔍 End-to-End Audit Trail & Traceability")
st.caption("Every user request, intent classification, tool decision, and response classification persisted in PostgreSQL.")

logs = get_recent_audit_logs(limit=100)

if not logs:
    st.info("No audit logs recorded yet. Query the Patient Services Assistant to generate traceable events.")
    st.stop()

# Summary Metrics
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Recorded Traces", len(logs))
with col2:
    write_actions = sum(1 for l in logs if l.answer_type == AnswerType.ACTION_COMPLETED)
    st.metric("State-Modifying Actions", write_actions)
with col3:
    fact_answers = sum(1 for l in logs if l.answer_type == AnswerType.RETRIEVED_FACT)
    st.metric("Grounded Fact Queries", fact_answers)
with col4:
    refusals = sum(1 for l in logs if l.answer_type == AnswerType.REFUSED)
    st.metric("Clinical Refusals / Guardrails", refusals)

st.divider()

# Filters
col_f1, col_f2 = st.columns(2)
with col_f1:
    role_filter = st.selectbox("Filter by User Role:", ["All", "patient", "staff", "admin"])
with col_f2:
    answer_filter = st.selectbox("Filter by Answer Type:", ["All"] + [e.value for e in AnswerType])

filtered_logs = logs
if role_filter != "All":
    filtered_logs = [l for l in filtered_logs if l.user_role == role_filter]
if answer_filter != "All":
    filtered_logs = [l for l in filtered_logs if l.answer_type.value == answer_filter]

st.markdown(f"Displaying **{len(filtered_logs)}** audit record(s):")

for entry in filtered_logs:
    badge_color = {
        "retrieved_fact": "blue",
        "calculated": "green",
        "action_completed": "purple",
        "clarification_needed": "orange",
        "not_found": "gray",
        "refused": "red",
        "conflict_flagged": "violet"
    }.get(entry.answer_type.value, "blue")

    with st.expander(
        f"Trace `{entry.trace_id}` — [{entry.user_role.upper()}] Query: \"{entry.query[:60]}...\" — :{badge_color}[{entry.answer_type.value.upper()}]"
    ):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"**Timestamp**: `{entry.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}`")
            st.markdown(f"**User ID**: `{entry.user_id}`")
            st.markdown(f"**Bound Patient ID**: `{entry.patient_id or 'None'}`")
            st.markdown(f"**Classified Intent**: `{entry.intent}`")
        with col_b:
            st.markdown(f"**Answer Type**: `{entry.answer_type.value}`")
            st.markdown(f"**Tools Invoked**: `{', '.join(entry.tools_invoked) if entry.tools_invoked else 'None'}`")

        st.markdown("**User Query:**")
        st.info(entry.query)

        st.markdown("**Response Summary / Persisted Output:**")
        st.write(entry.response_summary)
