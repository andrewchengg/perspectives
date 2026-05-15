# Making LLMs Output Clinically Accurate Language

> Research on fine-tuning, prompt engineering, terminology accuracy, stigma avoidance, and evaluation methods for clinical-grade LLM output. Compiled May 2026.

---

## Table of Contents

1. [The Problem: AI-Speak vs Clinical Writing](#1-the-problem-ai-speak-vs-clinical-writing)
2. [Prompt Engineering for Clinical Tone (No Training Required)](#2-prompt-engineering-for-clinical-tone)
3. [Clinical Terminology and Vocabulary](#3-clinical-terminology-and-vocabulary)
4. [Stigmatizing Language in SUD Documentation](#4-stigmatizing-language-in-sud-documentation)
5. [Structured Clinical Writing Patterns](#5-structured-clinical-writing-patterns)
6. [Fine-Tuning for Clinical Language](#6-fine-tuning-for-clinical-language)
7. [Evaluating Clinical Language Quality](#7-evaluating-clinical-language-quality)
8. [Production Systems: How the Big Players Do It](#8-production-systems)
9. [Practical Implementation Roadmap](#9-practical-implementation-roadmap)
10. [Sources](#10-sources)

---

## 1. The Problem: AI-Speak vs Clinical Writing

LLMs generate text that sounds like a polished chatbot, not a clinician. Specific failures identified in research ("Write on Paper, Wrong in Practice", 2025):

- **Too verbose**: LLMs generate outputs longer than the input text without specific constraints
- **Too hedging**: "might", "could", "possibly", "it appears" — clinicians write assertively
- **Wrong categorization**: Placing subjective information in wrong SOAP sections
- **Misinterpreting nuance**: Changing "anxious" to "has anxiety" (mood vs. diagnosis)
- **Omitting the obvious**: Leaving out information clinicians would always include
- **Over-explaining**: Providing reasoning that would be obvious to a clinical reviewer

The core issue is **sociotechnical misalignment** — LLMs are trained on general text, not the abbreviated, direct, problem-oriented style of clinical documentation.

---

## 2. Prompt Engineering for Clinical Tone

### The High-Impact Techniques (Ranked)

**1. Few-shot examples (highest impact)**

Research consistently shows few-shot examples are the most effective technique for clinical documentation quality. Key findings:

- 1-2 examples are suboptimal — **3-5 complete examples** are needed
- High-quality clinical outputs require **elaborate few-shot prompts exceeding 1,000 tokens total**
- The model deduces preferred format, terminology, and style from examples
- Examples should come from your **best clinicians' actual writing**

**2. Specific role priming**

"You are a board-certified addiction medicine specialist conducting a utilization review" is better than "You are a doctor." The persona should include:

- Specific credentials
- Specific task context
- Specific audience (e.g., "writing for a clinical peer reviewer at a payer organization")

**3. Explicit anti-hedging instructions**

Clinical documentation style guides explicitly prohibit hedging. Include in system prompt:

```
LANGUAGE RULES:
- Never use: "might", "could", "possibly", "it appears", "seem", "tend",
  "look like", "appear to be", "think", "believe", "doubt", "perhaps",
  "apparently"
- Instead use: "presents with", "criteria are met for", "findings indicate",
  "assessment supports", "documentation demonstrates", "clinical evidence
  supports"
```

**4. Quantified length constraints**

"Be concise" doesn't work. Quantify:

- "Limit each SOAP section to 3-5 sentences"
- "Each dimensional assessment should be 2-3 sentences with one supporting quote"
- "Total output should not exceed 800 words"

**5. Anti-verbosity instructions**

```
Write in the concise, abbreviated style of a clinical progress note. Do not
use complete sentences where clinical shorthand is standard. Do not explain
reasoning that would be obvious to a clinical reviewer. Do not use
transitional phrases or discourse markers.
```

### Recommended System Prompt Structure for UR

```
[ROLE]: Specific clinical role with credentials and context
[TASK]: Precise description of the document type being generated
[CONSTRAINTS]: Clinical language rules (anti-hedging, person-first, terminology)
[FORMAT]: Structural template (SOAP sections, required fields)
[EXAMPLES]: 3-5 complete examples of gold-standard output (>1,000 tokens total)
[INPUT]: The patient data to process
```

The IQVIA "Declarative LLM Prompting" approach structures prompts with explicit instruction layers, context variables, conditional logic branches, and output format constraints. Modular design (dedicated prompts per section) outperforms multi-purpose prompts.

---

## 3. Clinical Terminology and Vocabulary

### Assertive Clinical Language

| Instead of (hedging)                              | Use (clinical)                           |
| ------------------------------------------------- | ---------------------------------------- |
| "Patient seems to have..."                        | "Patient presents with..."               |
| "It appears that..."                              | "Clinical findings indicate..."          |
| "This might suggest..."                           | "Assessment supports a diagnosis of..."  |
| "It's possible that criteria could be met for..." | "Criteria are met for..."                |
| "The patient may benefit from..."                 | "Recommended level of care is..."        |
| "There seems to be a history of..."               | "Patient has a documented history of..." |
| "It looks like the patient is..."                 | "Patient is currently..."                |

### Ensuring Correct Medical Terminology

- Include terminology references in the prompt: "Use DSM-5 diagnostic criteria language", "Reference ASAM 4th Edition dimension names"
- Provide a glossary of required terms vs. prohibited terms
- Use structured output schemas (Pydantic/JSON Schema) that enforce controlled vocabulary values
- For ICD-10/DSM-5/CPT codes: include the specific code set as reference in context

### ASAM-Specific Vocabulary (4th Edition, 2023)

The ASAM 4th Edition updated dimension names:

- Dimension 1: Acute Intoxication and/or Withdrawal Potential
- Dimension 2: Biomedical Conditions and Complications
- Dimension 3: Emotional, Behavioral, or Cognitive Conditions and Complications
- Dimension 4: Readiness to Change
- Dimension 5: Relapse, Continued Use, or Continued Problem Potential
- **Dimension 6: Person-Centered Considerations** (renamed from "Recovery/Living Environment" — now incorporates SDOH, patient preferences, motivational enhancement)

Level-of-care designations: 0.5, 1.0, 2.1, 2.5, 3.1, 3.5, 3.7, 4.0

Documentation should reference the three-component assessment: Level of Care Assessment, Dimensional Admission Criteria, and Level of Care Standards.

---

## 4. Stigmatizing Language in SUD Documentation

### The Scale of the Problem

- **18.4% of clinical notes** contain stigmatizing language (health system study of 546K notes)
- **61.6% of patients** had at least one note with stigmatizing language
- Physician assistants most likely to use it (46.9%), nurses least (4.1%)
- **35.4% of LLM responses** contained stigmatizing language without prompt engineering
- With prompt engineering: only **6.3%** — an **88% reduction**

### The Fix: Prohibited Terms with Alternatives

| Stigmatizing Term                   | Preferred Alternative                      |
| ----------------------------------- | ------------------------------------------ |
| Addict, junkie, user                | Person with substance use disorder         |
| Substance abuse / abuser            | Substance use / substance use disorder     |
| Clean (negative test)               | Negative, substance-free                   |
| Dirty (positive test)               | Positive, actively using                   |
| Drug habit                          | Substance use disorder                     |
| Alcoholic                           | Person with alcohol use disorder           |
| Drug-seeking behavior               | Undertreated pain, unmanaged withdrawal    |
| EtOH abuse                          | Alcohol use disorder                       |
| Former addict                       | Person in recovery                         |
| Opioid replacement                  | Medication for opioid use disorder (MOUD)  |
| Medication-assisted treatment (MAT) | Medications for addiction treatment / MOUD |

### Implementation

Include this in your system prompt:

```
LANGUAGE REQUIREMENTS — SUBSTANCE USE DISORDER:
- Use person-first language at all times
- Never use: "addict", "junkie", "user", "abuser", "substance abuse",
  "clean", "dirty", "drug habit", "alcoholic", "drug-seeking"
- Use instead: "person with [specific] use disorder", "substance use disorder",
  "negative/substance-free", "positive/actively using", "person with alcohol
  use disorder"
- Conditions are diagnosed, not patients: "received a diagnosis of" not
  "was diagnosed as"
- Use "medications for opioid use disorder (MOUD)" not "medication-assisted
  treatment (MAT)" or "opioid replacement"
```

A fine-tuned stigma detection model achieved **97.2% accuracy** and identified novel stigmatizing phrases beyond its training data (Drexel, 2024). This could serve as a post-processing validation layer.

---

## 5. Structured Clinical Writing Patterns

### How Clinicians Actually Write (vs. How LLMs Write)

| Clinical Writing                    | LLM Default                             |
| ----------------------------------- | --------------------------------------- |
| Abbreviated, shorthand              | Complete sentences, formal              |
| Problem-oriented                    | Narrative flow                          |
| Direct, no throat-clearing          | "Based on the available information..." |
| Implicit clinical reasoning         | Explains everything explicitly          |
| Varies by individual clinician      | Standardized, over-consistent           |
| Concise to the point of telegraphic | Verbose, polished                       |

### Structural Templates

**SOAP** (most common for progress notes):

- **S**ubjective: Patient's reported symptoms, concerns
- **O**bjective: Measurable findings, observations, vital signs
- **A**ssessment: Clinical interpretation, diagnosis
- **P**lan: Treatment decisions, next steps

**DAP** (condensed):

- **D**ata: Combined subjective + objective
- **A**ssessment: Clinical interpretation
- **P**lan: Treatment decisions

John Snow Labs released a dedicated SOAP note generator model (`jsl_meds_text2soap_v1`) that converts unstructured clinical text into structured SOAP format.

### For Utilization Review Specifically

UR letters have unique requirements vs. progress notes:

- **Payer-facing language**: Must justify medical necessity to a reviewer at an insurance company
- **Criteria-based structure**: Organized around specific clinical criteria (ASAM dimensions, InterQual, MCG)
- **Evidence-driven**: Every assertion must cite specific clinical documentation
- **Decisional tone**: Clear recommendation, not equivocation

No published studies specifically address LLM-generated UR letters — most research focuses on progress notes and ambient scribing. This is a gap.

---

## 6. Fine-Tuning for Clinical Language

### When Prompt Engineering Isn't Enough

For tasks requiring nuanced clinical language (not just classification or extraction), **DPO after SFT** significantly outperforms SFT alone:

| Metric                                  | SFT Only | SFT + DPO | Improvement        |
| --------------------------------------- | -------- | --------- | ------------------ |
| Clinical reasoning accuracy (Llama3-8B) | Baseline | +8%       | DPO adds reasoning |
| Triage F1                               | 0.58     | 0.74      | +27.6%             |
| Summarization quality (Likert 1-5)      | 4.21     | 4.34      | +3.1%              |

### DPO for Clinical Documentation (Heart Failure Study)

Applied DPO to nursing documentation using Mistral-7B with 8,838 MIMIC-III nursing notes and 21,210 preference pairs:

- BLEU score: **+84%**
- BERTScore: **+7.6%**
- Expert-rated accuracy: **65.2 → 79.6**
- Eliminated hallucinations
- Recovered omitted clinical parameters
- Adopted SOAP formatting
- Replaced vague descriptions with specific measurements

### Practical Fine-Tuning Path

**QLoRA makes this feasible on modest hardware:**

- ~0.5 GB VRAM per 1 GB of model size (vs 2+ GB for standard LoRA)
- LLaMA-3-8B fine-tuned in **58 hours on a single 48GB GPU**
- Combined QLoRA + FSDP + Sequence Packing: **58.3% memory reduction, 5x speedup**
- QLoRA performance is only 2-4 points lower than full LoRA — negligible trade-off

**Recipe:**

1. Collect 1,000-5,000 examples of clinician-written UR text (gold standard)
2. Generate AI drafts for the same cases
3. Have clinicians rate/edit to create preference pairs (chosen vs. rejected)
4. SFT on the gold standard examples
5. DPO on the preference pairs
6. Fine-tune with QLoRA on a base medical model (OpenBioLLM, MedGemma, Meditron)

### Notable Medical Base Models

| Model                | Base      | Best For                              |
| -------------------- | --------- | ------------------------------------- |
| **Meditron-70B**     | Llama-2   | Clinical guidelines, PubMed knowledge |
| **OpenBioLLM-70B**   | Llama-3   | Broad biomedical tasks                |
| **BioMistral-7B**    | Mistral   | Lightweight, PubMed-trained           |
| **MedGemma-27B**     | Gemma 3   | Supports LoRA fine-tuning, multimodal |
| **Llama-3-Meditron** | Llama-3.1 | Medical instruction following         |

---

## 7. Evaluating Clinical Language Quality

### PDSQI-9 (The Standard Instrument, 2025)

Provider Documentation Summarization Quality Instrument — adapted from the validated PDQI-9 specifically for LLM-generated clinical text. Evaluates nine dimensions:

1. **Cited** — evidence-linked
2. **Accurate** — factually correct
3. **Thorough** — complete
4. **Useful** — clinically relevant
5. **Organized** — well-structured
6. **Comprehensible** — clear
7. **Succinct** — concise
8. **Synthesized** — integrated
9. **Non-stigmatizing** — absence of stigmatizing language

Validation: Cronbach's alpha **0.879**, ICC **0.867**. Strong enough for production use.

### Clinician Preference Studies

Blinded evaluations found:

- Reviewers **preferred AI-generated notes 47%** of the time vs. 39% for physician-authored
- AI notes rated as more thorough and better organized
- AI notes rated as **less succinct and more prone to hallucination**
- Hallucinations in 20% of human-written notes vs. 31% of AI-generated
- The **CLEVER framework** found doctors preferred smaller specialized medical LLMs over GPT-4o by **45-92%** on factuality, clinical relevance, and conciseness

### Automated Evaluation

**LLM-as-Judge** for clinical quality achieved **ICC of 0.818** against human evaluators — strong enough for production quality monitoring. Use for:

- Continuous monitoring of output quality
- A/B testing prompt changes
- Regression testing after model updates
- Flagging outputs that need human review

---

## 8. Production Systems

### Abridge (Most Relevant Architecture)

- Processes **1+ million clinical encounters per week** across 150+ health systems
- Trained on **proprietary dataset of 1.5+ million medical encounters**
- Key differentiator: **"Linked Evidence"** — every sentence links back to exact moment in conversation
- Published research on "Confabulation Elimination" (hallucination prevention)
- Clinician-in-the-loop evaluation before deploying any AI update
- Deployed at Kaiser Permanente across 40-hospital system

### Nuance DAX Copilot (Microsoft/Epic)

- **150+ health systems** as of 2024
- Records doctor-patient conversations, drafts notes in Epic
- **50% reduction in documentation time**, **70% reduction in burnout**
- 20.4% decrease in per-visit note time (46-clinician study)

### Common Patterns Across All Production Systems

1. **Clinician-in-the-loop review** — AI generates drafts, clinicians review and sign
2. **Evidence linking** — tying generated text back to source audio/transcript/notes
3. **Specialty-specific models** — different documentation patterns per specialty
4. **Iterative deployment** — extensive clinician evaluation before production rollout
5. **Structured output** — generating into predefined clinical document formats

---

## 9. Practical Implementation Roadmap

### Phase 1: Prompt Engineering (Immediate, No Training)

1. **Build a detailed system prompt** with:
   - Specific clinical role and credentials
   - Document type and audience
   - Anti-hedging word list with preferred alternatives
   - Stigmatizing language prohibition list
   - Quantified length constraints per section

2. **Include 3-5 few-shot examples** (>1,000 tokens total) of gold-standard UR text from your best clinicians

3. **Use structured output schemas** (Pydantic/JSON) enforcing clinical document structure and controlled vocabulary

4. **Expected impact**: 88% reduction in stigmatizing language, significant improvement in tone and conciseness

### Phase 2: Evaluation Pipeline (Week 2-4)

5. **Adopt PDSQI-9** for systematic evaluation across nine quality dimensions

6. **Set up LLM-as-Judge** automated monitoring (ICC 0.818 vs human evaluators)

7. **Run blinded clinician preference study**: AI output vs. human-written notes, 20+ cases

### Phase 3: Fine-Tuning (Month 2-3)

8. **Collect preference pairs** from clinical reviewers editing AI drafts (target: 1,000-5,000 pairs)

9. **SFT then DPO** on a medical base model using QLoRA (single 48GB GPU, ~58 hours)

10. **Build stigmatizing language detector** as post-processing validation (97% accuracy achievable)

### Phase 4: Production Hardening (Month 3+)

11. **Evidence linking** — every generated sentence must trace to source documentation

12. **Specialty-specific tuning** — different prompt/model configurations for different UR types

13. **Regression testing** — automated quality monitoring on every model/prompt update

---

## 10. Sources

### Clinical Language and Documentation

- [Write on Paper, Wrong in Practice: LLMs and Clinical Notes (2025)](https://arxiv.org/html/2509.04340)
- [Prompt Engineering in Clinical Practice (JMIR 2025)](https://www.jmir.org/2025/1/e72644)
- [Physician Prompt Engineering](https://physicianpromptengineering.com/)
- [IQVIA Declarative LLM Prompting](https://www.iqvia.com/blogs/2024/04/prompt-and-proper-how-iqvia-is-using-declarative-llm)
- [Prompt Engineering Paradigms for Medical Applications (JMIR Scoping Review)](https://www.jmir.org/2024/1/e60501)

### Fine-Tuning

- [SFT vs DPO for Clinical Medicine (JMIR 2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12457693/)
- [DPO for Heart Failure Nursing Documentation](https://arxiv.org/html/2510.05410v1)
- [ClinAlign: Scaling Healthcare Alignment from Clinician Preference](https://arxiv.org/html/2602.09653v2)
- [Fine-Tuning LLaMA-3 with QLoRA for Clinical Documentation](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2024.1493716/full)
- [QLoRA for Clinical Data Extraction](https://www.medrxiv.org/content/10.1101/2025.10.21.25338506v1.full.pdf)
- [RLHF Pipeline for Clinical LLMs (IntuitionLabs)](https://intuitionlabs.ai/articles/rlhf-pipeline-clinical-llms)
- [Mayo Clinic: Fine-Tuning LLMs for Specialized Use Cases](<https://www.mcpdigitalhealth.org/article/S2949-7612(24)00114-7/fulltext>)

### Medical LLMs

- [OpenBioLLM (Hugging Face)](https://huggingface.co/blog/aaditya/openbiollm)
- [BioMistral-7B](https://huggingface.co/BioMistral/BioMistral-7B)
- [Meditron-70B](https://arxiv.org/abs/2311.16079)
- [MedGemma (Google)](https://developers.google.com/health-ai-developer-foundations/medgemma)

### Stigmatizing Language

- [Detecting Stigmatizing Language in Clinical Notes (PMC 2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12363688/)
- [LLMs Use Stigmatizing Language About SUD (Mass General Brigham)](https://www.massgeneralbrigham.org/en/about/newsroom/press-releases/llms-stigmatizing-language-alcohol-substance-use-disorder)
- [Drexel LLM for Stigmatizing Language Detection](https://drexel.edu/news/archive/2024/December/LLM-substance-use-disorder-stigmatizing-language)
- [NIDA Words Matter Language Guide](https://www.in.gov/recovery/files/Stigma-AddictionLanguageGuide-v3.pdf)
- [Patient-Centered Documentation Guidelines (PMC 2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11791454/)

### Evaluation

- [PDSQI-9: Documentation Summarization Quality Instrument](https://arxiv.org/html/2501.08977v1)
- [Open-Source PDQI-9 Evaluation Tool](https://arxiv.org/abs/2503.16504)
- [Assessing AI-Generated Clinical Notes Quality (Frontiers 2025)](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1691499/full)
- [CLEVER: Clinical LLM Evaluation by Expert Review](https://ai.jmir.org/2025/1/e72153)
- [Evaluating Clinical AI Summaries with LLM-as-Judge](https://www.nature.com/articles/s41746-025-02005-2)

### Production Systems

- [Abridge AI Technology](https://www.abridge.com/ai)
- [Abridge AI Evaluation Science](https://www.abridge.com/ai/science-ai-evaluation)
- [Nuance DAX Copilot + Epic](https://www.epic.com/epic/post/nuance-and-epic-expand-ambient-documentation-integration-across-the-clinical-experience-with-dax-express-for-epic/)
- [John Snow Labs SOAP Note Generator](https://nlp.johnsnowlabs.com/2025/04/09/jsl_meds_text2soap_v1_en.html)

### Standards and Guidelines

- [ASAM Criteria 4th Edition](https://www.asam.org/asam-criteria)
- [Joint Commission Standards](https://www.jointcommission.org/en-us/standards)
