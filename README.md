# Perspectives Health — Clinical Intelligence Platform

Extracts patient data from SimplePractice EMR, runs ASAM Level of Care assessments, and audits TJC compliance — all with citation-verified AI outputs.

## What It Does

1. **Data Extraction** — Playwright browser automation scrapes SimplePractice, extracts demographics, BPS assessments, and progress notes into structured JSON
2. **ASAM Level of Care** — Evaluates patients across all 6 ASAM dimensions (12 subdimensions) with an algorithmic flowchart (pp 279-281, 4th Edition) that overrides the LLM when subdimension ratings don't match the recommendation
3. **TJC Compliance Audit** — 8 parallel agents audit 41 standards and 104 EPs (verbatim from Joint Commission Public Standards Database, March 2026) with official 3-point scoring and SAFER matrix risk ratings
4. **QA Verification** — Every citation is fuzzy-matched against the source document. Hallucinated citations get flagged, fixed, or marked unsupported. The LLM's clinical reasoning is kept; its citations are verified deterministically

## Architecture

```
SimplePractice (Playwright) → Structured JSON → PostgreSQL
                                                    ↓
                                    ┌───────────────┴───────────────┐
                                    │                               │
                              ASAM Engine                     TJC Engine
                              (2-pass LLM +                   (8 parallel agents +
                               algorithmic                     coverage check +
                               flowchart)                      retry for gaps)
                                    │                               │
                                    └───────────────┬───────────────┘
                                                    ↓
                                              QA Agent Loop
                                         (decompose → verify →
                                          fix → reconstruct)
                                                    ↓
                                              Streaming UI
                                         (SSE with live tokens,
                                          linked evidence)
```

## Quick Start

```bash
cp .env.example .env
# Add your ANTHROPIC_API_KEY and SimplePractice credentials to .env

pip install -r requirements.txt
playwright install chromium

uvicorn app.main:app --reload
# Open http://localhost:8000
```

## Sample Outputs

- `samples/extraction_danielle.json` — Structured patient data
- `samples/asam_danielle.json` — ASAM evaluation (Level 2.7 COE + Recovery Residence, 100% citation accuracy)
- `samples/tjc_danielle.json` — TJC audit (41 standards, 104 EPs, 20.2% compliance, 98.3% citation accuracy)

## Key Files

| File                             | What it does                                                                                                     |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `app/services/asam_flowchart.py` | Rule-based LOC determination from official ASAM 4th Edition (pp 279-281) with dimension-aware risk code mappings |
| `app/prompts/tjc_sections.py`    | 41 TJC standards, 104 EPs — verbatim from Joint Commission database, split into 8 sections for parallel audit    |
| `app/services/qa_stream.py`      | Streaming orchestrator for both ASAM and TJC with agentic QA loop                                                |
| `app/services/qa_loop.py`        | Citation verification (RapidFuzz), negation detection, claim decomposition, self-healing fix loop                |
| `app/services/simplepractice.py` | Playwright browser automation for SimplePractice data extraction                                                 |

## Tech Stack

FastAPI, PostgreSQL/SQLite, Playwright, Claude API (Sonnet), RapidFuzz
