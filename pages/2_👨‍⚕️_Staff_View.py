import streamlit as st
from core.auth import enforce_page_access
from core.models import UserRole
from database.db import get_db
from database.models import Patient
from tools.appointments import get_patient_appointments
from tools.lab_results import get_patient_lab_results
from tools.readiness import evaluate_patient_readiness
from tools.insurance import check_procedure_preauth

st.set_page_config(page_title="Staff Coordination View — CareBridge AI", page_icon="👨‍⚕️", layout="wide")

# Role Guard: Only STAFF and ADMIN can view Staff Coordination View
session = enforce_page_access("Staff View", allowed_roles=[UserRole.STAFF, UserRole.ADMIN])

st.title("👨‍⚕️ Care Coordinator & Staff View")
st.caption("Operational visibility across patient preparation, appointments, and laboratory clearances.")

# Fetch patients list from PostgreSQL
try:
    with get_db() as db:
        patients = db.query(Patient).all()
        patient_map = {f"{p.patient_id} — {p.full_name}": p.patient_id for p in patients}
except Exception as e:
    st.error(f"Could not connect to database: {e}. Please ensure database is seeded.")
    st.stop()

if not patient_map:
    st.warning("No patient records found in PostgreSQL. Please initialize and seed the database from the Home page.")
    st.stop()

selected_label = st.selectbox("Select Patient to Review:", options=list(patient_map.keys()))
selected_patient_id = patient_map[selected_label]

with get_db() as db:
    patient = db.query(Patient).filter(Patient.patient_id == selected_patient_id).first()

# Patient Overview Header
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Patient ID", patient.patient_id)
with col2:
    st.metric("DOB", patient.date_of_birth)
with col3:
    st.metric("Primary Care / Attending", patient.assigned_doctor.split("(")[0])
with col4:
    st.metric("Insurance", patient.insurance_provider)

st.divider()

# Tabbed Detail View
tab1, tab2, tab3, tab4 = st.tabs([
    "🩺 Surgical & Procedure Readiness",
    "📅 Appointments Schedule",
    "🧪 Verified Lab Results",
    "🛡️ Insurance Pre-Auth Rules"
])

with tab1:
    st.subheader("Clinical Procedure Readiness Evaluation")
    readiness = evaluate_patient_readiness(selected_patient_id)
    
    if readiness["is_ready"]:
        st.success(f"✅ Patient is **CLEARED & READY** for {readiness['procedure_name']}")
    else:
        st.error(f"⚠️ **READINESS DEFICIT DETECTED** for {readiness['procedure_name']}")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("##### Completed Clearances:")
        if readiness["completed_items"]:
            for item in readiness["completed_items"]:
                st.write(f"- ✅ {item}")
        else:
            st.write("None recorded.")

    with col_b:
        st.markdown("##### Outstanding / Missing Items:")
        if readiness["missing_items"]:
            for item in readiness["missing_items"]:
                st.write(f"- ❌ **{item}**")
        else:
            st.write("None! All pre-op requirements satisfied.")

    st.markdown("##### Patient Preparation Instructions:")
    for ins in readiness["instructions"]:
        st.info(f"ℹ️ {ins}")

with tab2:
    st.subheader("Scheduled Appointments")
    apts = get_patient_appointments(selected_patient_id)
    if apts:
        for a in apts:
            with st.container():
                st.markdown(f"**{a['department']}** with **{a['doctor_name']}**")
                st.caption(f"Time: `{a['scheduled_time']}` | Status: `{a['status']}`")
                if a.get("reason"):
                    st.write(f"*Clinical Reason*: {a['reason']}")
                st.divider()
    else:
        st.info("No scheduled appointments on file for this patient.")

with tab3:
    st.subheader("Verified Laboratory & Diagnostic Results")
    labs = get_patient_lab_results(selected_patient_id)
    if labs:
        for l in labs:
            status_color = "red" if l["status"] in ["ABNORMAL", "CRITICAL"] else "green"
            st.markdown(f"**{l['test_name']}**: `{l['value']} {l['unit']}` (Ref: {l['reference_range']}) — :{status_color}[**{l['status']}**]")
            st.caption(f"Date: {l['result_date']}")
            if l.get("physician_notes"):
                st.write(f"Physician Note: *{l['physician_notes']}*")
            st.divider()
    else:
        st.info("No verified lab results on file.")

with tab4:
    st.subheader("Hospital Procedure Pre-Authorization Engine")
    proc_search = st.text_input("Look up procedure requirement (e.g. Knee Arthroscopy, MRI, Colonoscopy):", value="Knee Arthroscopy")
    if proc_search:
        rule = check_procedure_preauth(proc_search)
        if rule:
            st.markdown(f"### {rule['procedure_name']} (`CPT: {rule['procedure_code']}`)")
            col_x, col_y, col_z = st.columns(3)
            with col_x:
                st.metric("Prior Authorization Required", "YES" if rule["requires_preauth"] else "NO")
            with col_y:
                st.metric("In-Network Only", "YES" if rule["in_network_only"] else "NO")
            with col_z:
                st.metric("Estimated Copay", f"${rule['estimated_copay']:.2f}")
            st.markdown(f"**Clinical Documentation Criteria:**\n{rule['criteria']}")
            if rule.get("notes"):
                st.caption(f"Policy Note: {rule['notes']}")
        else:
            st.warning("No specific insurance rule found for this procedure search.")
