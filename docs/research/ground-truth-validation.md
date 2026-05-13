# Ground Truth & Validation Research

## How Accurate Can ASAM and TJC Evaluations Be?

This document compiles research on the accuracy, reliability, and limitations of
ASAM Level of Care determinations and TJC CTS compliance auditing — by both
humans and automated systems.

---

## 1. ASAM Inter-Rater Reliability

**There is no gold standard for ASAM placement. Even clinicians disagree frequently.**

| Metric                                            | Value                           | Source                  |
| ------------------------------------------------- | ------------------------------- | ----------------------- |
| ICC with structured computerized tool (4 raters)  | **0.77**                        | Baker & Gastfriend 2003 |
| Clinician-algorithm agreement rate                | **42%**                         | Staines et al. 2003     |
| Clinician-algorithm disagreement rate             | **58%**                         | Staines et al. 2003     |
| Algorithm recommends higher care in disagreements | **81%**                         | Staines et al. 2003     |
| Real-world match rate                             | **72% matched, 28% mismatched** | Kosanke et al. 2002     |
| Patients not fitting any ASAM level               | **13%**                         | Morey 1995              |
| ASAM CONTINUUM software ICC                       | **0.77**                        | ASAM                    |

### Key Studies

**Baker & Gastfriend (2003)** — _Journal of Addictive Diseases_, 22 Suppl 1, 45-60

- 4 blind raters scored videotaped assessments of 8 substance-dependent adults
- ICC of 0.77 was achieved ONLY with a computerized structured interview
- Without structured tools, no published reliability data exists
- The fact that researchers had to build specialized instruments to reach 0.77
  strongly implies unaided inter-rater reliability is substantially lower

**Staines et al. (2003)** — _Journal of Addictive Diseases_, 22 Suppl 1, 61-77

- N=248 cases comparing computer algorithm vs. standard clinical assessment
- Only 42% agreement; 58% disagreement
- In 81% of disagreements, algorithm recommended MORE intensive care
- Sources of discrepancy: clinicians' reasoned departures from rules, algorithm
  conservatism, measurement overlap between dimensions

**Kosanke et al. (2002)** — _American Journal on Addictions_, 11(2), 124-134

- N=281 alcoholism treatment applicants
- 72% were placed at matched LOC, 28% mismatched
- Of mismatched: 59% overtreated, 41% undertreated
- Top overtreatment reason: Medicaid covered inpatient (93%)
- Top undertreatment reason: work schedule conflicts (72%)

---

## 2. ASAM Placement Outcomes (Does Matching Matter?)

**Undertreatment leads to worse outcomes. Overtreatment doesn't improve them.**

| Study                      | N          | Key Finding                                                   |
| -------------------------- | ---------- | ------------------------------------------------------------- |
| Sharon et al. 2003         | 95         | Mismatched patients used **~2x hospital bed-days**            |
| Magura et al. 2003         | 248        | Undertreatment predicted **poorer drinking outcomes**         |
| Stallvik & Gastfriend 2014 | Multi-site | Matched patients had **better 3-month outcomes**              |
| McKay et al. 1992/1997     | —          | **No differences** between matched/mismatched (contradictory) |
| Witbrodt et al. 2007       | 696        | No significant difference between day hospital vs residential |

**Sharon et al. (2003)** — _Journal of Addictive Diseases_, 22 Suppl 1, 79-93

- 95 U.S. veterans all assigned to residential rehab
- Blindly assessed with computerized ASAM criteria
- Patients mismatched to a LESSER level used nearly 2x hospital bed-days
- F(2,92) = 3.88, p < .05

**Magura et al. (2003)** — _American Journal on Addictions_, 12(5), 386-397

- N=248 across inpatient, IOP, and regular outpatient
- Undertreatment (outpatient when IOP recommended) predicted poorer drinking outcomes
- Overtreatment did NOT improve outcomes (cost savings opportunity)

**Patient retention (aggregate):** Patients at ASAM-recommended level show
30% better retention at 90 days.

---

## 3. AI/Automated ASAM Scoring

**No modern AI/LLM system has been validated for ASAM scoring.**

- **ASAM CONTINUUM** is the only authorized software (ICC 0.77, ~10 min faster)
- **ASAM explicitly prohibits** inputting their criteria into AI systems
- **Turner et al. (1999)** — first computerized implementation (N=593),
  showed acceptable discrimination between 3 ASAM levels
- No published studies using NLP/LLM approaches to extract ASAM dimensional
  information from clinical notes

---

## 4. TJC Survey Reliability

**TJC does not publish inter-rater reliability statistics for its surveyors.**

- TJC uses an internal "variation index" (chi-square based) to track surveyor
  consistency, but explicitly states their system "was not designed to
  systematically measure the validity or accuracy of surveyor scoring"
- Coaching outlier surveyors produced "statistically significant but modest"
  improvement
- "New outliers continue to emerge quarterly"
- No published kappa, ICC, or percent-agreement statistics exist

### CMS Validation (Closest to Ground Truth)

CMS sends its own surveyors to re-inspect TJC-accredited hospitals. The
"disparity rate" = proportion where CMS found serious deficiencies TJC missed.

| Facility Type             | Disparity Rate (FY2019) |
| ------------------------- | ----------------------- |
| Hospitals                 | **42%**                 |
| Psychiatric Hospitals     | **45%**                 |
| Critical Access Hospitals | **46%**                 |
| Home Health Agencies      | **8%**                  |
| Hospices                  | **19%**                 |

Historical: Psychiatric hospitals were at **75%** disparity in FY2014.

**Interpretation:** TJC surveys miss condition-level deficiencies in nearly
half of hospitals upon CMS re-inspection.

Source: CMS FY2020 Report to Congress; GAO-04-850

---

## 5. TJC Standards Evidence Base

**40% of TJC standards lack supporting evidence.**

BMJ Evidence Base Analysis (2022) of 20 actionable standards:

- **30%** fully supported by evidence
- **30%** partly supported
- **40%** NOT supported by evidence
- Of fully supported: only **17%** cited level 1-2 evidence
- **80%** of standards received Grade D (weakest GRADE rating)
- Healthcare systems spend **0.2-1.7% of operating costs** on accreditation

### TJC Accreditation vs. Patient Outcomes

**Lam et al. (2018)** — BMJ, 4.2M admissions, 4,400 hospitals:

- "US hospital accreditation by independent organizations is NOT associated
  with lower mortality"
- TJC-accredited hospitals had modestly WORSE patient experience scores
- No meaningful difference between TJC and other accreditors

**Schmaltz et al. (2011)** — JAMA, 3,891 hospitals:

- TJC-accredited outperformed on process measures (87.7% vs 80.6%)
- 82% accredited vs 48% non-accredited achieved 90%+ adherence

---

## 6. Behavioral Health Non-Compliance Data

| Standard      | Description            | Fail Rate          |
| ------------- | ---------------------- | ------------------ |
| CTS.03.01.03  | Treatment planning     | **61.69%**         |
| NPSG.15.01.01 | Suicide risk reduction | Most cited overall |
| CTS.03.01.09  | Measurement-based care | 4th most cited     |

60% of all TJC findings stem from staff not following their own written rules
(implementation gap, not policy gap).

---

## 7. Automated TJC Compliance Tools

**No vendor has published validation data (sensitivity/specificity/F1).**

| Company      | Claims                                          | Validation               |
| ------------ | ----------------------------------------------- | ------------------------ |
| Brellium     | 87% reduction in audit time, 98% cost reduction | No published metrics     |
| Eleos Health | Reviews 100% of notes (vs 5-10% sampling)       | No published metrics     |
| Qualifacts   | Claims >90% accuracy                            | No published study       |
| Adentris     | 50% decrease in audit findings                  | No precision/recall data |

General NLP benchmarks (not TJC-specific):

- Error detection in medical docs: F1 77-81%
- Performance status documentation: 99% accuracy
- PHI detection: 96% F1 (John Snow Labs)

---

## 8. LLM Clinical Reasoning Performance

### Medical Exam Performance (MCQ)

| Model             | MedQA Accuracy |
| ----------------- | -------------- |
| o1                | **96.52%**     |
| GPT-5.1           | **96.38%**     |
| GPT-5             | **95.84%**     |
| GPT-4o            | **~91%**       |
| GPT-4 (zero-shot) | **71.6%**      |
| Med-PaLM          | **~67%**       |

### Real-World Clinical Reasoning (Much Worse)

- Script Concordance Testing: LLMs fall below attending physician performance
- Emergency medicine boards (Taiwan): GPT-4 achieved only **60.1%**
- Multi-dimensional clinical assessment average: **57.2% +/- 24.5%**
- Safety scoring: **54.7% +/- 26.1%**
- Diagnostic accuracy range: **25% to 97.8%** depending on complexity
- **86.3% of models suffered performance degradation** with chain-of-thought
  on messy clinical text

### Substance Use Disorder Specifically

- ChatGPT-4 surface quality: **3.92/5**, appropriateness **4.38/5**
- BUT: GPT-4 affirmed unsafe home heroin detox **23% of the time**
- Conflicting answers depending on drug order presentation (17% vs 32%)
- LLaMA-2 fabricated helplines and scientific citations about kratom
- Both models failed to direct suicidal ideation to crisis support

### Mental Health Tasks

| Task                        | Model     | Accuracy          |
| --------------------------- | --------- | ----------------- |
| Depression detection        | GPT-3.5   | F1: 0.78          |
| Suicidal ideation detection | BERTimbau | 95.5%             |
| Psychiatric case evaluation | ChatGPT   | "A" rating 61/100 |
| Suicidal tendency diagnosis | GPT-4.1   | 69.53%            |

### What Improves LLM Clinical Performance

| Technique                              | Effect                                                    |
| -------------------------------------- | --------------------------------------------------------- |
| Structured prompting (CARDS framework) | Guideline adherence 83.3% -> 100%                         |
| Few-shot examples                      | "The secret sauce" for complex clinical tasks             |
| Two-pass (think then format)           | Better reasoning than direct structured output            |
| Chain-of-thought                       | MIXED — helps structured tasks, hurts messy clinical text |

---

## 9. Implications For This Project

### ASAM Evaluation

- Our output will never be "correct" — even experts disagree 58% of the time
- Value is in the **reasoning and citations**, not the level number
- The evaluators will judge whether dimensional analysis makes clinical sense
- Two-pass approach + severity rating reference + LOC determination matrix
  gives the model more grounding than a typical clinician gets from memory

### TJC Audit

- More validatable than ASAM — mostly documentation presence/absence checks
- Can manually verify: "did the system correctly identify spiritual assessment
  was missing?"
- The real TJC standards have a 42-46% miss rate even with human surveyors
- Our system just needs to be thorough and cite specific text

### Legal Note

- ASAM explicitly prohibits inputting their criteria into AI systems
- Our prompts are based on the official ASAM 4th Edition Level of Care
  Assessment Guide (publicly available PDF from asam.org) and describe
  the assessment structure and LOC determination rules

---

## Sources

### ASAM Reliability & Outcomes

- Baker & Gastfriend 2003 — PubMed: 15991589
- Staines et al. 2003 — PubMed: 15991590
- Sharon et al. 2003 — PubMed: 15991591
- Magura et al. 2003 — PubMed: 14660153
- Kosanke et al. 2002 — PubMed: 12028742
- Stallvik & Gastfriend 2014 — Addiction Research & Theory, 22(6)
- Witbrodt et al. 2007 — J Consulting & Clinical Psychology, 75(6)
- Turner et al. 1999 — Drug and Alcohol Dependence, 55
- Morey 1995 — via PMC6876533

### TJC Reliability & Outcomes

- Lam et al. 2018 — PMC6193202
- Schmaltz et al. 2011 — PMC3265714
- BMJ Evidence Base 2022 — PMC9215261
- CMS FY2020 Report to Congress
- GAO-04-850
- HFM Magazine: "Measuring TJC Surveyor Consistency"
- TJC: "Facts About Machine Learning for Survey Consistency"

### LLM Clinical Performance

- MedQA Benchmark — vals.ai/benchmarks/medqa
- PMC11705880 — Evaluating AI responses to drug-related questions
- PMC10722374 — ChatGPT for SUD education
- Nature 41467-025-64769-1 — Quantifying LLM reasoning on clinical cases
- PMC12934876 — "Prompting is All You Need" (CARDS framework)
- arXiv 2509.21933 — Why CoT fails in clinical text
- PMC11530718 — LLMs for mental health systematic review
