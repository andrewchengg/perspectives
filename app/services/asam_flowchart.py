"""
ASAM Level of Care Determination — 4th Edition (Official)

Based on The ASAM Criteria, Fourth Edition, Volume 1: Adults.
Level of Care Determination Rules (pp 279-281).

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
]

# Map risk rating codes to minimum levels
RISK_CODE_TO_LEVEL = {
    # Dimension 1
    "4": "4",
    "3B": "3.7_BIO",
    "3A": "3.7",
    "2": "2.7",
    "1": "1.7",
    "C": "3.7",
    "B": "2.7",
    "A": "1.7",
    # Dimension 3 psychiatric
    "3B_COE": "3.7_COE",
    "3A_COE": "3.5_COE",
    "2B_COE": "2.7_COE",
    "2A_COE": "2.5_COE",
    "1C_COE": "1.7_COE",
    "1B": "1.7",
    "1A_COE": "1.5_COE",
    "1Z_COE": "1.5_COE",
    # Dimension 4
    "E": "3.5",
    "D": "3.1",
    # already have C, B, A above but for D4 they map differently
    # Dimension 5
    # D, C, B, A map to residential levels
}


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


def _level_rank(level: str) -> int:
    """Return rank of a level (lower = more intensive)."""
    try:
        return LEVEL_HIERARCHY.index(level)
    except ValueError:
        return len(LEVEL_HIERARCHY)  # unknown levels rank lowest


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
    minimum_levels = [r.minimum_level for r in subdimension_results if r.minimum_level not in ("ANY", "0", "EVAL", "MOUD-C")]

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
            return LOCRecommendation(level=level, name="Medically Monitored Intensive Inpatient", coe=has_coe, recovery_residence=False,
                                     rationale="Requires medically managed care AND Level 3 services.", steps=steps)
        elif needs_level_2:
            steps.append({"step": 2, "result": "Level 2.7 indicated", "rationale": "Medically managed + Level 2 need"})
            return LOCRecommendation(level="2.7", name="Medically Monitored Intensive Outpatient", coe=has_coe, recovery_residence=False,
                                     rationale="Requires medically managed care AND Level 2 services.", steps=steps)
        else:
            steps.append({"step": 2, "result": "Level 1.7 indicated", "rationale": "Medically managed, no Level 2/3 need"})
            return LOCRecommendation(level="1.7", name="Medically Monitored Outpatient", coe=has_coe, recovery_residence=False,
                                     rationale="Requires medically managed care but no Level 2 or 3 services.", steps=steps)

    steps.append({"step": 2, "result": "Not indicated"})

    # Step 3: Residential (3.5 / 3.1)
    needs_residential = any(_is_residential(lvl) for lvl in minimum_levels)
    if needs_residential:
        needs_3_5 = any(lvl.startswith("3.5") for lvl in minimum_levels)
        # Also: any subdimension requiring minimum Level 2.5 bumps to 3.5
        needs_2_5_plus = any(lvl.startswith("2.5") for lvl in minimum_levels)

        if needs_3_5 or needs_2_5_plus:
            level = "3.5_COE" if has_coe else "3.5"
            steps.append({"step": 3, "result": f"Level {level} indicated"})
            return LOCRecommendation(level=level, name="Clinically Managed High-Intensity Residential", coe=has_coe, recovery_residence=False,
                                     rationale="Requires residential care with high clinical intensity.", steps=steps)
        else:
            level = "3.1"
            steps.append({"step": 3, "result": "Level 3.1 indicated"})
            return LOCRecommendation(level=level, name="Clinically Managed Low-Intensity Residential", coe=False, recovery_residence=False,
                                     rationale="Requires residential structure but not high-intensity clinical.", steps=steps)

    steps.append({"step": 3, "result": "Not indicated"})

    # Step 4: Outpatient (2.5 / 2.1 / 1.5)
    outpatient_levels = [lvl for lvl in minimum_levels if any(lvl.startswith(x) for x in ["2.5", "2.1", "1.5"])]
    if outpatient_levels:
        most_intensive = min(outpatient_levels, key=_level_rank)
        base = most_intensive.split("_")[0]

        # COE overlay
        if has_coe and base in ("2.1", "1.5"):
            # 2.1 + COE → 2.5 COE, per the rules
            if base == "2.1":
                base = "2.5"
            level = f"{base}_COE"
        elif has_coe:
            level = f"{base}_COE"
        else:
            level = base

        names = {
            "2.5": "Partial Hospitalization Services",
            "2.5_COE": "Partial Hospitalization, Co-occurring Enhanced",
            "2.1": "Intensive Outpatient Services",
            "1.5": "Outpatient Services",
            "1.5_COE": "Outpatient Services, Co-occurring Enhanced",
        }
        steps.append({"step": 4, "result": f"Level {level} indicated"})

        # Step 6: Recovery Residence check
        rr_needed = any(r.minimum_level.startswith("RR") or (r.dimension == 5 and r.minimum_level == "A")
                        for r in subdimension_results)

        return LOCRecommendation(
            level=level,
            name=names.get(level, f"Level {level}"),
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
        recovery_residence=False,
        rationale="No subdimension indicates need above Level 1.5.",
        steps=steps,
    )
