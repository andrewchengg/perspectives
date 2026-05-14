"""Tests for the QA Agent — validates all 7 checks work correctly."""

import pytest
from app.services.qa_agent import (
    check_citation,
    check_negation_flips,
    scan_fabrications,
    check_temporal_coherence,
    compute_confidence_score,
)


# ---------------------------------------------------------------------------
# Check 1: Citation Verification
# ---------------------------------------------------------------------------

class TestCitationVerification:
    SOURCE = (
        "Patient reports daily alcohol consumption of 6-8 standard drinks for the past 3 years. "
        "Denies any withdrawal symptoms including tremors, seizures, or delirium. "
        "History of one prior detox admission in 2022 at Springfield Medical Center. "
        "Currently prescribed naltrexone 50mg daily. "
        "Patient denies suicidal ideation, homicidal ideation, or self-harm behaviors."
    )

    def test_exact_match(self):
        result = check_citation("daily alcohol consumption of 6-8 standard drinks", self.SOURCE)
        assert result["verdict"] == "verified"
        assert result["score"] == 1.0
        assert result["method"] == "exact"

    def test_fuzzy_match_paraphrase(self):
        result = check_citation("reports consuming 6-8 alcoholic drinks every day", self.SOURCE)
        # Should find a fuzzy match since the key terms overlap
        assert result["verdict"] in ("verified", "partial")
        assert result["score"] > 0.5

    def test_hallucinated_citation(self):
        result = check_citation(
            "Patient tested positive for methamphetamine on urine drug screen",
            self.SOURCE,
        )
        assert result["verdict"] == "not_found"
        assert result["score"] < HALLUCINATED_THRESHOLD

    def test_short_citation_skipped(self):
        result = check_citation("yes", self.SOURCE)
        assert result["verdict"] == "verified"  # too short to meaningfully check
        assert result["method"] == "too_short_to_check"

    def test_partial_match(self):
        # Close but not exact — some words match
        result = check_citation(
            "previous detoxification treatment at a local hospital",
            self.SOURCE,
        )
        assert result["score"] > 0.0  # should find some overlap


HALLUCINATED_THRESHOLD = 0.65


# ---------------------------------------------------------------------------
# Check 2: Negation Flip Detection
# ---------------------------------------------------------------------------

class TestNegationDetection:
    SOURCE = (
        "Patient denies any history of seizures. "
        "Patient denies suicidal ideation. "
        "Patient reports daily alcohol use. "
        "No evidence of psychotic symptoms."
    )

    def test_detects_negation_flip(self):
        generated = "Patient reports a history of seizures requiring hospitalization."
        flips = check_negation_flips(self.SOURCE, generated)
        assert len(flips) > 0
        assert flips[0]["severity"] == "critical"

    def test_no_flip_when_consistent(self):
        generated = "Patient denies any history of seizures."
        flips = check_negation_flips(self.SOURCE, generated)
        assert len(flips) == 0

    def test_detects_suicidal_ideation_flip(self):
        generated = "Patient endorses suicidal ideation with a plan."
        flips = check_negation_flips(self.SOURCE, generated)
        # Should detect the flip from "denies" to "endorses"
        assert len(flips) > 0

    def test_affirm_to_negate_flip(self):
        generated = "Patient denies any alcohol use."
        flips = check_negation_flips(self.SOURCE, generated)
        assert len(flips) > 0  # source says "reports daily alcohol use"


# ---------------------------------------------------------------------------
# Check 6: Fabrication Scan
# ---------------------------------------------------------------------------

class TestFabricationScan:
    SOURCE = (
        "Patient is prescribed naltrexone 50mg daily. "
        "Diagnosis: F10.20 Alcohol use disorder, moderate. "
        "Blood pressure 130/85 mmHg."
    )

    def test_detects_fabricated_medication(self):
        generated = "Patient was started on disulfiram 250mg and continues naltrexone."
        fabs = scan_fabrications(self.SOURCE, generated)
        med_fabs = [f for f in fabs if f["type"] == "medication"]
        # disulfiram should be flagged (not in source)
        assert any("disulfiram" in f["value"].lower() for f in med_fabs)

    def test_detects_fabricated_code(self):
        generated = "Diagnoses include F10.20 and F14.10 cocaine use disorder."
        fabs = scan_fabrications(self.SOURCE, generated)
        code_fabs = [f for f in fabs if f["type"] == "diagnostic_code"]
        assert any("F14" in f["value"] for f in code_fabs)

    def test_no_false_positive_for_existing_med(self):
        generated = "Continues naltrexone 50mg daily as prescribed."
        fabs = scan_fabrications(self.SOURCE, generated)
        med_fabs = [f for f in fabs if f["type"] == "medication"]
        assert not any("naltrexone" in f["value"].lower() for f in med_fabs)

    def test_detects_fabricated_lab_value(self):
        generated = "Patient's BAC was 0.15 mg/dL on admission."
        fabs = scan_fabrications(self.SOURCE, generated)
        lab_fabs = [f for f in fabs if f["type"] == "lab_value"]
        assert len(lab_fabs) > 0


# ---------------------------------------------------------------------------
# Check 7: Temporal Coherence
# ---------------------------------------------------------------------------

class TestTemporalCoherence:
    SOURCE = (
        "Assessment date: 2026-01-15. "
        "Patient reports alcohol use for the past 3 years. "
        "Prior detox admission on 2022-06-10."
    )

    def test_detects_fabricated_date(self):
        generated = "Patient's last relapse was on 2025-11-20."
        issues = check_temporal_coherence(self.SOURCE, generated)
        date_issues = [i for i in issues if i["type"] == "date_not_in_source"]
        assert any("2025-11-20" in i["value"] for i in date_issues)

    def test_no_flag_for_existing_date(self):
        generated = "Based on the assessment from 2026-01-15."
        issues = check_temporal_coherence(self.SOURCE, generated)
        date_issues = [i for i in issues if i["type"] == "date_not_in_source"]
        assert not any("2026-01-15" in i["value"] for i in date_issues)

    def test_detects_duration_mismatch(self):
        generated = "Patient has been drinking heavily for 5 years."
        issues = check_temporal_coherence(self.SOURCE, generated)
        duration_issues = [i for i in issues if i["type"] == "duration_mismatch"]
        assert len(duration_issues) > 0  # source says 3 years, output says 5


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

class TestConfidenceScoring:
    def test_perfect_score(self):
        score = compute_confidence_score(
            citation_results=[{"verdict": "verified"}] * 5,
            negation_flips=[],
            completeness_gaps=[],
            consistency_issues=[],
            fabrications=[],
            temporal_issues=[],
            llm_verification={"overall_quality": "good"},
        )
        assert score == 1.0

    def test_zero_score_critical_failures(self):
        score = compute_confidence_score(
            citation_results=[{"verdict": "not_found"}] * 5,
            negation_flips=[{"severity": "critical"}],
            completeness_gaps=[{"severity": "critical"}],
            consistency_issues=[{"severity": "critical"}],
            fabrications=[{"severity": "critical"}],
            temporal_issues=[{"type": "date"}],
            llm_verification={"overall_quality": "poor"},
        )
        assert score < 0.2

    def test_negation_flip_tanks_score(self):
        good = compute_confidence_score(
            citation_results=[{"verdict": "verified"}] * 3,
            negation_flips=[],
            completeness_gaps=[],
            consistency_issues=[],
            fabrications=[],
            temporal_issues=[],
        )
        bad = compute_confidence_score(
            citation_results=[{"verdict": "verified"}] * 3,
            negation_flips=[{"severity": "critical"}],
            completeness_gaps=[],
            consistency_issues=[],
            fabrications=[],
            temporal_issues=[],
        )
        assert good - bad >= 0.15  # negation has 20% weight
