import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Ensure parent directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_db, init_database
from database.models import Patient, Appointment, LabResult, InsuranceRule, AppUser
from tools.document_ingestion import ingest_policy_document
import config

def seed_database():
    """Seed synthetic patients, users, appointments, lab results, insurance rules, and policy vectors."""
    print("Step 1: Initializing PostgreSQL database & vector capabilities...")
    success, msg = init_database()
    if not success:
        print(f"Database initialization failed: {msg}")
        return False

    print("Step 2: Seeding synthetic operational, patient, and user records...")
    with get_db() as db:
        # Seed App Users
        if db.query(AppUser).count() == 0:
            users = [
                AppUser(
                    login_id="sarah_j",
                    password_hash="password123",
                    full_name="Sarah Jenkins",
                    role="patient",
                    patient_id="PAT-001"
                ),
                AppUser(
                    login_id="robert_d",
                    password_hash="password123",
                    full_name="Robert Davis",
                    role="patient",
                    patient_id="PAT-002"
                ),
                AppUser(
                    login_id="nurse_emily",
                    password_hash="password123",
                    full_name="Nurse Emily Taylor",
                    role="staff",
                    patient_id=None
                ),
                AppUser(
                    login_id="admin_marcus",
                    password_hash="password123",
                    full_name="Marcus Vance",
                    role="admin",
                    patient_id=None
                )
            ]
            db.add_all(users)
            db.flush()

        # Check if patients already exist
        if db.query(Patient).count() > 0:
            print("Patients already exist in PostgreSQL. Checking policies...")
        else:
            # 1. Patients
            patients = [
                Patient(
                    patient_id="PAT-001",
                    full_name="Sarah Jenkins",
                    date_of_birth="1984-06-12",
                    phone="(555) 234-8910",
                    insurance_provider="Blue Cross Blue Shield",
                    insurance_policy_number="BCBS-8839210",
                    assigned_doctor="Dr. Marcus Thorne (Cardiology)"
                ),
                Patient(
                    patient_id="PAT-002",
                    full_name="Robert Davis",
                    date_of_birth="1968-11-23",
                    phone="(555) 872-4419",
                    insurance_provider="Aetna Health Advantage",
                    insurance_policy_number="AET-4920194",
                    assigned_doctor="Dr. Claire Rodriguez (Orthopedics)"
                )
            ]
            db.add_all(patients)
            db.flush()

            # 2. Appointments
            now = datetime.utcnow()
            appointments = [
                Appointment(
                    appointment_id="APT-1001",
                    patient_id="PAT-001",
                    department="Cardiology Clinic",
                    doctor_name="Dr. Marcus Thorne",
                    scheduled_time=now + timedelta(days=3, hours=2),
                    status="SCHEDULED",
                    reason="Routine echocardiogram follow-up and blood pressure check."
                ),
                Appointment(
                    appointment_id="APT-1002",
                    patient_id="PAT-002",
                    department="Orthopedic Surgery Center",
                    doctor_name="Dr. Claire Rodriguez",
                    scheduled_time=now + timedelta(days=2, hours=4),
                    status="SCHEDULED",
                    reason="Pre-operative evaluation for right knee arthroscopy."
                )
            ]
            db.add_all(appointments)

            # 3. Lab Results
            labs = [
                # Sarah Jenkins
                LabResult(
                    lab_id="LAB-301",
                    patient_id="PAT-001",
                    test_name="Complete Blood Count (CBC)",
                    value="7.4",
                    unit="x10^3/uL",
                    reference_range="4.5 - 11.0",
                    status="NORMAL",
                    result_date=now - timedelta(days=5),
                    physician_notes="White blood count and differential are normal."
                ),
                LabResult(
                    lab_id="LAB-302",
                    patient_id="PAT-001",
                    test_name="Lipid Panel - LDL",
                    value="138",
                    unit="mg/dL",
                    reference_range="< 100",
                    status="ABNORMAL",
                    result_date=now - timedelta(days=5),
                    physician_notes="Mildly elevated LDL cholesterol. Dietary counseling recommended."
                ),
                LabResult(
                    lab_id="LAB-303",
                    patient_id="PAT-001",
                    test_name="Comprehensive Metabolic Panel",
                    value="140",
                    unit="mEq/L",
                    reference_range="135 - 145",
                    status="NORMAL",
                    result_date=now - timedelta(days=5),
                    physician_notes="Normal electrolyte and kidney function."
                ),
                # Robert Davis
                LabResult(
                    lab_id="LAB-401",
                    patient_id="PAT-002",
                    test_name="Complete Blood Count (CBC)",
                    value="6.9",
                    unit="x10^3/uL",
                    reference_range="4.5 - 11.0",
                    status="NORMAL",
                    result_date=now - timedelta(days=3),
                    physician_notes="Within normal limits. Hemoglobin 14.8 g/dL."
                ),
                LabResult(
                    lab_id="LAB-402",
                    patient_id="PAT-002",
                    test_name="Coagulation PT/INR",
                    value="1.05",
                    unit="INR",
                    reference_range="0.9 - 1.2",
                    status="NORMAL",
                    result_date=now - timedelta(days=3),
                    physician_notes="Coagulation normal. Cleared for surgical intervention."
                )
            ]
            db.add_all(labs)

            # 4. Insurance Pre-Auth Rules
            rules = [
                InsuranceRule(
                    procedure_code="29881",
                    procedure_name="Knee Arthroscopy with Meniscectomy",
                    requires_preauth=True,
                    in_network_only=True,
                    estimated_copay=150.0,
                    criteria="Requires documented 6 weeks of conservative therapy (PT/NSAIDs) + MRI confirming meniscal pathology.",
                    notes="Pre-auth review turnaround is typically 48-72 business hours."
                ),
                InsuranceRule(
                    procedure_code="70553",
                    procedure_name="Brain MRI (with and without contrast)",
                    requires_preauth=True,
                    in_network_only=True,
                    estimated_copay=85.0,
                    criteria="Neurological deficit documentation or refractory severe headache resistant to first-line therapy.",
                    notes="Prior authorization valid for 90 days from date of issuance."
                ),
                InsuranceRule(
                    procedure_code="45378",
                    procedure_name="Preventive Screening Colonoscopy",
                    requires_preauth=False,
                    in_network_only=True,
                    estimated_copay=0.0,
                    criteria="Standard preventive colorectal cancer screening for average risk patients age 45+.",
                    notes="100% covered with zero patient cost-share under ACA guidelines."
                ),
                InsuranceRule(
                    procedure_code="66984",
                    procedure_name="Extracapsular Cataract Extraction with IOL",
                    requires_preauth=False,
                    in_network_only=True,
                    estimated_copay=175.0,
                    criteria="Visual impairment worse than 20/40 impacting daily activities (driving, reading).",
                    notes="Pre-clearance required if premium multifocal intraocular lens requested."
                ),
                InsuranceRule(
                    procedure_code="93458",
                    procedure_name="Left Heart Catheterization with Coronary Angiogram",
                    requires_preauth=True,
                    in_network_only=True,
                    estimated_copay=250.0,
                    criteria="Positive treadmill stress test or unstable angina refractory to medication.",
                    notes="Emergency catheterizations bypass pre-auth with post-service notification."
                )
            ]
            db.add_all(rules)
            db.commit()
            print("Synthetic patients, appointments, labs, and insurance rules seeded successfully.")

    print("Step 3: Ingesting hospital policies and generating Hugging Face pgvector embeddings...")
    policy_files = [
        ("visitor_policy.md", "POL-VIS-001", "Metro General Hospital Visitor Guidelines & Hours", "v2.1"),
        ("parking_transport.md", "POL-TRN-002", "Metro General Hospital Parking & Transportation Policy", "v1.4"),
        ("discharge_readiness.md", "POL-DIS-003", "Metro General Hospital Patient Discharge & Surgery Readiness", "v3.0")
    ]

    for filename, code, title, ver in policy_files:
        filepath = config.POLICIES_DIR / filename
        if filepath.exists():
            res = ingest_policy_document(filepath, code, title, ver)
            print(f" - Ingested {code}: {res.get('chunks_count', 0)} chunks vectorized.")
        else:
            print(f" - File not found: {filepath}")

    print("\n[SUCCESS] CareBridge AI seeding completed successfully!")
    return True

if __name__ == "__main__":
    seed_database()
