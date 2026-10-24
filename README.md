# CareBridge AI: Multi-Agent Hospital Operations Assistant

CareBridge AI coordinates hospital services, policy search, appointment scheduling, and surgical readiness using a LangGraph multi-agent workflow. The system connects to Groq for model inference, Hugging Face `sentence-transformers` for document vectorization, and PostgreSQL with pgvector (or local SQLite) for relational and vector storage.

## Architecture

The application separates routing, specialized execution, and response synthesis into discrete graph nodes.

```
User Query
    │
    ▼
[Supervisor Node] (ChatGroq router with structured output)
    │
    ├──► [doc_rag]          ──► search_hospital_policies
    ├──► [appointment]      ──► get_patient_appointments, preview_appointment_reschedule
    ├──► [lab_readiness]    ──► get_patient_lab_results, check_surgery_readiness
    ├──► [insurance]        ──► check_insurance_preauth
    └──► [refusal]          ──► clinical diagnostic guardrail
    │
    ▼
[Synthesis Node] (ChatGroq response formatter with policy citations)
    │
    ▼
Final Patient/Staff Response
```

### LangGraph Workflow

The workflow is defined in `core/multi_agent.py` using `langgraph.graph.StateGraph`:

1. **Supervisor Router**: A `ChatGroq` model with structured output (`SupervisorRoute`) inspects the incoming user query and selects the next agent (`doc_rag`, `appointment`, `lab_readiness`, `insurance`, or `refusal`).
2. **Specialist Agents**: Each specialist runs an LLM call bound to specific LangChain `@tool` functions:
   - Policy RAG: queries 384-dimensional chunk embeddings stored in the vector database.
   - Appointments: inspects existing appointments and generates two-step reschedule previews.
   - Clinical Verification: retrieves lab panels and evaluates surgical readiness against hospital criteria.
   - Insurance: checks CPT code requirements and estimates out-of-pocket copays.
   - Clinical Refusal: rejects diagnostic or treatment requests, advising users to contact an on-duty physician.
3. **Synthesis Node**: Takes the specialist output and tool observations, formats the final message, and attaches source citations with document IDs and section titles.

### Tools

All agent tools are defined in `core/hospital_tools.py` using the standard LangChain `@tool` decorator:

- `search_hospital_policies(query: str)`: Searches policy chunks using vector similarity.
- `get_patient_appointments(patient_id: str)`: Returns scheduled visits for the authenticated patient.
- `preview_appointment_reschedule(appointment_id: str, new_slot: str)`: Previews a schedule change and requires explicit patient confirmation before applying it.
- `get_patient_lab_results(patient_id: str, test_name: str)`: Looks up lab records with flag statuses (`NORMAL`, `ABNORMAL`, `CRITICAL`).
- `check_surgery_readiness(patient_id: str, procedure_name: str)`: Evaluates lab clearance, cardiac clearance, and pre-op fasting compliance.
- `check_insurance_preauth(payer_id: str, cpt_code: str)`: Returns prior-authorization requirements and estimated copay amounts.

## Storage and Vector Search

The data layer uses SQLAlchemy with PostgreSQL and the `pgvector` extension. When PostgreSQL is unavailable or `pgvector` is not compiled, the system automatically falls back to a local SQLite database (`carebridge_local.db`).

- Document text is split into chunks of 500 characters with 50-character overlap using LangChain `RecursiveCharacterTextSplitter`.
- Chunks are vectorized using `sentence-transformers/all-MiniLM-L6-v2`, producing 384-dimensional dense vectors.
- On PostgreSQL, `tools/knowledge_search.py` executes similarity searches using the built-in `<=>` cosine distance operator (`PolicyChunk.embedding.cosine_distance(query_vector)`).
- On SQLite, search calculates vector dot products directly in Python.

## Authentication and Role-Based Access

The application implements role-based page guards in `core/auth.py`.

| Role | Username | Password | Scope | Accessible Pages |
|---|---|---|---|---|
| Patient | `sarah_j` | `password123` | Patient `PAT-001` | Patient Chat |
| Patient | `robert_d` | `password123` | Patient `PAT-002` | Patient Chat |
| Staff | `nurse_emily` | `password123` | Hospital-wide | Patient Chat, Staff View, Audit Viewer |
| Admin | `admin_marcus` | `password123` | System-wide | Patient Chat, Staff View, Admin Panel, Audit Viewer |

Patients can only view and modify their own appointments and lab records. If an authenticated user enters an unauthorized URL or page, the application halts rendering and displays an access restriction warning.

## Repository Layout

```
carebridge-ai/
├── app.py                      # Main Streamlit entrypoint and authentication
├── config.py                   # Environment configuration loader
├── docker-compose.yml          # PostgreSQL 16 container definition with pgvector
├── requirements.txt            # Python dependencies
├── core/
│   ├── auth.py                 # User authentication and session verification
│   ├── audit.py                # Audit trail logger for compliance tracking
│   ├── config.py               # Core application settings
│   ├── hospital_tools.py       # LangChain @tool definitions for agents
│   ├── models.py               # Pydantic data schemas
│   ├── multi_agent.py          # LangGraph StateGraph, supervisor, and nodes
│   └── orchestrator.py         # Interface between Streamlit and LangGraph
├── database/
│   ├── db.py                   # SQLAlchemy engine and session factory
│   └── models.py               # ORM models (Patients, Appointments, Labs, Policies)
├── data/
│   ├── seed_data.py            # Database initialization and policy vectorizer
│   └── policies/               # Markdown hospital standard operating procedures
├── pages/
│   ├── 1_🏥_Patient_Chat.py    # Patient chat interface with citations
│   ├── 2_👨‍⚕️_Staff_View.py      # Staff procedure readiness and appointment roster
│   ├── 3_📋_Admin_Panel.py     # Document ingestion and chunking interface
│   └── 4_🔍_Audit_Viewer.py    # Audit log viewer
└── tools/
    ├── appointments.py         # Appointment lookup and reschedule logic
    ├── document_ingestion.py   # Document parsing and chunk storage
    ├── insurance.py            # CPT code and copay lookup
    ├── knowledge_search.py     # 384-dimensional vector similarity search
    ├── lab_results.py          # Lab record queries
    └── readiness.py            # Surgical checklist scoring engine
```

## Setup and Installation

### 1. Environment Setup

Python 3.10 or newer is required.

```bash
git clone https://github.com/your-username/carebridge-ai.git
cd carebridge-ai

python -m venv .venv

# Windows
.\.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configuration

Copy the example environment file and set your Groq API key:

```bash
cp .env.example .env
```

Edit `.env`:

```ini
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_BASE_URL=https://api.groq.com
GROQ_MODEL=openai/gpt-oss-120b

DATABASE_URL=postgresql://postgres:postgres@localhost:5432/carebridge

EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIM=384

APP_NAME=CareBridge AI
HOSPITAL_NAME=Metro General Hospital
```

If you do not have a running PostgreSQL instance, leave `DATABASE_URL` as is; the system will log a connection notice and use the included SQLite database.

### 3. Optional Database Setup with Docker

To run PostgreSQL with `pgvector` locally:

```bash
docker-compose up -d
```

### 4. Initialize Database and Ingest Policies

Run the seed script to create database tables, insert synthetic patient records, and vectorize the default hospital policies:

```bash
python data/seed_data.py
```

Expected output:
- Ingested `POL-VIS-001` (ICU and General Ward Visiting Hours): 5 chunks.
- Ingested `POL-TRN-002` (Non-Emergency Medical Transportation): 3 chunks.
- Ingested `POL-DIS-003` (Discharge and Post-Operative Care): 6 chunks.
- Seeded test patients, appointments, lab results, and insurance policies.

### 5. Run the Application

Start the Streamlit interface:

```bash
streamlit run app.py
```

The application runs at `http://localhost:8501`.

## Verification and Testing

To execute automated tests across the multi-agent graph, authentication checks, and tool executions:

```bash
pytest tests/ -v
```
