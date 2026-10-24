import streamlit as st
from typing import Dict, Optional, List
from core.models import UserSession, UserRole

# Registered system user accounts with Login IDs, Passwords, and Roles
REGISTERED_ACCOUNTS: Dict[str, Dict] = {
    "sarah_j": {
        "login_id": "sarah_j",
        "password": "password123",
        "name": "Sarah Jenkins",
        "role": UserRole.PATIENT,
        "patient_id": "PAT-001"
    },
    "robert_d": {
        "login_id": "robert_d",
        "password": "password123",
        "name": "Robert Davis",
        "role": UserRole.PATIENT,
        "patient_id": "PAT-002"
    },
    "nurse_emily": {
        "login_id": "nurse_emily",
        "password": "password123",
        "name": "Nurse Emily Taylor",
        "role": UserRole.STAFF,
        "patient_id": None
    },
    "admin_marcus": {
        "login_id": "admin_marcus",
        "password": "password123",
        "name": "Marcus Vance",
        "role": UserRole.ADMIN,
        "patient_id": None
    }
}

# Role-Based Page Access Matrix
ROLE_PERMISSIONS: Dict[UserRole, List[str]] = {
    UserRole.PATIENT: [
        "Patient Chat"
    ],
    UserRole.STAFF: [
        "Patient Chat",
        "Staff View",
        "Audit Viewer"
    ],
    UserRole.ADMIN: [
        "Patient Chat",
        "Staff View",
        "Admin Panel",
        "Audit Viewer"
    ]
}

def authenticate_user(login_id: str, password: str) -> Optional[UserSession]:
    """Validate credentials and return UserSession if successful."""
    clean_id = login_id.strip().lower()
    user_record = REGISTERED_ACCOUNTS.get(clean_id)
    if user_record and user_record["password"] == password:
        return UserSession(
            user_id=user_record["login_id"],
            name=user_record["name"],
            role=user_record["role"],
            patient_id=user_record["patient_id"]
        )
    return None

def enforce_patient_access(session: UserSession, target_patient_id: Optional[str]) -> str:
    """
    Enforces server-side patient binding.
    Rule: A patient user can NEVER access or specify a patient ID other than their bound one.
    """
    if session.role == UserRole.PATIENT:
        if not session.patient_id:
            raise PermissionError("Patient session is missing bound patient identifier.")
        return session.patient_id
    
    if target_patient_id:
        return target_patient_id
    if session.patient_id:
        return session.patient_id
    return ""

def enforce_page_access(page_name: str, allowed_roles: List[UserRole]) -> UserSession:
    """
    Streamlit page guard.
    Halts execution and shows an access-denied screen if user is unauthenticated
    or their role is not authorized to view the requested page.
    """
    # 1. Check Authentication
    if not st.session_state.get("authenticated", False) or "user_session" not in st.session_state:
        st.warning("⚠️ **Authentication Required**\nPlease log in with your Login ID at the home portal to access this hospital service.")
        if st.button("⬅️ Go to Login Portal", type="primary"):
            st.switch_page("app.py")
        st.stop()

    session: UserSession = st.session_state.user_session

    # 2. Render standard authenticated user badge in sidebar
    with st.sidebar:
        st.markdown(f"**Logged in as:** {session.name}")
        st.caption(f"Login ID: `{session.user_id}` | Role: `{session.role.value.upper()}`")
        if session.patient_id:
            st.caption(f"Bound Patient ID: `{session.patient_id}`")
        if st.button("🚪 Log Out", key=f"logout_{page_name}"):
            st.session_state.authenticated = False
            st.session_state.user_session = None
            st.session_state.messages = []
            st.switch_page("app.py")
        st.divider()

    # 3. Check Role Authorization
    if session.role not in allowed_roles:
        allowed_names = ", ".join(r.value.upper() for r in allowed_roles)
        st.error(f"🚫 **Access Denied — Restricted Workspace**")
        st.markdown(
            f"Your current account role (`{session.role.value.upper()}`) does not have permission "
            f"to view the **{page_name}** page.\n\n"
            f"*Authorized Roles for this page:* **{allowed_names}**"
        )
        st.info("Please navigate back to your permitted workspaces via the sidebar or home portal.")
        if st.button("⬅️ Return to Home"):
            st.switch_page("app.py")
        st.stop()

    return session
