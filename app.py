import streamlit as st
from pathlib import Path
import config
from core.auth import authenticate_user, REGISTERED_ACCOUNTS, ROLE_PERMISSIONS
from core.models import UserRole, UserSession
from database.db import init_database
from data.seed_data import seed_database

st.set_page_config(
    page_title=f"{config.APP_NAME} — {config.HOSPITAL_NAME}",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_session" not in st.session_state:
    st.session_state.user_session = None

# ==============================================================================
# VIEW 1: LOGIN PORTAL (When not authenticated)
# ==============================================================================
if not st.session_state.authenticated:
    st.title("🏥 CareBridge AI — Hospital Portal Login")
    st.markdown(f"Welcome to **{config.HOSPITAL_NAME}** secure patient and staff services portal.")
    st.divider()

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("🔐 Sign In with your Login ID")
        login_id_input = st.text_input("Login ID:", placeholder="e.g. sarah_j, nurse_emily, admin_marcus")
        password_input = st.text_input("Password:", type="password", placeholder="Enter your password")

        if st.button("Log In", type="primary", use_container_width=True):
            session = authenticate_user(login_id_input, password_input)
            if session:
                st.session_state.authenticated = True
                st.session_state.user_session = session
                st.session_state.messages = []
                st.success(f"Welcome, {session.name}!")
                st.rerun()
            else:
                st.error("Invalid Login ID or Password. Check credentials or use quick-login below.")

    with col2:
        st.subheader("⚡ Quick Demo Logins")
        st.caption("Click any account to test role-based access immediately:")

        # Patient 1
        if st.button("👤 Log in as Patient: Sarah Jenkins (`sarah_j`)", use_container_width=True):
            st.session_state.authenticated = True
            st.session_state.user_session = authenticate_user("sarah_j", "password123")
            st.session_state.messages = []
            st.rerun()

        # Patient 2
        if st.button("👤 Log in as Patient: Robert Davis (`robert_d`)", use_container_width=True):
            st.session_state.authenticated = True
            st.session_state.user_session = authenticate_user("robert_d", "password123")
            st.session_state.messages = []
            st.rerun()

        # Staff
        if st.button("👨‍⚕️ Log in as Staff: Nurse Emily Taylor (`nurse_emily`)", use_container_width=True):
            st.session_state.authenticated = True
            st.session_state.user_session = authenticate_user("nurse_emily", "password123")
            st.session_state.messages = []
            st.rerun()

        # Admin
        if st.button("📋 Log in as Admin: Marcus Vance (`admin_marcus`)", use_container_width=True):
            st.session_state.authenticated = True
            st.session_state.user_session = authenticate_user("admin_marcus", "password123")
            st.session_state.messages = []
            st.rerun()

    st.divider()
    st.caption("Default password for all demo accounts: `password123`")
    st.stop()

# ==============================================================================
# VIEW 2: AUTHENTICATED DASHBOARD (Role-Based Workspace View)
# ==============================================================================
user: UserSession = st.session_state.get("user_session")
if user is not None:
    allowed_pages = ROLE_PERMISSIONS.get(user.role, [])

with st.sidebar:
    st.image("https://img.icons8.com/color/96/hospital-3.png", width=64)
    st.title("CareBridge AI")
    st.markdown(f"**{user.name}**")
    st.caption(f"Login ID: `{user.user_id}`\nRole: `{user.role.value.upper()}`")
    if user.patient_id:
        st.caption(f"Bound Patient ID: `{user.patient_id}`")

    if st.button("🚪 Log Out", type="secondary"):
        st.session_state.authenticated = False
        st.session_state.user_session = None
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.subheader("⚙️ System Status")
    st.write(f"**Database**: PostgreSQL")
    st.write(f"**Embeddings**: Hugging Face (`all-MiniLM-L6-v2`)")
    
    # Groq API Status & Configuration (https://groq.com)
    groq_active = bool(config.GROQ_API_KEY and not config.GROQ_API_KEY.startswith("gsk-your") and not config.GROQ_API_KEY.startswith("xai-your"))
    if groq_active:
        st.success(f"⚡ **Groq LPU Engine**: ACTIVE (`{config.GROQ_MODEL}`)")
    else:
        st.warning("⚠️ **Groq API Key Not Set**\n(Using Deterministic Fallback Mode)")
        with st.expander("🔑 Configure Groq API Key"):
            new_groq_key = st.text_input("Enter Groq API Key (gsk_...):", type="password", placeholder="gsk_...")
            if st.button("Save Groq Key", key="save_groq_btn"):
                if new_groq_key.strip():
                    config.save_groq_key(new_groq_key.strip())
                    st.success("Groq API Key saved to .env!")
                    st.rerun()

# Main Authenticated Home
st.title(f"🏥 CareBridge AI — Welcome, {user.name}")
role_badge = {
    UserRole.PATIENT: "🟢 Patient Portal",
    UserRole.STAFF: "🔵 Clinical Staff Coordination",
    UserRole.ADMIN: "🟣 Hospital Administration"
}.get(user.role, "")
st.markdown(f"### {role_badge}")

st.markdown(f"""
You are logged in as **{user.name}** (`{user.user_id}`). Based on your role (**{user.role.value.upper()}**),
you have access to the authorized hospital services shown below.
""")

st.divider()
st.subheader("📁 Your Authorized Workspaces")

cols = st.columns(len(allowed_pages) if allowed_pages else 1)

page_descriptions = {
    "Patient Chat": {
        "icon": "🏥",
        "file": "pages/1_🏥_Patient_Chat.py",
        "desc": "Ask hospital policy questions, check appointments & lab results, and review surgical readiness."
    },
    "Staff View": {
        "icon": "👨‍⚕️",
        "file": "pages/2_👨‍⚕️_Staff_View.py",
        "desc": "Review patient preparation rosters, verify clinical clearances, and search pre-auth rules."
    },
    "Admin Panel": {
        "icon": "📋",
        "file": "pages/3_📋_Admin_Panel.py",
        "desc": "Upload and vectorize hospital SOPs & policies (PDF/Markdown) into pgvector."
    },
    "Audit Viewer": {
        "icon": "🔍",
        "file": "pages/4_🔍_Audit_Viewer.py",
        "desc": "Inspect end-to-end trace logs, tool invocation telemetry, and audit compliance."
    }
}

for i, page_name in enumerate(allowed_pages):
    info = page_descriptions.get(page_name, {})
    with cols[i]:
        st.markdown(f"### {info.get('icon', '📄')} {page_name}")
        st.write(info.get('desc', ''))
        # Navigation button
        if st.button(f"Open {page_name}", key=f"open_page_{i}", type="primary"):
            st.switch_page(info.get('file', ''))

st.divider()

# Database Setup & Health Check
st.subheader("🛠️ Database Setup & Health Check")
col_a, col_b = st.columns([1, 2])

with col_a:
    if st.button("🚀 Initialize & Seed Database"):
        with st.spinner("Connecting to PostgreSQL and vectorizing hospital policies with Hugging Face..."):
            try:
                res = seed_database()
                if res:
                    st.success("Database schema initialized and seed data loaded successfully!")
                else:
                    st.error("Seeding encountered an issue. Check server logs.")
            except Exception as e:
                st.error(f"Database error: {e}")

with col_b:
    st.caption("""
    Initializes PostgreSQL tables, activates vector capabilities, and generates embeddings
    for hospital visitor policies, parking guidelines, and surgical checklists.
    """)
