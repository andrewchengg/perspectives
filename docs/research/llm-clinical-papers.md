# LLM Research Papers: Long-Context Retrieval, Clinical AI, and Document QA Hallucination

> Compiled May 2026. Peer-reviewed papers with titles, authors, venues, years.

---

## Part 1: Long-Context PDF Retrieval (200K+ Tokens)

### Benchmarks

| Paper                                                                                               | Venue        | Key Finding                                                                                                        |
| --------------------------------------------------------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------ |
| **RULER: What's the Real Context Size of Your Long-Context Language Models?** (Hsieh et al.)        | COLM 2024    | Of 15+ models claiming 32K+, only 4 maintained satisfactory performance. Near-perfect NIAH masks real degradation. |
| **InfiniteBench: Extending Long Context Evaluation Beyond 100K Tokens** (Zhang et al.)              | ACL 2024     | First benchmark with avg data >100K tokens. 12 tasks. Existing models require significant advancement.             |
| **LongBench v2** (Bai et al.)                                                                       | 2024         | 503 questions, 8K-2M words. Best model: 50.1% accuracy. Human baseline: 53.7%.                                     |
| **BABILong: Testing the Limits of LLMs with Long Context Reasoning-in-a-Haystack** (Kuratov et al.) | NeurIPS 2024 | Models effectively use only 10-20% of context. RAG achieves modest 60% regardless of length.                       |
| **Lost in the Middle: How Language Models Use Long Contexts** (Liu et al.)                          | TACL 2024    | U-shaped attention: 30%+ accuracy drop when answer is in middle of 20-doc context.                                 |

### The Critical Hallucination Number

**"How Much Do LLMs Hallucinate in Document Q&A Scenarios?"** (2026, arXiv:2603.08274)

- 35 open-weight models, 3 context lengths, 172 billion tokens consumed
- **At 32K**: Best model fabricates 1.19%; median ~25%
- **At 128K**: Floor triples to 3.19%; only 5/26 models stay below 10%
- **At 200K**: No model stays below 10% fabrication
- Hallucination is "substantial and unavoidable"

### RAG vs Full Context

| Paper                                                                                    | Venue                     | Key Finding                                                                                                                                      |
| ---------------------------------------------------------------------------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Long-Context LLMs Meet RAG** (Xu et al.)                                               | ICLR 2025                 | Output quality initially improves then declines with more passages. Hard negatives are the primary cause. Stronger retrievers can make it worse. |
| **Evaluating RAG vs Long-Context Input for Clinical Reasoning over EHRs** (Myers et al.) | arXiv 2025                | RAG matches or exceeds full-context on clinical EHR tasks while using drastically fewer tokens.                                                  |
| **BriefContext** (Jiang et al.)                                                          | npj Digital Medicine 2025 | Map-reduce RAG improved accuracy from 55.81% to 66.47% on medical QA with LLaMA2-70B.                                                            |

### PDF Extraction

| Paper                                | Venue      | Key Finding                                                                                  |
| ------------------------------------ | ---------- | -------------------------------------------------------------------------------------------- |
| **OmniDocBench** (Ouyang et al.)     | CVPR 2025  | 1,355 pages, 9 doc types, 20K+ annotations. Full end-to-end parsing evaluation.              |
| **Applied AI PDF Parsing Benchmark** | 2025       | 17 parsers, 800+ docs. Legal: 95% accuracy. Academic: 40-60%. Gemini 3 Pro leads text (88%). |
| **PDF Table Extraction Benchmark**   | arXiv 2026 | Docling: 97.9% on complex tables. Unstructured: 100% simple, 75% complex.                    |

### Compression

| Paper                            | Venue      | Key Finding                                                                                 |
| -------------------------------- | ---------- | ------------------------------------------------------------------------------------------- |
| **LLMLingua** (Jiang et al.)     | EMNLP 2023 | Up to 20x compression with 1.5% performance loss.                                           |
| **LongLLMLingua** (Jiang et al.) | ACL 2024   | 21.4% performance boost with 4x fewer tokens. Compression can help by removing distractors. |
| **LLMLingua-2** (Pan et al.)     | ACL 2024   | Token classification for task-agnostic compression. Better generalizability.                |

### Attention Mechanisms

| Paper                                                            | Venue      | Key Finding                                                  |
| ---------------------------------------------------------------- | ---------- | ------------------------------------------------------------ |
| **Efficient Attention Mechanisms for LLMs: A Survey**            | arXiv 2025 | Comprehensive survey: sparse, linear, and hybrid approaches. |
| **Long-Context Generalization with Sparse Attention** (ASEntmax) | arXiv 2025 | Dynamic sparsity avoiding fixed pattern issues.              |
| **SWAA: Sliding Window Attention Adaptation**                    | arXiv 2025 | Architectural fixes for SWA degradation in long context.     |

### Additional Long-Context Papers

- **Found in the Middle: Calibrating Positional Attention Bias** (arXiv:2406.16008, 2024)
- **Hallucinate at the Last in Long Response Generation** (arXiv:2505.15291, 2025) — faithfulness drops below 0.65 in final summary segments
- **Towards Long Context Hallucination Detection** (arXiv:2504.19457, 2025)
- **BOOOOKSCORE** (Chang et al., ICLR 2024) — hierarchical vs incremental for book-length summarization
- **LLMxMapReduce** (ACL 2025) — chunk-process-collapse-reduce for documents exceeding any context window

---

## Part 2: LLMs in Clinical/Medical Field

### Medical Benchmarks & Model Performance

| Paper                                                                 | Venue                      | Key Finding                                                                                |
| --------------------------------------------------------------------- | -------------------------- | ------------------------------------------------------------------------------------------ |
| **Capabilities of GPT-4 on Medical Challenge Problems** (Nori et al.) | arXiv 2023                 | GPT-4: ~87% on USMLE, exceeding pass threshold by 20+ points.                              |
| **Med-PaLM 2** (Singhal et al.)                                       | arXiv 2023                 | 86.5% MedQA, 72.3% MedMCQA. Physicians preferred its answers on 8/9 axes.                  |
| **MedR-Bench**                                                        | Nature Communications 2025 | 1,453 cases. Models >85% on diagnosis but drop on treatment planning.                      |
| **Medmarks**                                                          | arXiv 2025                 | 30 benchmarks, 61 models. Frontier reasoning models (Gemini 3 Pro, GPT-5.2) highest.       |
| **CSEDB Safety Benchmark**                                            | npj Digital Medicine 2025  | 2,069 Q&A items, 32 specialists. Average: 57.2%. 13.3% drop in high-risk scenarios.        |
| **Questioning Our Questions**                                         | BioNLP 2025 (ACL)          | MedQA-to-clinical correlation: Spearman ρ=0.59 only. Benchmarks miss real clinical skills. |

### Domain-Specific Medical LLMs

| Model                          | Paper                     | Venue                                                                          | Key Finding |
| ------------------------------ | ------------------------- | ------------------------------------------------------------------------------ | ----------- |
| **BioMistral** (Labrak et al.) | Findings of ACL 2024      | First multilingual medical LLM evaluation (8 languages).                       |
| **Me-LLaMA** (Xie et al.)      | npj Digital Medicine 2025 | 13B/70B, 129B pre-training tokens. Outperforms GPT-4 on 5/8 tasks with tuning. |
| **Llama-3-Meditron** (EPFL)    | OpenReview 2025           | 8B surpasses all Llama-3.1; 70B outperforms GPT-4, Med-PaLM 2.                 |
| **MEDITRON-70B** (Chen et al.) | arXiv 2023                | Adapted from Llama-2, curated medical corpus.                                  |

### Clinical Note Generation & Summarization

| Paper                                                              | Venue                     | Key Finding                                                                           |
| ------------------------------------------------------------------ | ------------------------- | ------------------------------------------------------------------------------------- |
| **Clinical Safety Framework for LLM Summarization** (Tariq et al.) | npj Digital Medicine 2025 | 12,999 sentences. 1.47% hallucination, 3.45% omission. 44% of hallucinations "major." |
| **LLM vs Physician Discharge Summaries**                           | PubMed 2025               | Comparable quality but LLM summaries more likely to contain errors.                   |
| **AgenticSum**                                                     | arXiv 2026                | Decomposes into select-generate-verify-correct. Uses attention grounding signals.     |
| **LCDS**                                                           | arXiv 2025                | Logic-controlled discharge summaries with source attribution.                         |

### Ambient Scribe Studies

| Paper                       | Venue    | Key Finding                                                     |
| --------------------------- | -------- | --------------------------------------------------------------- |
| **Nuance DAX Cohort Study** | PMC 2024 | Documentation time: 5.3 → 4.54 min/visit (P<0.001).             |
| **Ambient AI Scribe RCT**   | PMC 2025 | 238 physicians randomized to DAX Copilot, Nabla, or usual care. |
| **Abridge Study**           | 2025     | 57 clinicians, 6.2 → 5.3 min/encounter (P<0.001).               |

### Clinical Decision Support

| Paper                                          | Venue                      | Key Finding                                                                                                  |
| ---------------------------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Diagnostic Accuracy: LLMs vs Professionals** | JMIR 2025                  | 30 studies. AI: 52.1%. No significant difference vs physicians overall, but inferior to experts (15.8% gap). |
| **Diagnostic Performance Meta-Analysis**       | npj Digital Medicine 2025  | 83 studies. GPT-4 most evaluated. LLMs comparable to non-expert physicians.                                  |
| **Medication Safety CDS**                      | Cell Reports Medicine 2025 | Co-pilot mode (pharmacist + LLM): 61% accuracy, 1.5x improvement detecting serious harm.                     |
| **NHS Medication Safety**                      | arXiv 2025                 | Dominant failure: contextual reasoning (not missing knowledge). Overconfidence in uncertainty.               |
| **LLM ED Triage**                              | JAMA Network Open 2024     | LLM-based triage evaluation in emergency department.                                                         |
| **Triage Performance Comparison**              | JMIR 2024                  | GPT-4 kappa=0.67 with professionals. Equals untrained ED doctors.                                            |
| **MedAgentBench**                              | NEJM AI 2025               | Virtual EHR environment for benchmarking clinical LLM agents.                                                |

### Substance Use Disorder & Behavioral Health

| Paper                                               | Venue                          | Key Finding                                                   |
| --------------------------------------------------- | ------------------------------ | ------------------------------------------------------------- |
| **Virtual Agents for Alcohol Use Counseling**       | ACM IVA 2024                   | GPT-4 motivational interviewing with virtual platform.        |
| **ChatThero**                                       | arXiv 2025                     | Multi-agent CBT/MI chatbot for addiction recovery. SFT + DPO. |
| **MICA: Secure LLM Chatbot for Alcohol Counseling** | Drug & Alcohol Dependence 2025 | GPT-4 single-session MI. High fidelity and acceptability.     |
| **AI-Augmented MI Therapist-Level Responses**       | ResearchGate 2025              | GPT-4 analyzed with 17 MI behavioral metrics.                 |
| **Therapy as an NLP Task**                          | arXiv 2024                     | Frames therapeutic interaction as NLP problem.                |
| **LLMs in Mental Health: Scoping Review**           | JMIR 2025                      | 95 articles from 4,859 studies.                               |
| **It's Not Only Attention We Need**                 | JMIR Mental Health 2025        | 205 studies. GPT dominates; most use prompting-only.          |

**Note: No papers found on LLMs for ASAM criteria assessment or TJC compliance auditing.**

### Regulatory & Safety

| Paper/Document                            | Source        | Key Point                                                                                              |
| ----------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------ |
| **FDA PCCP Guidance for AI Devices**      | FDA, Dec 2024 | Predetermined change control plans for AI devices.                                                     |
| **FDA AI Lifecycle Guidance**             | FDA, Jan 2025 | Draft lifecycle management for AI-enabled devices.                                                     |
| **FDA AI for Regulatory Decision-Making** | FDA, 2025     | AI use in drug safety/effectiveness decisions.                                                         |
| **ML Medical Devices Authorized in 2024** | PMC 2025      | 1,250+ AI devices authorized. Zero generative AI/LLM devices approved.                                 |
| **TJC/CHAI AI Guidance**                  | Sept 2025     | 7 elements: governance, HIPAA, quality monitoring, incident reporting. Voluntary certification coming. |

### RAG for Clinical QA

| Paper                       | Venue                  | Key Finding                                                                  |
| --------------------------- | ---------------------- | ---------------------------------------------------------------------------- |
| **i-MedRAG** (Xiong et al.) | PSB 2025               | Iterative follow-up queries. 69.68% on MedQA with GPT-3.5 (zero-shot SOTA).  |
| **MedRAG**                  | ACM WWW 2025           | Four-tier hierarchical diagnostic KG + EHR retrieval. Reduces misdiagnosis.  |
| **RAG²** (Sohn et al.)      | NAACL 2025             | Perplexity filtering + LLM rationales as queries. Up to 6.1% over SOTA.      |
| **Agentic Medical KGs**     | Findings of EMNLP 2025 | Bridges LLMs and evolving medical knowledge through agentic KG construction. |
| **MKRAG** (Shi et al.)      | AMIA 2024              | Medical fact acquisition + knowledge injection.                              |

### Fine-Tuning for Clinical Tasks

| Paper                                      | Venue                                | Key Finding                                                            |
| ------------------------------------------ | ------------------------------------ | ---------------------------------------------------------------------- |
| **QLoRA Clinical Extraction**              | medRxiv 2025                         | QLoRA only 1-4 points below full fine-tuning for NER (B-F1=0.82).      |
| **EchoGPT**                                | European Heart J Digital Health 2024 | Llama-2 + QLoRA on 95,506 echo reports. Win rate 87-99% vs other LLMs. |
| **LLaMA-3 for Radiation Oncology Letters** | Frontiers in AI 2024                 | QLoRA fine-tuning in 58 hours on single 48GB GPU.                      |
| **Cancer Staging with LoRA**               | arXiv 2025                           | Llama-3-8B + 4-bit QLoRA for pathology report staging.                 |
| **Weakly Supervised Radiology Extraction** | npj Digital Medicine 2025            | Two-phase on 15K unlabeled Mayo Clinic reports.                        |

### Multi-Agent Systems in Healthcare

| Paper                                  | Venue                     | Key Finding                                                                     |
| -------------------------------------- | ------------------------- | ------------------------------------------------------------------------------- |
| **MDAgents**                           | NeurIPS 2024              | Adaptive solo/group collaboration based on task complexity.                     |
| **MAC Diagnostic Framework**           | npj Digital Medicine 2025 | Multi-agent conversation for rare diseases (302 cases).                         |
| **KG4Diagnosis**                       | arXiv 2024                | Two-tier GP + specialist agents. 362 diseases.                                  |
| **AI Hospital**                        | COLING 2025               | Doctor/Patient/Examiner/Chief Physician agents. GPT-4 still gaps in multi-turn. |
| **Multi-Agent Therapy Recommendation** | arXiv 2025                | Agents simulate multidisciplinary team resolving medical conflicts.             |

---

## Part 3: Document QA Hallucination

### Foundational Papers

| Paper                                                                           | Venue                      | Key Finding                                                                                          |
| ------------------------------------------------------------------------------- | -------------------------- | ---------------------------------------------------------------------------------------------------- |
| **On Faithfulness and Factuality in Abstractive Summarization** (Maynez et al.) | ACL 2020                   | Defines intrinsic (contradicts source) vs extrinsic (not verifiable from source) hallucination.      |
| **Survey of Hallucination in NLG** (Ji et al.)                                  | ACM Computing Surveys 2023 | Canonical survey formalizing hallucination taxonomy across tasks.                                    |
| **FaithEval** (Li et al.)                                                       | ICLR 2025                  | 4.9K samples testing contextual faithfulness. Even top models struggle with counterfactual contexts. |
| **HaluEval** (Li et al.)                                                        | EMNLP 2023                 | 35K samples. ChatGPT fabricates unverifiable info in ~19.5% of queries.                              |

### Faithfulness Metrics

| Paper                          | Venue      | What It Measures                                                           |
| ------------------------------ | ---------- | -------------------------------------------------------------------------- |
| **FactCC** (Kryscinski et al.) | EMNLP 2020 | Weakly-supervised factual consistency model.                               |
| **FEQA** (Durmus et al.)       | ACL 2020   | QA-based faithfulness. Higher correlation than ROUGE.                      |
| **QuestEval** (Scialom et al.) | EMNLP 2021 | Bidirectional QA-based evaluation. Reference-free.                         |
| **SummaC** (Laban et al.)      | TACL 2022  | Fixes NLI granularity mismatch. 74.4% balanced accuracy.                   |
| **UniEval** (Zhong et al.)     | EMNLP 2022 | Multi-dimensional via Boolean QA. 23% higher correlation on summarization. |
| **AlignScore** (Zha et al.)    | ACL 2023   | RoBERTa alignment on diverse tasks. Outperforms prior metrics.             |
| **FActScore** (Min et al.)     | EMNLP 2023 | Atomic fact decomposition. ChatGPT: only 58% on biographies.               |
| **MiniCheck** (Tang et al.)    | EMNLP 2024 | 770M params, GPT-4 level at 400x lower cost.                               |

### Attribution & Provenance

| Paper                                                                | Venue                          | Key Finding                                                                             |
| -------------------------------------------------------------------- | ------------------------------ | --------------------------------------------------------------------------------------- |
| **AIS: Measuring Attribution in NLG** (Rashkin et al.)               | Computational Linguistics 2023 | Defines Attributable to Identified Sources framework. Standard for attribution eval.    |
| **Attributed QA** (Bohnet et al.)                                    | arXiv 2022                     | (answer, attribution) pairs where attribution points into corpus.                       |
| **ALCE: Enabling LLMs to Generate Text with Citations** (Gao et al.) | EMNLP 2023                     | 3 datasets. Even best models lack citation support 50% of time on ELI5.                 |
| **FAVA: Fine-grained Hallucination Detection** (Mishra et al.)       | arXiv 2024                     | Retrieval-augmented system outperforms ChatGPT by up to 38% on hallucination detection. |

### Knowledge Conflicts (Parametric vs Context)

| Paper                                                                | Venue               | Key Finding                                                                                              |
| -------------------------------------------------------------------- | ------------------- | -------------------------------------------------------------------------------------------------------- |
| **Entity-Based Knowledge Conflicts in QA** (Longpre et al.)          | EMNLP 2021          | First formal study. Models over-rely on parametric knowledge.                                            |
| **Adaptive Chameleon or Stubborn Sloth** (Xie et al.)                | ICLR 2024 Spotlight | Paradox: LLMs receptive to coherent external evidence but show confirmation bias with partial conflicts. |
| **LLMs Can Be Easily Distracted by Irrelevant Context** (Shi et al.) | ICML 2023           | Irrelevant context degrades performance. Self-consistency partially mitigates.                           |
| **Hallucination is Inevitable** (Xu et al.)                          | arXiv 2024          | Theoretical proof via computability theory that hallucination cannot be eliminated.                      |

### Reducing Hallucination in Document QA

| Paper                                                      | Venue                | Key Finding                                                                                             |
| ---------------------------------------------------------- | -------------------- | ------------------------------------------------------------------------------------------------------- |
| **Chain-of-Verification (CoVe)** (Dhuliawala et al., Meta) | Findings of ACL 2024 | 4-stage: draft → plan verification → answer independently → revise. Reduces hallucination across tasks. |
| **SelfCheckGPT** (Manakul et al.)                          | EMNLP 2023           | Stochastic samples diverge for hallucinated facts. Higher AUC-PR than grey-box methods.                 |
| **LLM-Augmenter** (Peng et al.)                            | arXiv 2023           | Plug-and-play external knowledge grounding with iterative prompt revision.                              |
| **FaithDial** (Dziri et al.)                               | TACL 2022            | 50K turns of faithful information-seeking dialogue. Benefits generalize zero-shot.                      |

### RAG Faithfulness Evaluation

| Paper                           | Venue          | Key Finding                                                                                                       |
| ------------------------------- | -------------- | ----------------------------------------------------------------------------------------------------------------- |
| **RAGAS** (Es et al.)           | EACL 2024 Demo | Reference-free faithfulness, relevancy, precision, recall. Atomic statement decomposition.                        |
| **ARES** (Saad-Falcon et al.)   | NAACL 2024     | Fine-tunes lightweight judges. Outperforms RAGAS in ranking accuracy.                                             |
| **RGB Benchmark** (Chen et al.) | AAAI 2024      | Tests noise robustness, negative rejection, info integration, counterfactual robustness. LLMs struggle on last 3. |

### Long-Document QA Benchmarks

| Paper                            | Venue      | Key Finding                                                                                |
| -------------------------------- | ---------- | ------------------------------------------------------------------------------------------ |
| **NarrativeQA** (Kocisky et al.) | TACL 2018  | QA over books/scripts. 46,765 pairs. Requires narrative understanding.                     |
| **Qasper** (Dasigi et al.)       | NAACL 2021 | 5,049 questions over NLP papers. Models underperform humans by 27+ F1 points.              |
| **QuALITY** (Pang et al.)        | NAACL 2022 | MCQ on ~5K token passages. Baseline 55.4% vs human 93.5%.                                  |
| **LongBench** (Bai et al.)       | ACL 2024   | 21 datasets, 6 task categories, bilingual. GPT-3.5-Turbo-16k struggles on longer contexts. |

### Clinical Document QA

| Paper                       | Venue        | Key Finding                                                                                         |
| --------------------------- | ------------ | --------------------------------------------------------------------------------------------------- |
| **EHRNoteQA** (Kim et al.)  | NeurIPS 2024 | 962 QA pairs from MIMIC-IV. Requires multi-note reasoning. Spearman 0.78 with clinician evaluation. |
| **Long Context Medical QA** | arXiv 2025   | Tests GPT-4o, Claude 3, Gemini 1.5 on MIMIC. QA performance low even at 32K context.                |
| **VeriFact** (Chung et al.) | NEJM AI 2025 | Fact verification against EHR. 93.2% agreement with clinicians (exceeds inter-rater 88.5%).         |

---

## Key Takeaways

1. **At 200K tokens, hallucination is unavoidable** — no model stays below 10% fabrication rate (172B token study)
2. **RAG matches full-context for clinical tasks** at far lower cost and hallucination risk (Myers et al., ICLR 2025)
3. **Models use only 10-20% of long context** for reasoning (BABILong, NeurIPS 2024)
4. **Compression can improve accuracy** by removing distractors (LongLLMLingua, ACL 2024)
5. **Medical benchmarks poorly predict clinical performance** — Spearman ρ=0.59 only (BioNLP 2025)
6. **No published research on LLMs for ASAM criteria or TJC compliance auditing**
7. **Zero generative AI/LLM devices have FDA approval** for clinical use as of 2025
8. **VeriFact achieves 93.2% clinician agreement** — better than inter-rater agreement (NEJM AI)
9. **44% of clinical hallucinations are "major"** despite only 1.47% overall rate (npj Digital Medicine)
10. **Knowledge conflicts are a fundamental problem** — LLMs show confirmation bias when context partially agrees with parametric memory (ICLR 2024 Spotlight)

---

## Part 4: Cost Optimization & Inference Efficiency

| Paper                                                        | Venue                     | Key Finding                                                                                            |
| ------------------------------------------------------------ | ------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Cost-Effective LLM at Health System Scale** (Klang et al.) | npj Digital Medicine 2024 | Query concatenation: 17x cost reduction bundling 50 tasks/prompt. GPT-4-turbo maintains 90%+ accuracy. |
| **PagedAttention / vLLM**                                    | SOSP 2023                 | Under 4% KV cache waste (vs 60-80% prior). 2-4x throughput improvement.                                |
| **RadixAttention / SGLang**                                  | arXiv 2023                | Radix tree KV cache sharing. Up to 6.4x throughput via automatic prefix reuse.                         |
| **LMCache**                                                  | arXiv 2025                | Up to 15x throughput for document analysis. Warning: context truncation halves cache hit ratio.        |
| **KVShare**                                                  | arXiv 2025                | Semantic-aware cache sharing. Reuses cache for ~60% of requests.                                       |
| **KVTC**                                                     | arXiv 2025                | 20x KV cache compression maintaining reasoning accuracy.                                               |
| **ConTextual**                                               | arXiv 2025                | Clinical text token filtering. ~4x throughput (142 vs 36 summaries/sec) on MIMIC-BHC.                  |
| **Unified Routing and Cascading** (ETH Zurich)               | arXiv 2024                | Cascade routing consistently outperforms routing or cascading alone.                                   |
| **Sherlock**                                                 | arXiv 2025                | Naive verification = 28.9x cost overhead. Selective speculative execution fixes this.                  |

**Anthropic prompt caching**: Cache reads at 10% of base input price. 85% latency reduction. For our pipeline: caching TJC/ASAM standards (~10K tokens) saves ~$27/MTok on every patient after the first.

---

## Part 5: Clinical NER & Information Extraction

| Paper                                                                  | Venue                      | Key Finding                                                                                           |
| ---------------------------------------------------------------------- | -------------------------- | ----------------------------------------------------------------------------------------------------- |
| **Improving LLMs for Clinical NER via Prompt Engineering** (Hu et al.) | JAMIA 2024                 | GPT-4: relaxed F1 0.861 on i2b2 format. Below supervised BERT (~0.90+). Prompt design matters hugely. |
| **Benchmarking LLMs for Biomedical NLP** (Chen et al.)                 | Nature Communications 2025 | Fine-tuned BioBERT averaged F1 0.6536 vs best LLM 0.5131 across 12 datasets. BERT wins 10/12.         |
| **Are We Ready to Switch to LLMs?** (Hu et al.)                        | JAMIA 2026                 | Fine-tuned LLaMA-3-70B outperforms BiomedBERT by 7% F1 on NER on unseen data.                         |
| **Human Level IE with Finetuned LMs** (Liu et al.)                     | Scientific Reports 2025    | LoRA-finetuned Llama-3.1 8B: 90.0% exact match. Non-inferior to human annotator.                      |
| **LLMs are Few-Shot Clinical IE** (Agrawal et al.)                     | EMNLP 2022                 | Foundational: InstructGPT viable for zero/few-shot clinical IE without domain training.               |
| **Beyond Negation Detection** (Kocaman et al.)                         | ECIR 2025                  | Fine-tuned LLM: 0.962 accuracy. GPT-4o: 0.901. Rule-based NegEx: 0.84-0.89.                           |
| **Medication IE with Local LLMs**                                      | JAMIA 2025                 | Fine-tuned Llama: +10 F1 on ADE extraction, +6 on medication reasons (n2c2 2018).                     |
| **TIMER: Temporal IE** (Cui et al.)                                    | npj Digital Medicine 2025  | First temporal benchmark for longitudinal EHRs. 7.3% improvement on human benchmarks.                 |

**Consensus**: Fine-tuned open LLMs (Llama family) closing gap with BERT-family. LLMs win on generalizability; BERT wins on cost and structured extraction with ample training data.

---

## Part 6: Evaluation of AI Clinical Documentation

### Evaluation Frameworks

| Framework              | Venue                     | What It Measures                                                                                  |
| ---------------------- | ------------------------- | ------------------------------------------------------------------------------------------------- |
| **QUEST** (Tam et al.) | npj Digital Medicine 2024 | Quality, Understanding, Expression, Safety, Trust. Min 130 cases, 6 evaluators.                   |
| **SCRIBE**             | npj Digital Medicine 2025 | Simulation + Computational + Reviewer + Intelligent Evaluation. National standard for AI scribes. |
| **PDSQI-9**            | JAMIA 2025                | Validated instrument: organization, clarity, accuracy, utility. ICC=0.867. Cronbach's α=0.879.    |
| **CLEVER**             | JMIR AI 2025              | Blind randomized preference evaluation by MDs. Found small medical LLMs preferred over GPT-4o.    |

### LLM-as-Judge for Clinical Text

GPT-o3-mini achieved **ICC 0.818** with human evaluators on PDSQI-9 instrument (npj Digital Medicine 2025). Reasoning models outperformed non-reasoning models. Evaluation time: 22 seconds per summary.

### Error Taxonomies

| Source                    | Categories                                                                                           |
| ------------------------- | ---------------------------------------------------------------------------------------------------- |
| npj Digital Medicine 2025 | Fabrication (43%), Negation (30%), Contextual (17%), Causality (10%)                                 |
| MIT Media Lab 2025        | Factual errors, outdated references, spurious correlations, incomplete reasoning, fabricated sources |
| Med-HALT 2023             | Reasoning-based + memory-based hallucination tests from multinational exams                          |

### Regulatory Validation

- **FDA**: 97% of AI devices cleared via 510(k). 1,250+ approved. Zero generative AI/LLM devices.
- **TJC/CHAI** (Sept 2025): 7 elements — governance, validation, risk monitoring, incident reporting, training
- **SPIRIT-AI / CONSORT-AI** (Lancet 2020): Standard for reporting clinical AI trials (14 new items)
- **CMS** (Dec 2024): AI tools must respect individual circumstances, not solely algorithmic decisions

---

## Part 7: Knowledge Graphs for Clinical QA

| Paper                                 | Venue                     | Key Finding                                                                                       |
| ------------------------------------- | ------------------------- | ------------------------------------------------------------------------------------------------- |
| **MedRAG**                            | ACM WWW 2025              | Four-tier hierarchical diagnostic KG + EHR retrieval. Reduces misdiagnosis.                       |
| **KARE**                              | ICLR 2025                 | Multi-source KG + community detection. 10.8-15.0% improvement on MIMIC-III/IV.                    |
| **DR.KNOWS**                          | JMIR AI 2025              | Multi-hop UMLS traversal. 107 SNOMED CT relations for diagnostic reasoning.                       |
| **KRAGEN**                            | Bioinformatics 2024       | Graph-of-thoughts prompting against KG vector DB. Open source (Cedars-Sinai).                     |
| **KG-RAG with SPOKE**                 | Bioinformatics 2024       | 71% boost for Llama-2 on medical QA. 50% token reduction.                                         |
| **AddictO**                           | UCL Discovery             | Formal addiction ontology on BFO. Maintained on GitHub.                                           |
| **Baker & Saba (1998)**               | Drug & Alcohol Dependence | First paper showing ASAM criteria can be automated as decision tree.                              |
| **LLM-Assisted Conformance Checking** | Springer 2025             | Extracts normative rules from guidelines, checks patient event logs. Closest to our TJC approach. |

**Critical gaps**: No open ASAM decision logic ontology (CONTINUUM is proprietary). No TJC CTS standards encoded as computable knowledge.

---

## Part 8: Explainability in Clinical AI

| Paper                                                            | Venue                     | Key Finding                                                                           |
| ---------------------------------------------------------------- | ------------------------- | ------------------------------------------------------------------------------------- |
| **Ignore, Trust, or Negotiate** (Sivaraman et al.)               | CHI 2023                  | 4 clinician behavior patterns with AI. Partial reliance may impact efficacy.          |
| **Explanations Can Reduce Overreliance** (Vasconcelos et al.)    | CSCW 2023                 | Explanations reduce overreliance only on difficult tasks. Cost-benefit framework.     |
| **Human Factor in XAI** (Nicolson et al.)                        | npj Digital Medicine 2025 | XAI impact varies by clinician. Some performed worse with explanations.               |
| **Counterfactual Explanations Reduce Overreliance** (Lee & Chew) | CSCW 2023                 | 21% reduction in overreliance vs salient feature explanations.                        |
| **ConfiDx** (Zhou et al.)                                        | npj Digital Medicine 2025 | Uncertainty recognition AUC 0.80-0.90 vs 0.45-0.65 for commercial systems.            |
| **Clinical AI Must Convey Uncertainty** (Banerji et al.)         | Nature Medicine 2023      | Conformal prediction for personalized uncertainty estimates.                          |
| **Cite-While-You-Generate** (Yan et al.)                         | arXiv 2026                | Attention-based citation at generation time. Outperforms embedding-based attribution. |
| **WHO LMM Guidance**                                             | WHO, Jan 2024             | 6 principles: autonomy, transparency, accountability, inclusiveness, responsiveness.  |
| **FUTURE-AI Consensus**                                          | BMJ 2025                  | 117 experts, 50 countries. Roadmap for trustworthy clinical AI.                       |

**Key insight**: Explanations are not uniformly helpful. Multiple papers show they can increase overreliance. Clinicians prefer exemplar-based and natural language rationales over technical methods (LIME/SHAP). Our linked evidence approach aligns with the citation-as-explanation paradigm.

---

## Updated Takeaways (All 8 Parts)

1. **At 200K tokens, hallucination is unavoidable** — no model below 10% fabrication (172B token study)
2. **RAG matches full-context for clinical tasks** at far lower cost (Myers et al., 2025)
3. **Prompt caching saves 90%** on repeated reference text (Anthropic cache_control)
4. **Fine-tuned Llama-3-70B outperforms BiomedBERT** by 7% on unseen clinical NER (JAMIA 2026)
5. **LLM-as-Judge achieves ICC 0.818** with human clinical evaluators (npj Digital Medicine 2025)
6. **No open ASAM decision logic** exists — our project fills a genuine gap
7. **No TJC compliance standards** encoded as computable knowledge — also novel
8. **Explanations can backfire** — increase overreliance in some contexts (CSCW 2023, npj Digital Medicine 2025)
9. **Citation-grounded generation** is the most promising path for trustworthy clinical AI (MEGA-RAG: 40% hallucination reduction)
10. **Query concatenation = 17x cost reduction** for clinical LLM workloads (Mount Sinai, npj Digital Medicine 2024)
11. **Negation errors are 30% of clinical hallucinations** — the #1 clinical failure mode
12. **Verification loops cost 28.9x naively** but can be optimized with selective execution (Sherlock, 2025)
