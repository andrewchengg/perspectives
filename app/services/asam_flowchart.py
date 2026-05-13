"""
ASAM Level of Care Decision Flowchart — Reference Implementation

This is a rule-based implementation of the ASAM LOC determination algorithm
based on the Optum San Diego LOC Determination Guidelines (May 2018) and
ASAM 3rd/4th Edition criteria.

This is NOT a replacement for the LLM-based evaluation. It serves as:
1. A consistency check against the LLM's recommendation
2. A reference for understanding the algorithm
3. A fallback if the LLM produces invalid output

The LLM evaluation is superior because it can:
- Extract dimensional ratings from unstructured clinical text
- Apply clinical judgment to ambiguous cases
- Provide citations and rationale
- Handle cases that don't fit neatly into the matrix
"""

from dataclasses import dataclass


@dataclass
class DimensionRatings:
    d1_withdrawal: int  # 0-4: Acute Intoxication / Withdrawal Potential
    d2_biomedical: int  # 0-4: Biomedical Conditions
    d3_emotional: int  # 0-4: Emotional / Behavioral / Cognitive
    d4_readiness: int  # 0-4: Readiness to Change
    d5_relapse: int  # 0-4: Relapse / Continued Use Potential
    d6_environment: int  # 0-4: Recovery / Living Environment

    def __post_init__(self):
        for field_name, val in self.__dict__.items():
            if not (0 <= val <= 4):
                raise ValueError(f"{field_name} must be 0-4, got {val}")


@dataclass
class LOCRecommendation:
    level: str
    name: str
    rationale: str
    pathway: str  # which step in the algorithm matched


def determine_loc(ratings: DimensionRatings) -> LOCRecommendation:
    """
    Walk through the ASAM LOC determination algorithm.

    Decision tree based on:
    - Optum San Diego ASAM LOC Determination Guidelines (May 2018)
    - ASAM 3rd Edition dimensional admission criteria
    - 4th Edition structural changes (Level 3.3 removed, 1.7/2.7 added)

    Returns the LEAST RESTRICTIVE level that matches the pattern.
    """
    d1 = ratings.d1_withdrawal
    d2 = ratings.d2_biomedical
    d3 = ratings.d3_emotional
    d4 = ratings.d4_readiness
    d5 = ratings.d5_relapse
    d6 = ratings.d6_environment

    # Step 1-2: Check Level 4.0 (Medically Managed Intensive Inpatient)
    # Requires rating of 4 in at least one of D1, D2, or D3
    # D4-D6 severity alone does NOT qualify
    if d1 >= 4 or d2 >= 4 or d3 >= 4:
        return LOCRecommendation(
            level="4.0",
            name="Medically Managed Intensive Inpatient",
            rationale=f"Rating of 4 (Very High) in D1={d1}, D2={d2}, D3={d3}. "
            "Requires acute care hospital resources with 24-hour physician management.",
            pathway="Step 2: Level 4.0 check",
        )

    # Step 3: Check Level 3.7 (Medically Monitored Intensive Inpatient)
    # High severity (3+) in at least TWO dimensions, at least one in D1-D3
    high_dims = sum(1 for d in [d1, d2, d3, d4, d5, d6] if d >= 3)
    high_medical = sum(1 for d in [d1, d2, d3] if d >= 3)
    if high_dims >= 2 and high_medical >= 1:
        return LOCRecommendation(
            level="3.7",
            name="Medically Monitored Intensive Inpatient",
            rationale=f"{high_dims} dimensions rated 3+ (including {high_medical} in D1-D3). "
            "Interaction of severity requires 24-hour medical monitoring.",
            pathway="Step 3: Level 3.7 check",
        )

    # Step 4: Check Level 3.5 (Clinically Managed High-Intensity Residential)
    # D1/D2 low-moderate, D3 high, D4 high, D5/D6 high
    if (d1 <= 2 or d2 <= 2) and d3 >= 3 and d4 >= 3 and (d5 >= 3 or d6 >= 3):
        return LOCRecommendation(
            level="3.5",
            name="Clinically Managed High-Intensity Residential",
            rationale=f"D3={d3} (severe psychiatric), D4={d4} (poor readiness), "
            f"D5={d5}/D6={d6} (high relapse/environment risk). "
            "Needs 24-hour therapeutic community with high clinical intensity.",
            pathway="Step 4: Level 3.5 check",
        )

    # Step 5: Check Level 3.1 (Clinically Managed Low-Intensity Residential)
    # D6 drives residential — hostile environment while clinical severity is manageable
    if d1 <= 2 and d2 <= 2 and d3 <= 2 and d4 <= 2 and d5 in (2, 3) and d6 >= 3:
        return LOCRecommendation(
            level="3.1",
            name="Clinically Managed Low-Intensity Residential",
            rationale=f"D6={d6} (unsupportive/hostile environment) drives need for "
            f"structured living. D5={d5} (relapse risk) but clinical dimensions "
            "D1-D3 are manageable. Needs 24-hour structure, not intensive clinical.",
            pathway="Step 5: Level 3.1 check",
        )

    # Step 6: Check Level 2.5 (Partial Hospitalization, 20+ hrs/week)
    # D1-D3 warrant daily monitoring, moderate severity in 2/3 of D4-D6
    d123_need_monitoring = sum(1 for d in [d1, d2, d3] if d >= 2)
    d456_moderate = sum(1 for d in [d4, d5, d6] if d >= 2)
    if d123_need_monitoring >= 1 and d456_moderate >= 2:
        return LOCRecommendation(
            level="2.5",
            name="Partial Hospitalization Services",
            rationale=f"D1-D3 warrant daily monitoring ({d123_need_monitoring} at 2+). "
            f"{d456_moderate}/3 of D4-D6 at moderate+ severity. "
            "Requires 20+ hours/week of structured treatment.",
            pathway="Step 6: Level 2.5 check",
        )

    # Step 7: Check Level 2.1 (Intensive Outpatient, 9-19 hrs/week)
    # D1-D2 low, D3 mild-moderate, at least one of D4/D5/D6 moderate-high
    if d1 <= 1 and d2 <= 1 and d3 in (1, 2) and (d4 >= 2 or d5 >= 2 or d6 >= 2):
        return LOCRecommendation(
            level="2.1",
            name="Intensive Outpatient Services",
            rationale=f"D1={d1}, D2={d2} (low medical risk). D3={d3} (mild-moderate). "
            f"D4={d4}/D5={d5}/D6={d6} (moderate+ in at least one). "
            "Requires 9-19 hours/week structured treatment.",
            pathway="Step 7: Level 2.1 check",
        )

    # Step 8: Check Level 1.0 (Outpatient, <9 hrs/week)
    # ALL dimensions 0-1
    if all(d <= 1 for d in [d1, d2, d3, d4, d5, d6]):
        return LOCRecommendation(
            level="1.0",
            name="Outpatient Services",
            rationale="All dimensions rated 0-1. Minimal severity across all domains. "
            "Outpatient services (<9 hours/week) are sufficient.",
            pathway="Step 8: Level 1.0 check",
        )

    # Fallback: Pattern doesn't match cleanly — recommend Level 2.1 as safe default
    # and flag for clinical review
    return LOCRecommendation(
        level="2.1",
        name="Intensive Outpatient Services",
        rationale=f"Pattern (D1={d1}, D2={d2}, D3={d3}, D4={d4}, D5={d5}, D6={d6}) "
        "does not match a clean pathway. Defaulting to Level 2.1 (IOP) as the "
        "least restrictive level above outpatient. Clinical review recommended.",
        pathway="Fallback: no exact pathway match",
    )


def check_withdrawal_management(
    substance: str,
    ciwa_ar: int | None = None,
    severity: str = "mild",
) -> str | None:
    """
    Determine withdrawal management level for a specific substance.
    Returns WM level string or None if WM not indicated.
    """
    if substance.lower() == "alcohol" and ciwa_ar is not None:
        if ciwa_ar < 10:
            return "1-WM (Ambulatory, no extended monitoring)"
        elif ciwa_ar <= 25:
            return "2-WM (Ambulatory, extended monitoring)"
        elif ciwa_ar >= 19:
            return "3.7-WM or 4-WM (requires medical monitoring)"
    elif substance.lower() == "opioids":
        if severity == "mild":
            return "1-WM (Ambulatory)"
        elif severity == "moderate":
            return "2-WM (Ambulatory, extended monitoring)"
        elif severity == "severe":
            return "3.7-WM (Medically Monitored Inpatient WM)"
    elif substance.lower() == "stimulants":
        if severity in ("mild", "moderate"):
            return "1-WM or 2-WM (Ambulatory)"
        elif severity == "severe":
            return "3.2-WM or 3.7-WM (Residential/Inpatient)"

    return None
