"""
TJC Section-by-Section Prompts

Instead of one massive prompt with 39 standards, we split into focused sections.
Each section gets its own LLM call with only its relevant EPs.
"""

TJC_SECTION_SYSTEM = """\
You are a Joint Commission (TJC) compliance auditor for behavioral health \
substance use disorder (SUD) treatment programs.

CRITICAL AUDIT PRINCIPLE: "Not documented = not done." If documentation \
is absent, that IS the finding. Do not assume something was done verbally.

Source: Joint Commission Public Standards Database, March 2026 edition.

You will audit a patient's clinical documentation against SPECIFIC standards \
and Elements of Performance (EPs). For EVERY EP listed, you MUST produce a finding.

Respond with ONLY valid JSON — no markdown fences, no extra text."""

TJC_SECTION_OUTPUT_FORMAT = """\

OUTPUT FORMAT — respond with ONLY this JSON structure:
{{
  "standards": [
    {{
      "standard_id": "CTS.XX.XX.XX",
      "standard_name": "Name of the standard",
      "overall_status": "compliant" | "non_compliant" | "partial",
      "findings": [
        {{
          "element": "CTS.XX.XX.XX EP N",
          "description": "What this EP requires",
          "status": "pass" | "fail" | "partial",
          "finding": "Specific finding with evidence or gap description",
          "citations": [
            {{
              "source": "BPS Intake" | "SOAP Note" | "DAP Note" | etc,
              "text": "EXACT verbatim quote from document",
              "relevance": "why this demonstrates compliance or gap"
            }}
          ],
          "remediation": "Specific actionable fix" or null if pass
        }}
      ],
      "compliance_percentage": 75.0
    }}
  ]
}}

RULES:
- You MUST produce a finding for EVERY EP listed — do NOT skip any
- Citations must be EXACT verbatim text from the document
- If documentation is absent, status is "fail" and cite what IS documented (or state "Not documented")
- compliance_percentage = (pass count / total findings) * 100
- overall_status: all pass = "compliant", all fail = "non_compliant", mixed = "partial"
"""

# --- Section definitions ---

SECTIONS = [
    {
        "id": "screening",
        "name": "Screening (CTS.02.01)",
        "standards": """\
CTS.02.01.01: Screening for risk of imminent harm to self or others.
  EP 1: The screening procedure determines the need for immediate intervention.
  EP 2: The organization follows its process for responding when immediate risk of harm is identified.

CTS.02.01.03: Screenings and assessments performed per policy.
  EP 1: The organization assesses each individual in accordance with policy.
  EP 2: Assessment conducted within the time frame specified by needs, policy, and law/regulation.
  EP 3: The organization collects information during screenings/assessments about the individual's perception of needs and goals; physical health; psychological, social, spiritual, and cultural factors; strengths; and risk factors.

CTS.02.01.05: Physical health screening.
  EP 1: Follows written physical health screening process to determine whether individual needs a medical history and physical examination.

CTS.02.01.09: Screens all individuals for physical pain.
  EP 1: Screens to identify those for whom a pain assessment is indicated.
  EP 2: Individuals for whom a physical pain assessment is indicated are either assessed and treated by the organization or referred for assessment.

CTS.02.01.11: Screens all individuals for nutritional status.
  EP 1: Screens to identify those for whom a nutritional assessment is indicated.
  EP 2: Individuals for whom a nutritional assessment is indicated are either assessed and treated by the organization or referred.
  EP 3: For organizations that assess nutritional status, the assessment identifies those who may be at moderate or high nutritional risk.

CTS.02.01.15: Screens for legal issues as relevant.
  EP 1: Identifies individuals for whom a legal assessment is indicated.
  EP 3: For organizations that assess legal status, information collected includes at least: legal history, current legal status, pending charges, probation/parole status, and legal issues affecting treatment.""",
    },
    {
        "id": "assessment",
        "name": "Assessment (CTS.02.02-03)",
        "standards": """\
CTS.02.02.01: Collects assessment data on each individual.
  EP 1: Collects information about the individual's needs, strengths, preferences, and goals.
  EP 3: Assessment data on emotional and behavioral functioning.
  EP 4: Assessment data include the individual's short- and long-term goals.
  EP 5: When indicated, evaluations conducted: mental status, psychological, psychiatric, intellectual, neuropsychological.
  EP 6: Family members invited to participate in the assessment process.

CTS.02.02.05: Identifies individuals who may have experienced trauma, abuse, neglect, or exploitation.
  EP 2: Identifies during initial screening/assessment and on an ongoing basis.
  EP 3: Assesses or refers the individual for assessment.

CTS.02.02.07: Reassesses individuals as needed.
  EP 1: The organization reassesses each individual served, as needed.

CTS.02.02.09: Medical histories, physical exams, and lab tests.
  EP 5 (SUD): Toxicological specimens collected with trust/respect while preventing falsification.
  EP 15 (SUD): When initiating medications for SUD, medical assessments and testing follow current national guidelines.

CTS.02.03.07 (SUD): Assessment includes history of addictive behaviors.
  EP 1: Obtains history of alcohol use, drug use, nicotine use, and other addictive behaviors including: age of onset, method of acquiring substance, duration, patterns of use (continuous/episodic/binge), frequency, amounts, and route of substance taken.
  EP 2: Assessment includes: consequences of substance use, physical problems related to use, family substance use history, spirituality and cultural factors, readiness to change, current living arrangements.
  EP 7: Assessments contain: previous care/treatment/services, response to previous treatment, current risks and history of risks related to substance use, relapse history, acute intoxication/withdrawal potential, readiness to change, current living arrangements and options for supportive living environment.

CTS.02.03.13 (SUD): Individual placed in appropriate level of care.
  EP 1: Uses an evidence-based, multidimensional admission assessment (e.g., ASAM Criteria, LOCUS) including mental health, medical, and substance-use history for placement at appropriate level of care.

CTS.02.03.15 (SUD): Drug testing to promote safety and quality.
  EP 1: Follows written policy on performing drug testing.
  EP 2: Documents in clinical record: reason for testing, results, and actions based on results.""",
    },
    {
        "id": "treatment_planning",
        "name": "Treatment Planning (CTS.03)",
        "standards": """\
CTS.03.01.01: Plan based on needs, strengths, preferences, and goals.
  EP 1: In collaboration with the individual and family, care decisions are based on information collected about needs, strengths, preferences, goals.
  EP 2: Decisions are collaborative and interdisciplinary when more than one discipline is involved.
  EP 4: Planning includes interventions and services necessary to meet goals.

CTS.03.01.03: Plan reflects assessed needs, strengths, preferences, goals.
  EP 1: Develops a plan reflecting assessed needs, strengths, preferences, goals.
  EP 2: Plan includes: Goals expressed in a manner that captures the individual's words or ideas; Goals that build on the individual's strengths; Factors supporting transition to community integration; Criteria and process for expected discharge/termination.
  EP 3: Objectives of the plan meet the following criteria: Based on identified goals; Include identified steps to achieve the goal(s); Sufficiently specific to assess progress; Expressed in terms that provide indices of progress.
  EP 4: Reevaluates and revises goals/objectives based on changes in needs, preferences, goals, and response to treatment.
  EP 5: Reasons for deferring a goal or objective are documented.
  EP 6: Care provided according to the plan.
  EP 14 (SUD): Develops plan at time of admission reflecting assessed needs, strengths, preferences, and goals.

CTS.03.01.05: Plan addresses family involvement.
  EP 1: Family involved in developing the plan upon consent (adults) or per law/regulation (minors). Family participation documented.

CTS.03.01.07: Referrals documented.
  EP 1: When the organization does not directly provide needed services, it refers to an outside source. Referrals documented in clinical record.
  EP 2: Concurrent care from outside sources that is integral to meeting goals is addressed in the plan.

CTS.03.01.09: Measurement-based care outcomes.
  EP 1: Uses a standardized tool or instrument to monitor progress in achieving care, treatment, or service goals.
  EP 2: Gathers and analyzes data from standardized monitoring. Results used to inform goals and objectives of the plan as needed.
  EP 3: Evaluates outcomes by aggregating and analyzing monitoring data.""",
    },
    {
        "id": "provision",
        "name": "Provision of Care (CTS.04)",
        "standards": """\
CTS.04.01.01: Coordinates care as part of the plan.
  EP 1: Coordinates care provided through internal resources.
  EP 5: When external resources needed, participates in coordinating care.
  EP 6: Process to receive/share relevant information for coordination and continuity when individuals are referred.

CTS.04.01.03: Individual receives education specific to needs.
  EP 1: Education based on needs and abilities.
  EP 2: Learning needs assessment addresses cultural/religious beliefs, emotional barriers, motivation, cognitive limitations, communication barriers.
  EP 4: Individual educated about: safe/effective use of medications, nutrition, safe/effective use of medical equipment, pain management, habilitation/rehabilitation techniques, community resources, how to obtain further treatment, and responsibilities in care.
  EP 5: Content of education presented in an understandable manner.
  EP 7: The individual's comprehension of the education provided is evaluated.

CTS.04.02.33 (SUD): Evidence-based OUD treatment.
  EP 1: Offers individuals with OUD medication to treat opioid use disorder (MOUD) as part of mutually agreed treatment plan.
  EP 2: If providing a referral for MOUD, the organization coordinates care and confirms initiation and continuation of medication.
  EP 3: If initiating MOUD, informs individual about dangers of abrupt discontinuation.

CTS.04.03.35: Medical emergency response.
  EP 8 (SUD): Provides information on how to obtain naloxone for opioid overdose.""",
    },
    {
        "id": "continuity",
        "name": "Continuity of Care (CTS.06) + Safety (NPSG.15)",
        "standards": """\
CTS.06.02.01: Continuity maintained at transfer/discharge.
  EP 1: Process for addressing continuity after transfer, discharge, or termination of services.
  EP 4 (SUD): Discharge planning addresses referrals for continuing outpatient care after last dose of medication and plan for re-entry to treatment if relapse occurs.

CTS.06.02.03: Discharge decisions based on assessed needs.
  EP 1: Identifies physical and psychosocial needs for continuing care.
  EP 2: Individuals told in timely manner of need to plan for discharge.
  EP 3: Planning involves the individual, family, and staff.
  EP 4: When transferred, information provided includes: reason for transfer, individual's physical/psychosocial needs, and summary of care provided.
  EP 5: Discusses discharge plans with individual and family.
  EP 6: Discharge information provided includes: diagnoses, treatment course, medication reconciliation, aftercare plans.
  EP 7: Individual educated about how to obtain further care.
  EP 8: Organization arranges for or helps arrange continuing care.
  EP 9: Discharge instructions provided in form individual can understand.

CTS.06.02.05: Information exchanged with other providers.
  EP 1: Communicates pertinent information to receiving organization/provider.
  EP 2: Information shared includes: reason for transfer/discharge, individual's physical/psychosocial needs, summary of care provided, and community resources/referrals.

NPSG.15.01.01: Reduce the risk for suicide.
  EP 1: Environmental risk assessment for suicide attempt features.
  EP 2: Screen ALL individuals for suicidal ideation using a validated screening tool.
  EP 3: Use evidence-based process to conduct suicide assessment for those screening positive. Directly asks about ideation, plan, intent, behaviors, risk factors, and protective factors.
  EP 4: Document overall level of risk for suicide AND the plan to mitigate the risk.
  EP 5: Follow written policies for care of at-risk individuals including: staff training, guidelines for reassessment, monitoring of high-risk individuals.
  EP 6: Follow policies for counseling and follow-up care at discharge for individuals at risk for suicide.""",
    },
    {
        "id": "rights_records_meds",
        "name": "Rights (RI) + Records (RC) + Medications (NPSG.03, MM) + Equity (NPSG.16)",
        "standards": """\
RI.01.01.01: Organization respects the rights of the individual served.
  EP 2: Individual informed of their rights (signed acknowledgment in chart).
  EP 3: If disoriented at entry, re-informed when able to understand.
  EP 6: Respects cultural and personal values, beliefs, and preferences.

RI.01.01.03: Right to receive information in understandable manner.
  EP 1: Information provided tailored to individual's language and ability.
  EP 2: Interpreting and translation services provided as necessary.
  EP 3: Communication accommodations for vision, speech, hearing, or cognitive impairments.

RI.01.02.01: Right to collaborate in care decisions.
  EP 1: Individual involved in making decisions about their care.
  EP 4: Right to refuse care documented; individual informed of consequences.

RI.01.03.01: Informed consent.
  EP 2: Informed consent process documented, including discussion of: proposed care/services, goals, benefits, risks, and reasonable alternatives.

RI.01.04.01: Right to know staff responsible for care.
  EP 1: Individual informed of name of primary staff member and other staff providing care.

RC.01.01.01: Complete and accurate clinical records.
  EP 5: Record includes required clinical content: information supporting diagnosis, justifying care provided, documenting course and results.
  EP 6: Uses standardized formats.
  EP 7: All entries dated.

RC.01.02.01: Entries authenticated.
  EP 3: Author of each entry identified.
  EP 4: Entry authenticated by author (signature, electronic, or initials with credentials).

RC.01.03.01: Timely documentation.
  EP 2: Follows written policy requiring timely entry.

RC.02.01.01: Record contains required demographics and clinical information.
  EP 1: Demographics include: name, address, DOB, sex, family/representative contact info, preferred language, special communication needs.
  EP 4: Additional information as appropriate: advance directives, informed consent, consent for admission, documentation of family involvement, unusual occurrences.

RC.02.04.01: Discharge information in record.
  EP 3: Discharge summary includes: reason for acceptance, care/services provided, condition at discharge, information given to patient/family (written instructions, medications, follow-up care).

NPSG.03.06.01: Maintain and communicate accurate medication information.
  EP 1: Obtain and/or update current medication list at first contact and when medications change.
  EP 2: Define types of medication information collected (name, dose, route, frequency, purpose).
  EP 4: Provide written medication information to individual at end of encounter or discharge.
  EP 5: Explain importance of managing medication information to individual.

NPSG.16.01.01: Improving health outcomes for all individuals served.
  EP 2: Assess health-related social needs (HRSNs) and provide information about community resources.

MM.01.01.01: Medication management planning.
  EP 1: Staff in medication management process have access to: age, sex, diagnoses/conditions, allergies, sensitivities, current medications, height/weight when necessary, drug/alcohol use, pregnancy/lactation info.

MM.04.01.01: Clear and accurate medication orders.
  EP 9: Diagnosis, condition, or indication exists for each medication ordered.

MM.07.01.01: Monitoring for medication effects.
  EP 1: Monitor side effects and effectiveness as reported by individual or family.
  EP 2: Monitor response based on clinical record and individual's response.

""",
    },
]


def build_section_prompt(section: dict, clinical_document: str) -> str:
    """Build a focused prompt for one TJC section."""
    return f"""\
Audit the following clinical documentation against ONLY these standards.
You MUST produce a finding for EVERY EP listed below — do NOT skip any.

STANDARDS TO AUDIT:
{section['standards']}

CLINICAL DOCUMENTATION:
{clinical_document}
{TJC_SECTION_OUTPUT_FORMAT}"""
