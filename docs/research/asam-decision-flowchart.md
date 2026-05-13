# ASAM Level of Care Decision Flowchart

## The Algorithm

ASAM uses a two-stage process:

1. Rate each of 6 dimensions on a 0-4 scale
2. Match the pattern of ratings across dimensions to a level of care

It is NOT "highest score wins." It's pattern-matching across all 6 dimensions.

---

## The Decision Tree

```
PATHWAY 1 --> LEVEL 1.0 (Outpatient)
  IF rating = 0 or 1 in ALL six dimensions
  THEN --> Level 1.0

PATHWAY 2 --> LEVEL 2.1 (Intensive Outpatient)
  IF rating = 0 or 1 in Dimensions 1 AND 2
  AND rating = 1 or 2 in Dimension 3
  AND rating = 2 or 3 in Dimensions 4, 5, OR 6
  THEN --> Level 2.1

PATHWAY 3 --> LEVEL 3.1 (Low-Intensity Residential)
  IF rating = 0-2 in Dimension 3
  AND rating = 0-2 in Dimension 4
  AND rating = 2 or 3 in Dimension 5
  AND rating = 3-4 in Dimension 6
  THEN --> Level 3.1

PATHWAY 4 --> LEVEL 3.5 (High-Intensity Residential)
  IF rating = 0-2 in Dimensions 1 OR 2
  AND rating = 3 or 4 in Dimension 3
  AND rating = 3 or 4 in Dimension 4
  AND rating = 3 or 4 in Dimensions 5-6
  THEN --> Level 3.5

PATHWAY 5 --> LEVEL 3.7 (Medically Monitored Inpatient)
  IF meets specifications in at least TWO of six dimensions,
  at least one of which is in Dimension 1, 2, or 3
  THEN --> Level 3.7

PATHWAY 6 --> LEVEL 4.0 (Medically Managed Inpatient)
  IF rating = 4 in at least ONE of Dimensions 1, 2, or 3
  THEN --> Level 4.0
  EXCEPTION: Dimensions 4-6 alone do NOT qualify for Level 4

PATHWAY 7 --> OTP/NTP (Opioid Treatment Program)
  IF physiologically dependent on opioids (Dimension 1)
  AND rating = 0 or 1 in Dimensions 2-4
  AND rating = 3 in Dimension 5
  AND rating = 0 or 1 in Dimension 6
  THEN --> OTP/NTP
```

## Master Algorithm Steps

```
STEP 1: EMERGENCY TRIAGE
  Assess Dimensions 1, 2, 3 first (acute intoxication, biomedical, psychiatric)
  IF any = 4 --> Consider Level 4.0 immediately

STEP 2: ASSIGN RISK RATINGS (0-4) for each dimension

STEP 3: APPLY LOC DETERMINATION RULES
  Start at LEAST intensive level (1.0), check if patient fits
  If no, move up to next level
  Goal: LEAST restrictive effective level

STEP 4: WITHDRAWAL MANAGEMENT OVERLAY
  If active withdrawal, also determine WM level using substance-specific rules
  CIWA-Ar for alcohol: <10 = 1-WM, 10-25 = 2-WM, >=19 = 3.7-WM or 4-WM

STEP 5: SHARED DECISION-MAKING (Dimension 6)
  Patient preferences, cultural factors, practical constraints
  May modify final recommendation

STEP 6: DOCUMENT AND JUSTIFY
  If clinical judgment overrides algorithm, document rationale
```

## Dimension Severity Rating Scale

### Dimension 1: Acute Intoxication/Withdrawal

- 0: No withdrawal signs. CIWA-Ar <3. No intoxication
- 1: Mild. CIWA-Ar 3-7. Not dangerous
- 2: Moderate. CIWA-Ar 8-11. Some difficulty coping
- 3: High. CIWA-Ar 12-15. Severe signs, possible danger
- 4: Very High. CIWA-Ar >15. Seizures, DTs, life-threatening

### Dimension 2: Biomedical Conditions

- 0: No problems, stable
- 1: Mild, wouldn't interfere with treatment
- 2: May interfere with treatment. Non-life-threatening
- 3: Severe but stable. Requires medical/nursing services
- 4: Life-threatening

### Dimension 3: Emotional/Behavioral/Cognitive

- 0: No or stable mental health problems
- 1: Sub-clinical. SI without plan. Mild symptoms
- 2: SI/HI needing monitoring. Moderate role dysfunction
- 3: Frequent harm impulses, not imminent. ADL impairment
- 4: Severe unstable psych symptoms. Imminent danger

### Dimension 4: Readiness to Change

- 0: Actively engaged, committed, articulates goals
- 1: Willing but ambivalent (Contemplation stage)
- 2: Reluctant, complying to avoid consequences
- 3: Inconsistent follow-through, minimal awareness
- 4: Unable to follow through, in denial

### Dimension 5: Relapse/Continued Use Potential

- 0: Low risk. Good coping. No craving
- 1: Minimal risk. Some craving, can resist. Sporadic use
- 2: Impaired recognition. Regular use 1-2x/week
- 3: Little recognition. Severe craving. Frequent use 3+/week
- 4: No coping skills. Daily use. IV drug use. Treatment-resistant

### Dimension 6: Recovery/Living Environment

- 0: Supportive, drug-free home. No barriers
- 1: Passive support. Some access to substances. Minor barriers
- 2: Not supportive but can cope with clinical structure. Alone
- 3: Not supportive, difficult even with structure. Household using
- 4: Hostile/toxic. Homeless. Extreme barriers

## Alcohol Withdrawal Management by CIWA-Ar

| CIWA-Ar                                  | WM Level                                        |
| ---------------------------------------- | ----------------------------------------------- |
| <10                                      | 1-WM (Ambulatory, no extended monitoring)       |
| 10-25                                    | 2-WM (Ambulatory, extended monitoring)          |
| <8 at admission                          | 3.2-WM (Residential, if monitoring keeps it <8) |
| >=19                                     | 3.7-WM or 4-WM depending on acuity              |
| >=19 + hourly monitoring/IV/seizures/DTs | 4-WM                                            |

## Sources

- Optum San Diego ASAM LOC Determination Guidelines (May 2018)
- GAIN-Q4 ASAM B Dimensions Placement Decision Tree (Chestnut Health, 2023)
- NDBH Dimensional Admission Criteria (ASAM 3rd Ed licensed reprint)
- Alameda County BHCS Severity Ratings (CIBHS)
