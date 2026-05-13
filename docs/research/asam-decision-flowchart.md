# ASAM Level of Care Decision — 4th Edition (Official)

Source: The ASAM Criteria, Fourth Edition, Volume 1: Adults.
Level of Care Assessment Guide v4.1.0.0.

---

## How It Works

The 4th Edition uses a **subdimensional minimum level** approach:

1. Evaluate each subdimension across 5 clinical dimensions
2. Each subdimension maps to a **minimum level of care code** (not a 0-4 number)
3. Apply LOC Determination Rules **top-down** (most intensive first)
4. Dimension 6 is a shared decision-making conversation, not scored

## The Dimensions and Subdimensions

### Dimension 1: Acute Intoxication and/or Withdrawal Potential (pp 212-229)

- **1A: Intoxication and Associated Risks** → codes: 4, 3B, 3A, 2, ANY, 0
- **1B: Withdrawal and Associated Risks** → codes: 4, 3B, 3A, 2, 1, EVAL, 0
- **1C: Addiction Medication Needs** → codes: C, B, A, EVAL, ANY, MOUD-C

### Dimension 2: Biomedical Conditions (pp 230-239)

- **2A: Physical Health Concerns** → codes: 4, 3B, 3A, 2, 1, ANY, 0
- **2B: Pregnancy-related Concerns** → codes: 4, 3, 2, 1, ANY, 0

### Dimension 3: Emotional, Behavioral, or Cognitive Conditions (pp 240-254)

- **3A: Active Psychiatric Symptoms** → codes: 4, 3B, 3A, 2B, 2A, 1C, 1B, 1A, ANY, 0
- **3B: Persistent Disability** → codes: 1Z, ANY, 0

### Dimension 4: Substance Use-related Risks (pp 255-271)

- **4A: Likelihood of Engaging in Risky Substance Use** → codes: E, D, C, B, A
- **4B: Likelihood of Engaging in Risky SUD-related Behaviors** → codes: E, D, C, B, A, 0

### Dimension 5: Recovery Environment Interactions (pp 272-278)

- **5A: Ability to Function Effectively in Current Environment** → codes: D, C, B, A, ANY, 0
- **5B: Safety in Current Environment** → codes: A (recovery residence), 0
- **5C: Support in Current Environment** → codes: B, A, ANY, 0

### Dimension 6: Level of Care Selection (not scored)

- Shared decision-making about willingness and ability to attend recommended level
- Document any discrepancy between recommended and selected level

## Risk Rating Code Meanings

| Code   | Minimum Level                                                    |
| ------ | ---------------------------------------------------------------- |
| 4      | Level 4 (Medically Managed Intensive Inpatient)                  |
| 3B     | Level 3.7 BIO (Medically Monitored, Biomedical Enhanced)         |
| 3A     | Level 3.7 (Medically Monitored Intensive Inpatient)              |
| 3A_COE | Level 3.5 COE                                                    |
| 2B     | Level 2.7 COE                                                    |
| 2A     | Level 2.5 COE                                                    |
| 2      | Level 2.7                                                        |
| 1C     | Level 1.7 COE                                                    |
| 1B     | Level 1.7                                                        |
| 1A     | Level 1.5 COE                                                    |
| 1Z     | Level 1.5 COE (Persistent Disability)                            |
| 1      | Level 1.7                                                        |
| E      | Level 3.5 (Dimension 4/5)                                        |
| D      | Level 3.1 (Dimension 4/5)                                        |
| C      | Level 2.5 or Level 3.7 (context-dependent)                       |
| B      | Level 2.1 or Level 2.7 (context-dependent)                       |
| A      | Level 1.5 or Level 1.7 or Recovery Residence (context-dependent) |
| ANY    | Any Level of Care                                                |
| EVAL   | Prompt Evaluation (further assessment needed)                    |
| MOUD-C | MOUD Continuation (flag need for medication-supporting program)  |
| 0      | No Specific Needs                                                |

## LOC Determination Rules (pp 279-281)

Apply top-down, most intensive first:

```
STEP 1: INPATIENT (Level 4 / Level 4 Psychiatric)
  IF any subdimension = 4 → Level 4
  IF 3.7 BIO + any COE → Level 4
  IF Level 4 Psychiatric only (no 4 or 3.7 BIO) → Level 4 Psychiatric

STEP 2: MEDICALLY MANAGED (Level 3.7 / 2.7 / 1.7)
  IF any subdimension needs medically managed care:
    + any Level 3 need → Level 3.7 (or 3.7 BIO)
    + any Level 2 need (no Level 3) → Level 2.7
    + no Level 2 or 3 need → Level 1.7

STEP 3: CLINICALLY MANAGED RESIDENTIAL (Level 3.5 / 3.1)
  IF any subdimension needs residential:
    + any needs Level 3.5 or Level 2.5+ → Level 3.5
    + no Level 3.5 need → Level 3.1

STEP 4: CLINICALLY MANAGED OUTPATIENT (Level 2.5 / 2.1 / 1.5)
  What is the most intensive outpatient level indicated?
    Level 2.5 → 2.5
    Level 2.1 → 2.1
    Level 1.5 → 1.5

STEP 5: CO-OCCURRING ENHANCED (COE) OVERLAY
  IF any subdimension indicates COE → append COE to the level
  Exceptions:
    Level 4 + Level 4 Psychiatric → Level 4 (not 4 Psychiatric)
    Level 3.7 BIO + COE → Level 4
    Would be 3.1 + COE → Level 3.5 COE
    Would be 2.1 + COE → Level 2.5 COE

STEP 6: RECOVERY RESIDENCE
  IF outpatient recommended (1.5, 1.7, 2.1, 2.5, 2.7):
    IF any D5 subdimension indicates recovery residence need
    → Add recovery residence to recommendation

STEP 7: DIMENSION 6 (Level of Care Selection)
  Discuss with patient → document willingness → adjust if needed
```

## Valid Levels of Care (4th Edition)

| Level         | Name                                                                 |
| ------------- | -------------------------------------------------------------------- |
| 1.5           | Outpatient Services                                                  |
| 1.5 COE       | Outpatient Services, Co-occurring Enhanced                           |
| 1.7           | Medically Monitored Outpatient                                       |
| 1.7 COE       | Medically Monitored Outpatient, Co-occurring Enhanced                |
| 2.1           | Intensive Outpatient Services                                        |
| 2.5           | Partial Hospitalization Services                                     |
| 2.5 COE       | Partial Hospitalization, Co-occurring Enhanced                       |
| 2.7           | Medically Monitored Intensive Outpatient                             |
| 2.7 COE       | Medically Monitored Intensive Outpatient, Co-occurring Enhanced      |
| 3.1           | Clinically Managed Low-Intensity Residential                         |
| 3.5           | Clinically Managed High-Intensity Residential                        |
| 3.5 COE       | Clinically Managed High-Intensity Residential, Co-occurring Enhanced |
| 3.7           | Medically Monitored Intensive Inpatient                              |
| 3.7 BIO       | Medically Monitored Intensive Inpatient, Biomedical Enhanced         |
| 3.7 COE       | Medically Monitored Intensive Inpatient, Co-occurring Enhanced       |
| 4             | Medically Managed Intensive Inpatient                                |
| 4 Psychiatric | Medically Managed Inpatient Psychiatric                              |

## Source

The ASAM Criteria, Fourth Edition, Volume 1: Adults.
Level of Care Assessment Guide v4.1.0.0.
American Society of Addiction Medicine, 2024.
