"""
ASAM Level of Care Determination — 4th Edition (Official)

Based on The ASAM Criteria, Fourth Edition, Volume 1: Adults.
Level of Care Assessment Guide, pp 279-281.
Risk Rating Forms from official ASAM LOC Assessment Guide v4.1.0.0.

The 4th Edition uses a TOP-DOWN DEDUCTIVE approach:
1. Each subdimension maps to a minimum level of care code
2. Start at the most intensive level (Level 4) and work down
3. The highest minimum level across all subdimensions drives placement

This module provides a rule-based implementation for consistency checking
against the LLM's recommendation.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Level hierarchy (most intensive to least)
LEVEL_HIERARCHY = [
    "4",
    "4_PSYCH",
    "3.7_BIO",
    "3.7_COE",
    "3.7",
    "3.5_COE",
    "3.5",
    "3.1",
    "2.7_COE",
    "2.7",
    "2.5_COE",
    "2.5",
    "2.1",
    "1.7_COE",
    "1.7",
    "1.5_COE",
    "1.5",
    "RR",  # Recovery Residence (not a level but a modifier)
]

# ── Dimension-aware risk code to minimum level mappings ──
# Source: ASAM LOC Assessment Guide v4.1.0.0, Risk Rating Forms (pp 7, 10, 13, 15, 17)

# Dimension 1: Intoxication, Withdrawal, and Addiction Medications
D1_INTOXICATION = {
    "4": "4", "3B": "3.7_BIO", "3A": "3.7", "2": "2.7", "ANY": "ANY", "0": "0",
}
D1_WITHDRAWAL = {
    "4": "4", "3B": "3.7_BIO", "3A": "3.7", "2": "2.7", "1": "1.7",
    "EVAL": "EVAL", "0": "0",
}
D1_ADDICTION_MEDS = {
    "C": "3.7", "B": "2.7", "A": "1.7", "EVAL": "EVAL", "ANY": "ANY", "MOUD-C": "MOUD-C",
}

# Dimension 2: Biomedical Conditions
D2_PHYSICAL = {
    "4": "4", "3B": "3.7_BIO", "3A": "3.7", "2": "2.7", "1": "1.7", "ANY": "ANY", "0": "0",
}
D2_PREGNANCY = {
    "4": "4", "3": "3.7", "2": "2.7", "1": "1.7", "ANY": "ANY", "0": "0",
}

# Dimension 3: Psychiatric and Cognitive Conditions
D3_PSYCHIATRIC = {
    "4": "4_PSYCH", "3B": "3.7_COE", "3A": "3.5_COE", "2B": "2.7_COE",
    "2A": "2.5_COE", "1C": "1.7_COE", "1B": "1.7", "1A": "1.5_COE",
    "ANY": "ANY", "0": "0",
}
D3_PERSISTENT_DISABILITY = {
    "1Z": "1.5_COE", "ANY": "ANY", "0": "0",
}

# Dimension 4: Substance Use-Related Risks
D4_RISKY_USE = {
    "E": "3.5", "D": "3.1", "C": "2.5", "B": "2.1", "A": "1.5",
}
D4_RISKY_BEHAVIORS = {
    "E": "3.5", "D": "3.1", "C": "2.5", "B": "2.1", "A": "1.5", "0": "0",
}

# Dimension 5: Recovery Environment Interactions
D5_FUNCTIONING = {
    "D": "3.5", "C": "3.1", "B": "2.5", "A": "2.1", "ANY": "ANY", "0": "0",
}
D5_SAFETY = {
    "A": "RR", "0": "0",
}
D5_SUPPORT = {
    "B": "3.1", "A": "RR", "ANY": "ANY", "0": "0",
}

# Map (dimension, subdimension_name_keyword) to the correct lookup table
# Used to resolve risk codes when we know which dimension/subdimension they belong to
SUBDIM_MAPPINGS = {
    (1, "intoxication"): D1_INTOXICATION,
    (1, "withdrawal"): D1_WITHDRAWAL,
    (1, "addiction"): D1_ADDICTION_MEDS,
    (1, "medication"): D1_ADDICTION_MEDS,
    (2, "physical"): D2_PHYSICAL,
    (2, "health"): D2_PHYSICAL,
    (2, "pregnancy"): D2_PREGNANCY,
    (3, "psychiatric"): D3_PSYCHIATRIC,
    (3, "active"): D3_PSYCHIATRIC,
    (3, "persistent"): D3_PERSISTENT_DISABILITY,
    (3, "disability"): D3_PERSISTENT_DISABILITY,
    (4, "substance"): D4_RISKY_USE,
    (4, "risky_use"): D4_RISKY_USE,
    (4, "use"): D4_RISKY_USE,
    (4, "behavior"): D4_RISKY_BEHAVIORS,
    (4, "risky_behavior"): D4_RISKY_BEHAVIORS,
    (5, "function"): D5_FUNCTIONING,
    (5, "ability"): D5_FUNCTIONING,
    (5, "safety"): D5_SAFETY,
    (5, "support"): D5_SUPPORT,
}


def resolve_minimum_level(dimension: int, subdimension_name: str, risk_code: str) -> str:
    """Resolve a risk code to its minimum level using dimension-aware mappings."""
    code = risk_code.upper().strip()
    name_lower = subdimension_name.lower()

    # Find the matching lookup table
    for (dim, keyword), table in SUBDIM_MAPPINGS.items():
        if dim == dimension and keyword in name_lower:
            if code in table:
                return table[code]

    # Fallback: try to parse the minimum_level string directly
    # (LLM sometimes outputs "Minimum Level 2.5" instead of a risk code)
    logger.warning(
        "No mapping found for D%d/%s code=%s — will use LLM's minimum_level",
        dimension, subdimension_name, risk_code,
    )
    return code


@dataclass
class SubdimensionResult:
    dimension: int
    subdimension: str
    risk_code: str
    minimum_level: str


@dataclass
class LOCRecommendation:
    level: str
    name: str
    coe: bool
    recovery_residence: bool
    rationale: str
    steps: list[dict] = field(default_factory=list)


LEVEL_NAMES = {
    "4": "Medically Managed Intensive Inpatient",
    "4_PSYCH": "Medically Managed Inpatient Psychiatric",
    "3.7_BIO": "Medically Monitored Intensive Inpatient (BIO)",
    "3.7_COE": "Medically Monitored Intensive Inpatient (COE)",
    "3.7": "Medically Monitored Intensive Inpatient",
    "3.5_COE": "Clinically Managed High-Intensity Residential (COE)",
    "3.5": "Clinically Managed High-Intensity Residential",
    "3.1": "Clinically Managed Low-Intensity Residential",
    "2.7_COE": "Medically Monitored Intensive Outpatient (COE)",
    "2.7": "Medically Monitored Intensive Outpatient",
    "2.5_COE": "Partial Hospitalization, Co-occurring Enhanced",
    "2.5": "Partial Hospitalization Services",
    "2.1": "Intensive Outpatient Services",
    "1.7_COE": "Medically Monitored Outpatient (COE)",
    "1.7": "Medically Monitored Outpatient",
    "1.5_COE": "Outpatient Services, Co-occurring Enhanced",
    "1.5": "Outpatient Services",
}


def _level_rank(level: str) -> int:
    """Return rank of a level (lower = more intensive)."""
    try:
        return LEVEL_HIERARCHY.index(level)
    except ValueError:
        return len(LEVEL_HIERARCHY)


def _is_medically_managed(level: str) -> bool:
    return any(level.startswith(x) for x in ["1.7", "2.7", "3.7"])


def _is_residential(level: str) -> bool:
    return any(level.startswith(x) for x in ["3.1", "3.5"])


def _is_level3(level: str) -> bool:
    return any(level.startswith(x) for x in ["3.1", "3.5", "3.7"])


def _is_level2(level: str) -> bool:
    return any(level.startswith(x) for x in ["2.1", "2.5", "2.7"])


def _is_coe(level: str) -> bool:
    return "COE" in level or "PSYCH" in level


def determine_loc(subdimension_results: list[SubdimensionResult]) -> LOCRecommendation:
    """
    Apply the official ASAM 4th Edition LOC Determination Rules.
    Top-down approach: start at Level 4, work down.
    """
    steps = []
    skip = {"ANY", "0", "EVAL", "MOUD-C", "RR"}
    minimum_levels = [r.minimum_level for r in subdimension_results if r.minimum_level not in skip]

    if not minimum_levels:
        return LOCRecommendation(
            level="1.5",
            name="Outpatient Services",
            coe=False,
            recovery_residence=False,
            rationale="No subdimension indicates specific level needs.",
            steps=[{"step": 1, "result": "No specific needs identified"}],
        )

    has_coe = any(_is_coe(lvl) for lvl in minimum_levels)
    rr_needed = any(r.minimum_level == "RR" for r in subdimension_results)

    # Step 1: Level 4 / 4 Psychiatric
    has_level_4 = any(lvl == "4" for lvl in minimum_levels)
    has_level_4_psych = any(lvl == "4_PSYCH" for lvl in minimum_levels)
    has_3_7_bio = any(lvl == "3.7_BIO" for lvl in minimum_levels)

    if has_level_4:
        steps.append({"step": 1, "result": "Level 4 indicated", "rationale": "Subdimension requires Level 4"})
        return LOCRecommendation(level="4", name="Medically Managed Intensive Inpatient", coe=False, recovery_residence=False,
                                 rationale="At least one subdimension requires Level 4.", steps=steps)

    if has_3_7_bio and has_coe:
        steps.append({"step": 1, "result": "Level 4 indicated", "rationale": "Level 3.7 BIO + COE = Level 4"})
        return LOCRecommendation(level="4", name="Medically Managed Intensive Inpatient", coe=True, recovery_residence=False,
                                 rationale="Patient meets criteria for Level 3.7 BIO AND a COE level.", steps=steps)

    if has_level_4_psych and not has_level_4 and not has_3_7_bio:
        steps.append({"step": 1, "result": "Level 4 Psychiatric indicated"})
        return LOCRecommendation(level="4_PSYCH", name="Medically Managed Inpatient Psychiatric", coe=True, recovery_residence=False,
                                 rationale="Patient meets criteria for Level 4 Psychiatric.", steps=steps)

    steps.append({"step": 1, "result": "Not indicated"})

    # Step 2: Medically Managed (3.7 / 2.7 / 1.7)
    needs_medical = any(_is_medically_managed(lvl) for lvl in minimum_levels)
    if needs_medical:
        needs_level_3 = any(_is_level3(lvl) for lvl in minimum_levels)
        needs_level_2 = any(_is_level2(lvl) for lvl in minimum_levels)

        if needs_level_3:
            level = "3.7_BIO" if has_3_7_bio else "3.7"
            steps.append({"step": 2, "result": f"Level {level} indicated", "rationale": "Medically managed + Level 3 need"})
            return LOCRecommendation(level=level, name=LEVEL_NAMES.get(level, level), coe=has_coe, recovery_residence=rr_needed,
                                     rationale="Requires medically managed care AND Level 3 services.", steps=steps)
        elif needs_level_2:
            level = "2.7_COE" if has_coe else "2.7"
            steps.append({"step": 2, "result": f"Level {level} indicated", "rationale": "Medically managed + Level 2 need"})
            return LOCRecommendation(level=level, name=LEVEL_NAMES.get(level, level), coe=has_coe, recovery_residence=rr_needed,
                                     rationale="Requires medically managed care AND Level 2 services.", steps=steps)
        else:
            level = "1.7_COE" if has_coe else "1.7"
            steps.append({"step": 2, "result": f"Level {level} indicated", "rationale": "Medically managed, no Level 2/3 need"})
            return LOCRecommendation(level=level, name=LEVEL_NAMES.get(level, level), coe=has_coe, recovery_residence=rr_needed,
                                     rationale="Requires medically managed care but no Level 2 or 3 services.", steps=steps)

    steps.append({"step": 2, "result": "Not indicated"})

    # Step 3: Residential (3.5 / 3.1)
    needs_residential = any(_is_residential(lvl) for lvl in minimum_levels)
    if needs_residential:
        needs_3_5 = any(lvl.startswith("3.5") for lvl in minimum_levels)
        needs_2_5_plus = any(lvl.startswith("2.5") for lvl in minimum_levels)

        if needs_3_5 or needs_2_5_plus:
            level = "3.5_COE" if has_coe else "3.5"
            steps.append({"step": 3, "result": f"Level {level} indicated"})
            return LOCRecommendation(level=level, name=LEVEL_NAMES.get(level, level), coe=has_coe, recovery_residence=rr_needed,
                                     rationale="Requires residential care with high clinical intensity.", steps=steps)
        else:
            level = "3.1"
            steps.append({"step": 3, "result": "Level 3.1 indicated"})
            return LOCRecommendation(level=level, name=LEVEL_NAMES.get(level, level), coe=False, recovery_residence=rr_needed,
                                     rationale="Requires residential structure but not high-intensity clinical.", steps=steps)

    steps.append({"step": 3, "result": "Not indicated"})

    # Step 4: Outpatient (2.5 / 2.1 / 1.5)
    outpatient_levels = [lvl for lvl in minimum_levels if any(lvl.startswith(x) for x in ["2.5", "2.1", "1.5"])]
    if outpatient_levels:
        most_intensive = min(outpatient_levels, key=_level_rank)
        base = most_intensive.split("_")[0]

        # COE overlay
        if has_coe and base in ("2.1", "1.5"):
            if base == "2.1":
                base = "2.5"
            level = f"{base}_COE"
        elif has_coe:
            level = f"{base}_COE"
        else:
            level = base

        steps.append({"step": 4, "result": f"Level {level} indicated"})

        return LOCRecommendation(
            level=level,
            name=LEVEL_NAMES.get(level, f"Level {level}"),
            coe=has_coe,
            recovery_residence=rr_needed,
            rationale=f"Most intensive outpatient level indicated is {level}.",
            steps=steps,
        )

    steps.append({"step": 4, "result": "Level 1.5 (default)"})
    return LOCRecommendation(
        level="1.5",
        name="Outpatient Services",
        coe=False,
        recovery_residence=rr_needed,
        rationale="No subdimension indicates need above Level 1.5.",
        steps=steps,
    )
