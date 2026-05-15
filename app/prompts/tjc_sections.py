"""
TJC Section-by-Section Prompts — Verbatim from Joint Commission Public Standards Database

Instead of one massive prompt with 41 standards, we split into focused sections.
Each section gets its own LLM call with only its relevant EPs.

All EP text is verbatim from: docs/research/tjc-all-standards-with-eps.txt
Source: Joint Commission Public Standards Database, March 2026 edition.
Program: Behavioral Health Care and Human Services

41 standards, 104 EPs — filtered to chart-auditable items only.
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

# --- Section definitions (verbatim EP text) ---

SECTIONS = [
    {
        "id": "screening",
        "name": "Screening (CTS.02.01)",
        "standards": """\
CTS.02.01.01: The organization has a screening procedure for the early detection of risk of imminent harm to self or others.
  EP 1: The screening procedure determines the need for immediate intervention to protect the individual served or others.
  EP 2: The organization follows its process for responding when an immediate risk of harm to self or others is identified.

CTS.02.01.03: The organization performs screenings and assessments as defined by the organization's policy.
  EP 1: The organization assesses each individual served in accordance with organization policy.
  EP 2: The organization conducts each individual's assessment within the time frame specified by the needs of the individual served, organization policy, and law and regulation.
  EP 3: The organization collects information during screenings and/or assessments about the following: The individual's perceptions of their needs, preferences, and goals for care, treatment, or services; When indicated and available, the family's perceptions and preferences for care, treatment, or services.

CTS.02.01.05: Physical health screening.
  EP 1: For organizations providing care, treatment, or services in non-24-hour settings: The organization follows its written physical health screening process to determine whether an individual served is in need of a medical history and physical examination that is based on the population(s) served and, at a minimum, includes the following: Data to be collected; Time frame for completion of the screening; Screening triggers that indicate the need for a medical history and physical examination.

CTS.02.01.09: The organization screens all individuals served for physical pain.
  EP 1: The organization screens all individuals served to identify those for whom a physical pain assessment is indicated.
  EP 2: Individuals for whom a physical pain assessment is indicated are either assessed and treated by the organization or referred for assessment or treatment.

CTS.02.01.11: The organization screens all individuals served for their nutritional status.
  EP 1: The organization screens all individuals served to identify those for whom a nutritional assessment is indicated. At a minimum, the screening includes questions about the following: Food allergies; Weight loss or gain of 10 pounds or more in the last 3 months; Decrease in food intake and/or appetite; Dental problems; Eating habits or behaviors that may be indicators of an eating disorder, such as bingeing or inducing vomiting.
  EP 2: Individuals for whom a nutritional assessment is indicated are either assessed and treated by the organization or referred for assessment or treatment.
  EP 3: For organizations that assess nutritional status, the assessment identifies those individuals who may be at moderate or high nutritional risk.

CTS.02.01.15: As relevant to care, treatment, or services, the organization screens for the legal issues of the individual served.
  EP 1: A screening identifies individuals for whom a legal assessment is indicated, and the individuals who are identified are either assessed by the organization or referred for assessment.
  EP 3: For organizations that assess the legal status of the individual, the information to be collected includes at least the following: A legal history; A preliminary discussion to determine how much the individual's legal situation will influence their progress in care, treatment, or services, and the urgency of the legal situation; The relationship between the presenting conditions and legal involvement.""",
    },
    {
        "id": "assessment",
        "name": "Assessment (CTS.02.02-03)",
        "standards": """\
CTS.02.02.01: The organization collects assessment data on each individual served.
  EP 1: The organization collects information about the individual's needs, strengths, preferences, and goals.
  EP 3: As relevant to care, treatment, or services, the assessment data collected about the individual's emotional and behavioral functioning include at least the following: History of emotional functioning; History of behavioral functioning; Addictive behaviors as a primary or a co-occurring condition(s), including the use of alcohol, other drugs, gambling, or other addictive behaviors by the individual served and family members; Current emotional functioning; Current behavioral functioning.
  EP 4: The assessment data collected include the individual's short- and long-term personal goal(s).
  EP 5: When indicated, the following evaluations are conducted: Mental status; Psychological; Psychiatric; Intellectual and cognitive functioning.
  EP 6: Family members are invited to participate in the assessment process as relevant to the care, treatment, or services provided, and the age and preference of the individual served.

CTS.02.02.05: The organization identifies individuals who may have experienced trauma, abuse, neglect, or exploitation.
  EP 2: The organization identifies individuals who may have experienced trauma, abuse, neglect, or exploitation during initial screening and assessment and on an ongoing basis.
  EP 3: The organization assesses the individual who may have experienced trauma, abuse, neglect, or exploitation or refers the individual for such assessment.

CTS.02.02.07: Reassessment.
  EP 1: The organization reassesses each individual served, as needed.

CTS.02.02.09: The organization has a process to provide medical histories, physical examinations, and diagnostic and laboratory tests.
  EP 5: For organizations providing care, treatment, or services to individuals with addictions: The program collects toxicological specimens in a manner that demonstrates trust and respect while taking reasonable steps to prevent falsification of samples.
  EP 15: For programs providing medications for substance use disorders: When initiating medications for substance use disorders, the program makes certain that medical assessments and testing are done according to current national guidelines established for the treatment being used.

CTS.02.03.07: For organizations providing care, treatment, or services to individuals with addictions: The assessment includes the individual's history of addictive behaviors.
  EP 1: For organizations providing care, treatment, or services to individuals with addictions: The organization obtains the individual's history of alcohol use, drug use, nicotine use, and other addictive behaviors. The history includes the following information: Age of onset; Method of acquiring substance; Duration; Patterns of use (for example, continuous, episodic, binge); Frequency, amounts, and route of the substance that is taken.
  EP 2: For organizations providing care, treatment, or services to individuals with addictions: The assessment includes the following: Consequences of substance use; Physical problems related to use; Family substance use history; Spirituality and cultural factors; Readiness to change; Current living arrangements.
  EP 7: For organizations providing care, treatment, or services to individuals with addictions: Assessments of the individual served contain information about the following: Previous care, treatment, or services; Response to previous care, treatment, or services; Current risks and history of risks related to substance use (likelihood of engaging in substance use or substance use-related behaviors that carry significant risk for serious medical, psychological, social, or financial/legal consequences); Acute intoxication and/or withdrawal potential; Needs related to medications for substance use disorders.

CTS.02.03.13: For organizations providing care, treatment, or services to individuals with addictions: The individual served is placed in the appropriate level of care.
  EP 1: For organizations providing care, treatment, or services to individuals with addictions: The organization uses an evidence-based, multidimensional admission assessment that includes, at a minimum, mental health, medical, and substance-use history for placement of the individual at the appropriate level of care.

CTS.02.03.15: For organizations providing care, treatment, or services to individuals with addictions: The organization uses drug testing to promote safety and quality of care.
  EP 1: For organizations providing care, treatment, or services to individuals with addictions: The organization follows its written policy on performing drug testing.
  EP 2: For organizations providing care, treatment, or services to individuals with addictions: The organization documents in the individual's clinical/case record the reason for drug testing, the results, and actions based on the results.""",
    },
    {
        "id": "treatment_planning",
        "name": "Treatment Planning (CTS.03)",
        "standards": """\
CTS.03.01.01: The organization bases the planned care, treatment, or services on the needs, strengths, preferences, and goals of the individual served.
  EP 1: In collaboration with the individual served and, as appropriate, their family, the organization makes care, treatment, or service decisions that are based on information it has collected about the individual's needs, strengths, preferences, and goals.
  EP 2: Care, treatment, or service decisions are collaborative and interdisciplinary when more than one discipline is involved in the care, treatment, or services of the individual served.
  EP 4: Planning for care, treatment, or services includes interventions and services necessary to meet the identified goals.

CTS.03.01.03: The organization has a plan for care, treatment, or services that reflects the assessed needs, strengths, preferences, and goals of the individual served.
  EP 1: The organization develops a plan for care, treatment, or services that reflects the assessed needs, strengths, preferences, and goals of the individual served.
  EP 2: The plan for care, treatment, or services includes the following: Goals that are expressed in a manner that captures the individual's words or ideas; Goals that build on the individual's strengths; Factors that support the transition to community integration when identified as a need during assessment; The criteria and process for the individual's expected successful transfer and/or discharge/termination of services, which the organization discusses with the individual.
  EP 3: The objectives of the plan for care, treatment, or services meet the following criteria: They are based on identified goals; They include identified steps to achieve the goal(s); They are sufficiently specific to assess the progress of the individual served; They are expressed in terms that provide indices of progress.
  EP 4: The organization reevaluates and, when necessary, revises the goals and objectives of the plan for care, treatment, or services based on change(s) in the individual's needs, preferences, and goals and the individual's response to care, treatment, or services. If no change(s) occurs, the goals and objectives are reevaluated at a specified time interval established by organization policy.
  EP 5: Reasons for deferring a goal, or the objectives leading toward or related to a goal, are documented.
  EP 6: The organization provides care, treatment, or services for each individual served according to the plan for care, treatment, or services.
  EP 14: For organizations providing care, treatment, or services to individuals with addictions: The organization develops a plan for care, treatment, or services at the time of admission or entry into care that reflects the assessed needs, strengths, preferences, and goals of the individual served.

CTS.03.01.05: The plan for care, treatment, or services addresses the family's involvement.
  EP 1: The family of the individual served is involved in developing the plan for care, treatment, or services upon consent from the individual (if an adult) or in accordance with law and regulation (if a minor), unless such participation is contraindicated. Family participation is documented.

CTS.03.01.07: When individuals served need additional care, treatment, or services not offered by the organization, referrals are made and documented in the clinical/case record.
  EP 1: When the organization does not directly provide care, treatment, or services needed by the individual served, it refers the individual to an outside source. Referrals are documented in the clinical/case record.
  EP 2: Concurrent care, treatment, or services provided by an outside source that are integral to meeting goals and objectives are addressed in the plan for care, treatment, or services.

CTS.03.01.09: The organization assesses the outcomes of care, treatment, or services provided to the individual served.
  EP 1: The organization uses a standardized tool or instrument to monitor the individual's progress in achieving the individual's care, treatment, or service goals.
  EP 2: The organization gathers and analyzes the data generated through standardized monitoring, and the results are used to inform the goals and objectives of the individual's plan for care, treatment, or services as needed.
  EP 3: The organization evaluates the outcomes of care, treatment, or services provided to the population(s) it serves by aggregating and analyzing the data gathered through the standardized monitoring effort.""",
    },
    {
        "id": "provision",
        "name": "Provision of Care (CTS.04)",
        "standards": """\
CTS.04.01.01: The organization coordinates the care, treatment, or services provided to an individual served as part of the plan for care, treatment, or services and in a manner consistent with the organization's scope of care, treatment, or services.
  EP 1: The organization coordinates the care, treatment, or services provided through internal resources to an individual served.
  EP 5: When external resources are needed, the organization participates in coordinating care, treatment, or services with these resources.
  EP 6: The organization has a process to receive or share relevant information about the individual served to facilitate coordination and continuity when individuals are referred to other care, treatment, or service providers.

CTS.04.01.03: The individual served receives education and training specific to the individual's needs and abilities consistent with the care, treatment, or services provided.
  EP 1: Education provided is based on the needs and abilities of the individual served.
  EP 2: The assessment of learning needs addresses the individual's cultural and religious beliefs, emotional barriers, desire and motivation to learn, physical or cognitive limitations, and barriers to communication.
  EP 4: Based on the assessed needs and abilities of the individual served and the organization's scope of care, treatment, or services, the individual is educated about the following: The plan for care, treatment, or services; Basic health practices and safety; The safe and effective use of medications; Nutrition interventions, modified diets, and oral health, as needed; Habilitation or rehabilitation techniques to help them reach the maximum level of independence possible.
  EP 5: The content of the education provided to the individual served is presented in an understandable manner.
  EP 7: The individual's comprehension of the education provided is evaluated.

CTS.04.02.33: For organizations providing care, treatment, or services for opioid use disorder to individuals with addictions: The organization provides evidence-based treatment for opioid use disorder, including medications for opioid use disorder.
  EP 1: For organizations providing care, treatment, or services for opioid use disorder to individuals with addictions: As indicated by evidence-based practice, the organization offers individuals served who have an opioid use disorder medication to treat opioid use disorder (MOUD) as part of their mutually agreed upon treatment plan. The MOUD can be provided by the organization, through contractual agreement, or through a referral.
  EP 2: For organizations providing care, treatment, or services for opioid use disorder to individuals with addictions: If the organization provides a referral for medication to treat opioid use disorder, the organization coordinates their care and confirms initiation and continuation of medication.
  EP 3: For organizations providing care, treatment, or services for opioid use disorder to individuals with addictions: If the organization initiates medications for opioid use disorder, the organization informs the individual served about the dangers of abrupt discontinuation of treatment if they leave the organization for any reason, including but not limited to requiring a different level of care or transferring to a different facility.

CTS.04.03.35: The organization responds to medical emergencies according to organization policy and procedures.
  EP 8: For organizations providing care, treatment, or services to individuals with addictions: The organization provides information on how to obtain life-saving medication in the case of opioid overdose.""",
    },
    {
        "id": "continuity",
        "name": "Continuity of Care (CTS.06) + Safety (NPSG.15)",
        "standards": """\
CTS.06.02.01: Continuity of care, treatment, or services is maintained when an individual served is transferred or after discharge/termination of care, treatment, or services.
  EP 1: The organization has a process for addressing the continuity of care, treatment, or services after transfer, discharge, or termination of care, treatment, or services that includes the following: The transfer of responsibility for care, treatment, or services for the individual served; The reason(s) for transfer, discharge, or termination of care, treatment, or services; Mechanisms for internal and external transfer; Identification of the person who has accountability and responsibility for the safety and well-being of the individual served during a transfer.
  EP 4: For programs providing medications for substance use disorders: The discharge planning process addresses referrals for continuing outpatient care after the last dose of medication and the plan for re-entry to treatment if relapse occurs.

CTS.06.02.03: When an individual served is transferred or discharged or when care, treatment, or services are terminated, the organization bases the decision on the assessed needs of the individual and the organization's capabilities.
  EP 1: The organization identifies the physical and psychosocial needs for continuing care of the individual served.
  EP 2: Individuals served are told in a timely manner of the need to plan for discharge or transfer to another organization or level of care, treatment, or services.
  EP 3: Planning for transfer, discharge, or termination of care, treatment, or services involves the individual served, their family, if applicable, and staff.
  EP 4: When the individual served is transferred, information provided to the individual includes the following: The reason they are being transferred; Alternatives to transfer, if any.
  EP 5: The organization discusses plans for transfer, discharge, or termination of care, treatment, or services, or changes in these plans, with the individual served and, with the individual's consent, their family. If the individual is a child or youth, the organization acts in accordance with law and regulation.
  EP 6: When the individual served is discharged or care, treatment, or services are terminated, information provided to the individual and, if applicable, their family includes the following: The reason(s) the individual is being discharged or care, treatment, or services are being terminated; The anticipated need for continued care, treatment, or services after discharge or termination of care, treatment, or services.
  EP 7: When indicated, the individual served is educated about how to obtain further care, treatment, or services to meet their identified needs.
  EP 8: When indicated and before discharge or termination of care, treatment, or services, the organization arranges for or helps the family arrange for care, treatment, or services needed to meet the needs of the individual served after discharge.
  EP 9: The organization provides the individual served and the individual's family, if applicable, discharge or termination of care, treatment, or services instructions in a form the individual can understand.

CTS.06.02.05: Pertinent information related to care, treatment, or services is exchanged with other providers when an individual served is transferred or discharged or when care, treatment, or services are terminated.
  EP 1: The organization communicates pertinent information to any organization or provider to which the individual served is transferred or discharged.
  EP 2: The information shared includes the following: The reason(s) for transfer, discharge, or termination of care, treatment, or services; Relevant biopsychosocial status at transfer, discharge, or termination of care, treatment, or services; A summary of care, treatment, or services provided and progress made toward goals; Community resources or referrals provided to the individual served.

NPSG.15.01.01: Reduce the risk for suicide.
  EP 1: The organization conducts an environmental risk assessment that identifies features in the physical environment that could be used to attempt suicide and takes necessary action to minimize the risk(s) (for example, removal of anchor points, door hinges, and hooks that can be used for hanging).
  EP 2: Screen all individuals served for suicidal ideation using a validated screening tool.
  EP 3: Use an evidence-based process to conduct a suicide assessment of individuals served who have screened positive for suicidal ideation. The assessment directly asks about suicidal ideation, plan, intent, suicidal or self-harm behaviors, risk factors, and protective factors.
  EP 4: Document individuals' overall level of risk for suicide and the plan to mitigate the risk for suicide.
  EP 5: Follow written policies and procedures addressing the care of individuals served identified as at risk for suicide. At a minimum, these should include the following: Training and competence assessment of staff who care for individuals served at risk for suicide; Guidelines for reassessment; Monitoring individuals served who are at high risk for suicide.
  EP 6: Follow written policies and procedures for counseling and follow-up care at discharge for individuals served identified as at risk for suicide.""",
    },
    {
        "id": "rights_records_meds",
        "name": "Rights (RI) + Records (RC) + Medications (NPSG.03, MM) + Equity (NPSG.16)",
        "standards": """\
RI.01.01.01: The organization respects the rights of the individual served.
  EP 2: The organization informs the individual served of the individual's rights.
  EP 3: If an individual served is disoriented or lacks capacity to understand rights at the time of entry, they are informed again when they are able to understand.
  EP 6: The organization respects the cultural and personal values, beliefs, and preferences of the individual served.

RI.01.01.03: The organization respects the right of the individual served to receive information in a manner the individual understands.
  EP 1: The organization provides information to the individual served in a manner tailored to the individual's language and ability to understand.
  EP 2: The organization provides interpreting and translation services, as necessary.
  EP 3: The organization communicates with the individual served who has vision, speech, hearing, or cognitive impairments in a manner that meets the needs of that individual.

RI.01.02.01: The organization respects the right of the individual served to collaborate in decisions about their care, treatment, or services.
  EP 1: The organization involves the individual served in making decisions about their care, treatment, or services.
  EP 4: The organization respects the right of the individual served or surrogate decision-maker to refuse care, treatment, or services in accordance with law and regulation.

RI.01.03.01: The organization honors the right of the individual served to give or withhold informed consent.
  EP 2: The informed consent process includes a discussion about the following: The proposed care, treatment, or services for the individual served; The goals and potential benefits and risks of the proposed care, treatment, or services; Reasonable alternatives to the individual's proposed care, treatment, or services. The discussion encompasses risks and benefits related to the alternatives and the risks related to not receiving the proposed care, treatment, or services.

RI.01.04.01: The organization respects the right of the individual served to receive information about the staff responsible for the individual's care, treatment, or services.
  EP 1: The organization informs the individual served of the following: The name of the staff member who has primary responsibility for the individual's care, treatment, or services; The name of the staff member(s) who will provide the individual's care, treatment, or services.

RC.01.01.01: The organization maintains complete and accurate clinical/case records.
  EP 5: The clinical/case record includes the following: Information needed to support the diagnosis or condition of the individual served; Information needed to justify the care, treatment, or services provided to the individual served; Information that documents the course and result of the care, treatment, or services provided to the individual served; Information about the care, treatment, or services provided to the individual served that promotes continuity among staff and providers.
  EP 6: The organization uses standardized formats to document the care, treatment, or services it provides to individuals served.
  EP 7: All entries in the clinical/case record are dated.

RC.01.02.01: Entries in the clinical/case record are authenticated.
  EP 3: The author of each clinical/case record entry is identified in the clinical/case record.
  EP 4: Entries in the clinical/case record are authenticated by the author. Information introduced into the clinical/case record through transcription or dictation is authenticated by the author.

RC.01.03.01: Documentation in the clinical/case record is entered in a timely manner.
  EP 2: The organization follows its written policy requiring timely entry of information into the clinical/case record of the individual served.

RC.02.01.01: The clinical/case record contains information that reflects the care, treatment, or services provided to the individual served.
  EP 1: The clinical/case record contains the following demographic information: The name, address, date of birth, and sex of the individual served; The name and contact information for the individual's family and any legally authorized representative; The preferred language and any special communication needs of the individual served.
  EP 4: As needed to provide care, treatment, or services, the clinical/case record contains the following additional information: Any advance directives; Any informed consent; Any documentation of protective services; Any documentation of consent by the individual served, family, or guardian for admission; care, treatment, or services; evaluation; continuing care; or research; Any records of communication with the individual served, such as telephone calls or e-mail; Any documentation of involvement in care, treatment, or services by the individual served and, when necessary, their family; Any information on unusual occurrences, such as complications; accidents or injuries to the individual served; procedures that place the individual served at risk or cause pain; other illnesses or conditions that affect care, treatment, or services; or the death of the individual served; Any indications for and episodes of special procedures.

RC.02.04.01: The clinical/case record of the individual served contains discharge information.
  EP 3: The clinical/case record contains the following: A concise discharge summary that includes the reason(s) for acceptance for care, treatment, or services; The care, treatment, or services provided; The condition at discharge of the individual served; Information provided to the individual served and their family (for example, written discharge instructions; medication taken by the individual; follow-up care, treatment, or services).

NPSG.03.06.01: Maintain and communicate accurate medication information for the individual served.
  EP 1: Obtain and/or update information on the medications the individual served is currently taking. This information is documented in a list or other format that is useful to those who manage medications.
  EP 2: Define the types of medication information (for example, name, dose, route, frequency, purpose) to be collected in non-24-hour settings based on situations of individuals served and characteristics of different settings.
  EP 4: For organizations that prescribe medications: Provide the individual served (or family as needed) with written information on the medications the individual should be taking at the end of the encounter (for example, name, dose, route, frequency, purpose).
  EP 5: For organizations that prescribe medications: Explain the importance of managing medication information to the individual served.

NPSG.16.01.01: Improving health outcomes for all the individuals served by the organization is a quality and safety priority.
  EP 2: The organization assesses the health-related social needs (HRSNs) of the individual served and provides information about community resources and support services.

MM.01.01.01: The organization plans its medication management processes.
  EP 1: For organizations that engage in any aspect of the medication management process: The organization follows a written policy that describes that the following information about the individual served is accessible to staff who participate in the medication management process: Age; Sex; Diagnoses/conditions; Allergies; Sensitivities; Height and weight (when necessary); Drug and alcohol use and abuse; Current medications; Pregnancy and lactation information (when necessary); Any additional information required by the organization.

MM.04.01.01: Medication orders are clear and accurate.
  EP 9: For organizations that prescribe medications: A diagnosis, condition, or indication for use exists for each medication ordered.

MM.07.01.01: The organization monitors individuals served to determine the effects of their medication(s).
  EP 1: For organizations that prescribe or administer medications: The organization monitors the side effects and effectiveness of the medications, as reported by the individual served or their family.
  EP 2: For organizations that prescribe or administer medications: The organization monitors the response of the individual served to their medications by taking into account information from the clinical/case record, and the individual's response.""",
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
