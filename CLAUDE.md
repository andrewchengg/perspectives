# Perspectives Health - Clinical Intelligence Prototype

## Project Overview

Intern technical assessment for Perspectives Health. Build a prototype that:

1. Extracts patient data from SimplePractice EMR
2. Applies clinical logic for ASAM Level of Care estimation
3. Audits TJC (The Joint Commission) compliance

**Submission:** Code repo + sample JSON response to kyle@perspectiveshealth.ai and eshan@perspectiveshealth.ai

## Tech Stack

- **Backend:** FastAPI (Python)
- **Database:** PostgreSQL (preferred, but flexible)
- **UI:** Optional but nice to have
- **LLM:** Claude API for clinical intelligence (ASAM + TJC analysis)

## Project Structure

```
perspectives/
├── app/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Settings, env vars
│   ├── db/
│   │   ├── models.py            # SQLAlchemy/DB models
│   │   ├── database.py          # DB connection setup
│   │   └── seed.py              # Seed synthetic patient data
│   ├── api/
│   │   ├── routes/
│   │   │   ├── extraction.py    # Task 2: Data extraction endpoints
│   │   │   ├── asam.py          # Task 3 Endpoint 1: ASAM LoC prediction
│   │   │   └── tjc.py           # Task 3 Endpoint 2: TJC compliance audit
│   │   └── dependencies.py      # Shared deps (DB sessions, auth)
│   ├── services/
│   │   ├── simplepractice.py    # SimplePractice API client
│   │   ├── asam_engine.py       # ASAM 4th edition evaluation logic
│   │   └── tjc_engine.py        # TJC/CTS compliance audit logic
│   ├── schemas/
│   │   ├── patient.py           # Pydantic models for patient data
│   │   ├── asam.py              # Pydantic models for ASAM output
│   │   └── tjc.py               # Pydantic models for TJC output
│   └── prompts/
│       ├── asam_prompt.py       # LLM prompt templates for ASAM analysis
│       └── tjc_prompt.py        # LLM prompt templates for TJC audit
├── tests/
├── alembic/                     # DB migrations (if using PostgreSQL)
├── requirements.txt
├── .env.example
├── docker-compose.yml           # PostgreSQL + app
└── README.md
```

## Tasks Breakdown

### Task 1: Environment Setup & Data Generation

- Create SimplePractice sandbox account
- Create a single synthetic patient with:
  - **Admission Assessment:** Comprehensive Biopsychosocial (BPS) intake
    - History of present illness
    - Substance use history
    - Initial risk screening
  - **Progress Notes (3+, different dates, different formats):**
    - SOAP note (Subjective, Objective, Assessment, Plan)
    - DAP note (Data, Assessment, Plan)
    - DSAP note (Data, Subjective, Assessment, Plan)

### Task 2: Data Extraction API

- Build API that extracts from SimplePractice sandbox
- Output structured JSON containing:
  - Patient demographic data
  - Full text of initial assessment
  - Timeline-ordered progress notes with metadata (date, author, type)

### Task 3: Clinical Intelligence Endpoints

#### Endpoint 1: ASAM Level of Care Prediction

- Evaluate patient across the **6 ASAM Dimensions** (4th edition):
  1. Acute Intoxication / Withdrawal Potential
  2. Biomedical Conditions and Complications
  3. Emotional, Behavioral, or Cognitive Conditions
  4. Readiness to Change
  5. Relapse, Continued Use, or Continued Problem Potential
  6. Recovery/Living Environment
- Output a recommended Level of Care (e.g., 0.5, 1.0, 2.1, 2.5, 3.1, 3.5, 3.7, 4.0)
- Include per-dimension risk ratings and rationale citing specific note text

#### Endpoint 2: TJC Compliance Audit

- Audit against Joint Commission CTS (Care, Treatment, Services) standards for behavioral health
- Key standard areas: CTS.01 through CTS.05 (screening, assessment, planning, provision, coordination)
- Output per-standard compliance status with rationale referencing specific documentation gaps
- Example: "Standard CTS.02.02.01 EP2 failed because spiritual orientation was not documented"

## Domain Knowledge Reference

### ASAM Criteria (4th Edition)

- American Society of Addiction Medicine multidimensional assessment
- Used to determine appropriate level of care for substance use disorders
- Levels range from 0.5 (Early Intervention) to 4.0 (Medically Managed Intensive Inpatient)
- Key levels: 1.0 (Outpatient), 2.1 (Intensive Outpatient), 2.5 (Partial Hospitalization), 3.1 (Clinically Managed Low-Intensity Residential), 3.5 (Clinically Managed High-Intensity Residential), 3.7 (Medically Monitored Intensive Inpatient), 4.0 (Medically Managed)

### TJC CTS Standards (Behavioral Health)

- CTS.01: Screening and assessment requirements
- CTS.02: Comprehensive assessment (biopsychosocial, spiritual, cultural, strengths-based)
- CTS.03: Treatment planning (individualized, measurable goals, patient involvement)
- CTS.04: Provision of care (evidence-based interventions, progress monitoring)
- CTS.05: Coordination and continuity of care (discharge planning, referrals)

### SimplePractice API

- RESTful API for EMR data access
- Sandbox available for development
- Key endpoints: clients, appointments, treatment notes, documents
- OAuth2 authentication

## Evaluation Criteria

1. **Extraction Accuracy:** Capture all relevant clinical fields from SimplePractice forms
2. **Rationale Quality:** Not just Yes/No — cite specific text from notes (e.g., "Standard CTS.02.02.01 EP2 failed because spiritual orientation was not documented")
3. **ASAM Consistency:** Predicted Level of Care must be logically supported by dimension risk ratings

## Key Conventions

- Use Pydantic models for all request/response schemas
- All clinical logic must include text-level citations from source documents
- Use environment variables for all secrets (API keys, DB credentials)
- Write async endpoints where possible
- Keep clinical reasoning transparent and auditable — no black-box outputs

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload

# Run tests
pytest

# Database migrations (if using alembic)
alembic upgrade head
```

## Environment Variables (.env)

```
DATABASE_URL=postgresql://user:pass@localhost:5432/perspectives
SIMPLEPRACTICE_CLIENT_ID=
SIMPLEPRACTICE_CLIENT_SECRET=
SIMPLEPRACTICE_SANDBOX_URL=
ANTHROPIC_API_KEY=
```
