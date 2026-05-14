# QA-Checking LLM-Generated Content: Comprehensive Research

> Deep research on reducing hallucination rates, needle-in-haystack mitigation, multi-agent QA architectures, grounding techniques, and evaluation frameworks. Compiled May 2026.

---

## Table of Contents

1. [The Core Problem](#1-the-core-problem)
2. [Hallucination Detection Methods](#2-hallucination-detection-methods)
3. [Needle-in-Haystack: Why LLMs Lose Information](#3-needle-in-haystack-why-llms-lose-information)
4. [Chunking & Retrieval Strategies](#4-chunking--retrieval-strategies)
5. [Grounding & Citation Techniques](#5-grounding--citation-techniques)
6. [Multi-Agent QA Architectures](#6-multi-agent-qa-architectures)
7. [Evaluation Frameworks & Benchmarks](#7-evaluation-frameworks--benchmarks)
8. [Production Monitoring](#8-production-monitoring)
9. [Practical Architecture for Clinical Document QA](#9-practical-architecture-for-clinical-document-qa)
10. [Tool & Library Reference](#10-tool--library-reference)
11. [Sources](#11-sources)

---

## 1. The Core Problem

When you dump whole PDFs or clinical records into an LLM, three things go wrong:

1. **Positional attention decay** — LLMs exhibit a U-shaped attention curve. Content at the beginning and end gets ~72-75% accuracy; content in the middle drops to ~55% (Liu et al., TACL 2024). This is the "lost in the middle" phenomenon.

2. **Small needle blindness** — When the critical piece of information is short (a single sentence about spiritual orientation, a lab value, a medication change), it's disproportionately likely to be missed. A 2025 paper confirmed: smaller gold contexts = sharper performance drops across 7 SOTA models.

3. **Hallucination under pressure** — When the model can't find the answer in context, it fabricates one rather than admitting uncertainty. Even GPT-4 fails ~60% of basic factual questions (SimpleQA benchmark).

**The gap between advertised and effective context is massive.** NVIDIA's RULER benchmark found only ~50% of models claiming 32K+ context maintain performance at those lengths. On Sequential-NIAH (extracting multiple facts), even the best model maxes out at 63.5% accuracy.

---

## 2. Hallucination Detection Methods

### 2.1 Factual Consistency Checking (Source-Grounded)

Decompose LLM output into atomic claims, verify each against source documents.

- **HalluGraph** (2025): Extracts knowledge graphs from context and response, measures Entity Grounding and Relation Preservation
- **Claim decomposition pipelines**: Break text → atomic claims → verify each via retrieval or entailment
- **Best for**: RAG systems, document summarization, clinical compliance auditing
- **Weakness**: Requires reference documents; computationally expensive; struggles with implicit/inferred information

### 2.2 Self-Consistency / Sampling

Generate multiple responses (temperature > 0), check agreement. Hallucinated content varies across samples; factual content stays consistent.

- **SelfCheckGPT** (Manakul et al., EMNLP 2023): The canonical method. 5 scoring variants (BERTScore, QA, n-gram, NLI, LLM prompting). Open-source on GitHub.
- **MetaQA** (2024-2025): Outperforms SelfCheckGPT by 0.15-0.37 F1 using meta-level QA
- **Best for**: Reference-free settings, black-box API models
- **Weakness**: 5-20x cost; can miss "consistent hallucinations" where the model confidently repeats the same wrong fact

### 2.3 Entailment-Based (NLI Models)

Classify whether source text entails, contradicts, or is neutral toward each generated claim.

- **Vectara HHEM 2.1-2.3**: DeBERTa-v3 based. Factual Consistency Score 0-1. Handles 4,096 tokens. Supports 8 languages. **58x faster than RAGAS with GPT-4.** Outperforms GPT-4 by 30%+ on RAGTruth tasks.
- **Best for**: High-throughput production scoring of document-grounded tasks
- **Weakness**: Struggles with negation, multi-hop reasoning, numerical claims

### 2.4 Confidence Calibration / Uncertainty Estimation

Use model internals (token probabilities, hidden states, entropy) to flag low-confidence regions.

- **Semantic Entropy** (Farquhar et al., Nature 2024): Landmark paper. Clusters sampled outputs by meaning, computes entropy over meaning clusters. Task-agnostic, no domain-specific training needed.
- **Semantic Entropy Probes (SEPs)**: Linear probes on hidden states that approximate semantic entropy from a single generation — reduces 5-10x overhead to "almost zero"
- **Kernel Language Entropy (KLE)** (NeurIPS 2024): Generalizes semantic entropy with positive semidefinite kernels
- **Best for**: Open-weight models with logit access; real-time per-token confidence flags
- **Weakness**: Requires model internals (not available via most APIs); high confidence ≠ correctness

### 2.5 Chain-of-Verification (CoVe)

Four-stage self-verification (Meta AI, ACL Findings 2024):

1. **Draft** → generate initial response
2. **Plan** → generate verification questions targeting factual claims
3. **Execute** → answer questions independently (without seeing original draft — prevents confirmation bias)
4. **Revise** → produce corrected response incorporating verification results

- **Best for**: Factual QA, list-based questions, longform generation
- **Weakness**: 3-4x cost; same model verifying itself can miss systematic errors

### 2.6 Reference-Free Detection

Detect hallucinations without ground truth.

- **LLM-as-a-Judge**: One LLM evaluates another's output. DeepEval, G-Eval implement this.
- **Internal activation analysis** (May 2025): Using activations of a smaller open-weight proxy model to detect hallucinations in larger models
- **Patronus Lynx** (8B/70B): Fine-tuned Llama-3 with CoT reasoning. **Outperforms GPT-4o on medical hallucination detection by 8.3%.** Deployable via Ollama.
- **Best for**: Open-ended generation where no reference exists; cheap first-pass filtering
- **Weakness**: Lower accuracy than source-grounded methods; LLM judges have their own biases

---

## 3. Needle-in-Haystack: Why LLMs Lose Information

### The U-Shaped Attention Curve

| Position                | Accuracy | Explanation                             |
| ----------------------- | -------- | --------------------------------------- |
| Beginning (tokens 1-1K) | ~75%     | Primacy bias — strong initial attention |
| Middle (tokens 5K-15K)  | ~55%     | Attention degradation zone              |
| End (last 1-2K tokens)  | ~72%     | Recency bias — elevated final attention |

**Root causes:**

- **RoPE (Rotary Position Embedding)** introduces decay that de-emphasizes middle content
- **Causal attention masks** create position-specific hidden states contributing to bias
- **Training data distribution** — important information tends to appear at document boundaries

### The "Context Rot" Effect (Chroma, 2025)

Tested 18 models including Claude Opus 4, GPT-4.1, Gemini 2.5 Pro. Key findings:

- Performance degrades **non-linearly** with context length
- The 10,000th token is not processed as reliably as the 100th
- What matters is **how information is presented**, not just its presence

### Posterior Salience Attenuation (PSA)

The salience of gold-label information gradually degrades as overall context length grows, **independent of position**. Even if you put the needle at the start, adding more haystack after it degrades retrieval.

### Mitigation Strategies (API Users — No Model Access Required)

1. **Reorder documents** — most relevant at start and end, least relevant in middle. Haystack's `LostInTheMiddleRanker` automates this.
2. **Reduce context aggressively** — fewer, more relevant chunks beats more context
3. **Explicit instructions** — "pay special attention to ALL sections; every section is equally important"
4. **Multi-pass processing** — break into focused passes over subsets
5. **Structured extraction prompts** — ask for specific fields, not open-ended analysis
6. **Prompt compression** — 50-70% token reduction while maintaining accuracy; 21.4% accuracy improvement by eliminating the middle zone

---

## 4. Chunking & Retrieval Strategies

### Chunking Methods (Ranked by Sophistication)

| Strategy               | How It Works                                                 | Best For                  | Trade-off                      |
| ---------------------- | ------------------------------------------------------------ | ------------------------- | ------------------------------ |
| **Fixed-size**         | Uniform token/char lengths (e.g., 512 tokens)                | Homogeneous content       | Breaks semantic boundaries     |
| **Overlapping**        | Sliding window with 10-20% overlap                           | Preserving edge context   | 1.1-1.2x storage               |
| **Context-aware**      | Split on paragraph/section/header boundaries                 | Structured documents      | Requires format-specific logic |
| **Semantic**           | Group sentences by embedding similarity; detect topic shifts | Multi-topic documents     | Compute-intensive              |
| **Hierarchical**       | Parent chunks (broad) → child chunks (specific)              | Nested document structure | Complex retrieval logic        |
| **Adaptive/ML-driven** | Model determines optimal boundaries per document             | Clinical records          | Most compute-intensive         |

**Clinical study result**: Adaptive chunking aligned to logical topic boundaries achieved **87% accuracy vs. 13% for fixed-size** in clinical decision support (Nov 2025).

**Recommendation for clinical records**: Context-aware or semantic chunking that respects section boundaries (Assessment, History, Plan), with 10-15% overlap.

### RAG Best Practices for Clinical QA

1. **Hybrid retrieval**: BM25 (exact terms — drug names, lab values, standard IDs) + dense embeddings (semantic meaning) + cross-encoder reranking → P@5 of 0.68+
2. **Two-stage retrieval**: Broad recall (top 20-50) → reranking (top 3-5)
3. **Self-reflective RAG**: (1) Generate with citations → (2) List uncited claims → (3) Refine using only cited passages. Achieves 5.8% hallucination rate.
4. **Iterative RAG (i-MedRAG)**: LLM iteratively asks follow-up queries based on previous retrieval results — addresses cases where single retrieval misses context

### Map-Reduce for Multi-Document Analysis

**Map**: Process each clinical note independently (extract ASAM dimensions, identify TJC elements)
**Reduce**: Synthesize into unified assessment

This naturally avoids the "lost in the middle" problem and produces auditable intermediate results. Each note's extraction can be inspected independently.

**LLMxMapReduce** (ACL 2025): Adds structured information protocol, in-context confidence calibration, and entropy-driven collapse between map and reduce.

---

## 5. Grounding & Citation Techniques

### 5.1 Citation-Based Generation

- **Google AGREE** (NAACL 2024): Fine-tunes LLMs to self-ground with inline citations. NLI model evaluates support. Iterative refinement retrieves more when claims lack support. **30%+ improvement in citation recall/precision** over post-hoc citing.
- **Post-hoc citation** (generate first, attach citations after) consistently underperforms inline citation.

### 5.2 Extractive + Abstractive Hybrid (Two-Stage Pipeline)

The most practical production pattern:

1. **Extract**: Retrieve relevant passages via embedding search + BM25
2. **Generate**: Pass only extracted passages to LLM with instructions to synthesize exclusively from them

This constrains the LLM's "knowledge horizon" to provided extracts.

### 5.3 Structured Output with Evidence Fields

Force JSON schemas where every claim requires evidence:

```json
{
  "finding": "string — the claim or assessment",
  "evidence": ["1-5 verbatim quotes from source documents"],
  "confidence": "high | medium | low",
  "source_section": "which document section the evidence comes from"
}
```

Requiring a verbatim quote makes hallucination structurally harder — the model must produce text that actually appears in the source.

### 5.4 Deterministic Quoting (Healthcare-Specific)

The most novel technique found. The LLM selects a reference ID, but the actual quoted text is retrieved **deterministically from a database lookup — never passed through the LLM**.

**Results**: Zero hallucinations in quoted sections, surrounding text hallucination dropped from 12% to 2%, quote relevance at 92%.

### 5.5 Prompt Engineering for Faithfulness (Ranked by Effectiveness)

1. **Explicit constraints**: "Answer ONLY using information from the provided documents"
2. **Citation-forcing**: "For every claim, cite the specific passage using [Doc X, Section Y]"
3. **Chain-of-thought with grounding**: List relevant quotes first → reason over only those → produce answer
4. **Structured reference tagging**: Wrap source chunks in `<quote><title>REF_001</title>...</quote>` tags
5. **Negative instructions**: "Do not use training data. Do not speculate beyond what is stated."
6. **Self-verification**: After generating, review and flag unsupported statements

Combining citation requirements + structured output constraints yields the strongest prompt-only results.

### 5.6 Fine-Tuning for Faithfulness

- **Factuality-aware DPO (FLAME)**: SFT on more-factual data + DPO preferring non-hallucinated outputs. Over 50% reduction in factual errors on LLaMA-2 7B.
- **NAACL 2025**: Synthetic hard-to-hallucinate examples + preference optimization → **90-96% hallucination reduction** without quality degradation.
- DPO is preferred over full RLHF for faithfulness (simpler, comparable results).

---

## 6. Multi-Agent QA Architectures

### 6.1 Generator-Verifier (Maker-Checker)

One agent produces, a separate agent reviews against source material.

- **SEC filing study**: Reflexive self-correcting loop achieved **0.943 F1 with Claude 3.5 Sonnet** at 2.3x cost
- **CRITIC**: Requires tool-interactive validation (code interpreters, search, document lookup) — critic can't just reason, must ground critique in evidence
- **Key insight**: Use a different model or temperature for verifier than generator to reduce confirmation bias

### 6.2 Debate-Based Verification

Multiple LLM instances argue about correctness and converge on truth (Du et al., ICML 2024).

- Even 3 agents debating for 2 rounds shows significant improvement
- **DebateCV** (2025): First debate-driven claim verification — corrects misinterpretation, overlooked evidence, overreliance on speculation
- **Tool-MAD** (2025): Combines debate with tool use for evidence retrieval during debate
- **Caveat**: A 2025 paper ("Can LLM Agents Really Debate?") found debate doesn't always improve outcomes — can degrade when agents are too deferential

### 6.3 Specialized Checker Agents (Spawn in Parallel)

Decompose verification into specialized roles:

| Agent                    | Responsibility                                          |
| ------------------------ | ------------------------------------------------------- |
| **Citation Grounding**   | Verify every quoted passage exists verbatim in source   |
| **Completeness Checker** | Verify all required elements were addressed             |
| **Consistency Checker**  | Validate that ratings logically support recommendations |
| **Standards Fidelity**   | Cross-check findings against official standard text     |

**MAJ-Eval** (medical domain): Multiple evaluator personas debate and cross-verify clinical responses.
**AgentsCourt** (legal): Adversarial prosecutor/defense/judge structure.
**MARCH** (2025): Decomposes into atomic propositions, formulates verifiable Q&A pairs, agents verify solely on retrieved evidence.

### 6.4 Ensemble / Voting Approaches

- **ReConcile** (ACL 2024): Round-table conference with confidence-weighted voting. Multiple rounds where agents see each other's answers. Surpassed baselines by up to **11.4%** and outperformed GPT-4 on three benchmarks.
- **Cross-model ensembles**: 5 diverse models typically yields 10-30% accuracy improvement
- **Cost tip**: Run fast single check first; escalate to multi-agent only when uncertainty is flagged

### 6.5 Frameworks for Multi-Agent Verification

| Framework             | Best For                      | Key Feature                                                               |
| --------------------- | ----------------------------- | ------------------------------------------------------------------------- |
| **LangGraph**         | Production compliance systems | Graph-based orchestration, audit trails, checkpoints, typed state         |
| **CrewAI**            | Rapid prototyping             | Role-based DSL, lowest learning curve (20 lines)                          |
| **OpenAI Agents SDK** | Guardrails                    | Built-in input/output validation running in parallel with agent execution |
| **AutoGen**           | Legacy (maintenance mode)     | Being merged into Microsoft Semantic Kernel                               |

LangGraph is the clear leader for production healthcare/compliance systems — supports guard nodes, approval steps, and typed state updates at graph positions.

---

## 7. Evaluation Frameworks & Benchmarks

### Hallucination Benchmarks

| Benchmark            | Scale                            | Key Finding                                       | Status                                  |
| -------------------- | -------------------------------- | ------------------------------------------------- | --------------------------------------- |
| **TruthfulQA**       | 817 questions, 38 domains        | Measures factuality, not hallucination per se     | **Saturated** — data contamination      |
| **FActScore**        | Atomic fact decomposition        | ChatGPT: only 58% on biographies                  | Gold standard for long-form             |
| **SimpleQA**         | Short fact-seeking questions     | GPT-4 fails ~60% of basic questions               | Active                                  |
| **HalluLens** (2025) | 3 tasks, dynamic generation      | GPT-4o: 52.59% on PreciseWikiQA                   | Prevents data leakage                   |
| **MedHallu** (2025)  | 10K medical QA pairs             | Best models: F1 as low as **0.625** on hard cases | Largest medical hallucination benchmark |
| **Med-HALT**         | Multinational medical exams      | Reasoning + memory-based tests                    | QA format only                          |
| **HELM / MedHELM**   | 7 metrics, 35 medical benchmarks | 10-25% accuracy gaps from hallucinations          | Holistic evaluation                     |

### Automated Evaluation

| Metric/Tool            | Type                      | Speed                     | Strength                                |
| ---------------------- | ------------------------- | ------------------------- | --------------------------------------- |
| **RAGAS Faithfulness** | LLM-as-judge, claim-level | Moderate                  | 95% agreement with humans; best for RAG |
| **HHEM (Vectara)**     | Neural classifier         | **58x faster than RAGAS** | High-throughput production              |
| **FActScore**          | Atomic fact verification  | Slow                      | Most granular                           |
| **G-Eval**             | LLM + CoT evaluation      | Moderate                  | 0.514 Spearman correlation with humans  |
| **DeepEval**           | LLM-as-judge, 50+ metrics | Varies                    | pytest-native CI/CD integration         |

**Critical insight**: Most metrics are **uni-dimensional** with low inter-metric correlation (2025 "Mirage of Hallucination Detection" paper). Use **ensembles of metrics**, not a single one.

### LLM-as-Judge Best Practices

1. Use **binary evaluations** (faithful/hallucinated) — more reliable than 1-100 scales
2. **Low temperature** (0.0-0.1) for deterministic evaluation
3. **Ask for reasoning before judgment** (CoT improves quality)
4. **Majority voting** across multiple evaluations to reduce variance
5. **Validate against human annotations** on a calibration set first

### LLM-as-Judge Known Biases

- **Position bias**: Favors responses based on presentation order
- **Verbosity bias**: Prefers longer outputs regardless of quality
- **Self-preference**: Models prefer their own family's outputs
- **Domain gaps**: Agreement drops to 64-68% on expert tasks (vs. 72-75% inter-expert)

---

## 8. Production Monitoring

### Four-Layer Architecture

```
┌─────────────────────────────────────────┐
│  Layer 1: Pre-Production Evaluation     │
│  Benchmarks, regression suites, evals   │
├─────────────────────────────────────────┤
│  Layer 2: Real-Time Detection           │
│  LLM-as-judge, HHEM scoring, semantic   │
│  similarity against source              │
├─────────────────────────────────────────┤
│  Layer 3: Observability & Alerting      │
│  Threshold alerts, anomaly detection,   │
│  distributed tracing                    │
├─────────────────────────────────────────┤
│  Layer 4: Continuous Feedback Loop      │
│  User feedback, human review queues,    │
│  dataset curation → re-evaluation       │
└─────────────────────────────────────────┘
```

### Key Monitoring Metrics

- **Faithfulness score**: Output adherence to retrieved context
- **Groundedness score**: Every claim traceable to a source
- **Answer relevance**: Alignment with user intent
- **Refusal rate**: Too high = overcautious; too low = reckless

### Emerging Tech

- **HaluGate** (vLLM, 2025): Token-level hallucination detection that catches unsupported claims **before they reach users** in the generation stream
- **Semantic Entropy Probes**: Near-zero overhead uncertainty estimation from single generation

### Platforms

| Platform          | Type                       | Key Feature                                  |
| ----------------- | -------------------------- | -------------------------------------------- |
| **Langfuse**      | Open-source, self-hostable | Multi-level tracing, human annotation queues |
| **Arize Phoenix** | Open-source                | Embedding drift, RAG hallucination detection |
| **DeepEval**      | Open-source                | pytest-native, CI/CD, 50+ metrics            |
| **Braintrust**    | Commercial                 | Quality gates, 9+ framework integrations     |
| **Datadog LLM**   | Enterprise                 | Hallucination detection via LLM-as-judge     |

---

## 9. Practical Architecture for Clinical Document QA

Based on all research, here's the recommended architecture for QA-checking ASAM assessments and TJC compliance audits:

### Layer 1: Smart Document Processing

```
Clinical Records (BPS + Progress Notes)
         │
         ▼
┌─────────────────────────┐
│  Section-Aware Chunking  │  Respect SOAP/DAP/DSAP structure
│  + 10-15% Overlap        │  Semantic boundaries at section level
└────────────┬────────────┘
         │
         ▼
┌─────────────────────────┐
│  Hybrid Retrieval Index  │  BM25 (exact terms) + Dense embeddings
│  (per-patient store)     │  Cross-encoder reranking
└────────────┬────────────┘
```

### Layer 2: Multi-Pass Extraction (Map Phase)

```
For each clinical note independently:
  Pass 1: Extract structured data (demographics, substances, diagnoses, meds)
  Pass 2: For each ASAM dimension, find supporting evidence
  Pass 3: For each TJC standard, find compliance evidence
  Pass 4: Hunt specifically for gaps (spiritual, cultural, discharge planning)
```

### Layer 3: Parallel Verification Agents

```
Primary Analysis Output
         │
         ├──→ [Citation Grounding Agent]     Verify quotes exist in source
         ├──→ [Completeness Agent]           All ASAM dims / TJC standards covered?
         ├──→ [Consistency Agent]            Do ratings support the LOC recommendation?
         └──→ [Standards Fidelity Agent]     Findings match official standard text?
                    │
                    ▼
         Confidence-Weighted Aggregation (ReConcile pattern)
                    │
              ┌─────┴─────┐
              │ Agreement  │ Disagreement → Debate round → Human review if unresolved
              └─────┬─────┘
                    │
                    ▼
              Final QA'd Output with per-claim confidence scores
```

### Layer 4: Structural Guardrails

- **Structured JSON output** with mandatory evidence fields for every finding
- **Deterministic quoting** where possible — LLM selects reference ID, actual quote pulled from database
- **Constitutional principles check**: "All risk ratings must cite direct quotes", "ASAM level = minimum level indicated by highest-severity dimension"

### Cost-Performance Trade-offs

| Approach                          | Cost Multiplier | Hallucination Reduction | Latency         |
| --------------------------------- | --------------- | ----------------------- | --------------- |
| Prompt engineering alone          | 1x              | ~35%                    | Baseline        |
| + Structured output with evidence | 1x              | ~50%                    | Baseline        |
| + RAG instead of full-context     | 1x              | ~60%                    | +retrieval time |
| + Multi-pass extraction           | 3-4x            | ~70%                    | 3-4x            |
| + Single verifier agent           | 2x              | ~80%                    | 2x              |
| + Parallel specialized checkers   | 5-6x            | ~90%                    | 2x (parallel)   |
| + Cross-model ensemble            | 10x+            | ~95%                    | 2-3x            |

_Estimates based on research findings; exact numbers are task-dependent._

---

## 10. Tool & Library Reference

### Detection & Scoring

| Tool                       | Type                    | Access              | Speed               | Languages   |
| -------------------------- | ----------------------- | ------------------- | ------------------- | ----------- |
| **Patronus Lynx** (8B/70B) | Fine-tuned Llama-3      | HuggingFace, Ollama | Fast                | English     |
| **Vectara HHEM 2.1**       | DeBERTa-v3 classifier   | HuggingFace, API    | Very fast           | 8 languages |
| **SelfCheckGPT**           | Sampling-based          | GitHub, PyPI        | Slow (multi-sample) | Any         |
| **UQLM** (CVS Health)      | Black/white-box scorers | GitHub              | Varies              | Any         |

### Evaluation Frameworks

| Tool          | Focus                    | Integration           |
| ------------- | ------------------------ | --------------------- |
| **RAGAS**     | RAG pipeline evaluation  | LangChain, LlamaIndex |
| **DeepEval**  | General LLM testing      | pytest, CI/CD         |
| **FActScore** | Atomic fact verification | Standalone            |

### Observability

| Platform          | Self-Hostable | Human Review |
| ----------------- | ------------- | ------------ |
| **Langfuse**      | Yes           | Yes          |
| **Arize Phoenix** | Yes           | Limited      |
| **Braintrust**    | No            | Yes          |

### Multi-Agent Orchestration

| Framework             | Production-Ready | Best For                     |
| --------------------- | ---------------- | ---------------------------- |
| **LangGraph**         | Yes              | Compliance-sensitive systems |
| **CrewAI**            | Yes              | Rapid prototyping            |
| **OpenAI Agents SDK** | Yes              | Guardrails                   |

### Grounding

| Tool                      | What It Does                                             |
| ------------------------- | -------------------------------------------------------- |
| **Google LangExtract**    | Source-grounded extraction with character-offset mapping |
| **Vectara Open-RAG-Eval** | Groundedness + citation scoring without golden answers   |

---

## 11. Sources

### Foundational Papers

- [Lost in the Middle: How Language Models Use Long Contexts (TACL 2024)](https://aclanthology.org/2024.tacl-1.9/)
- [Detecting Hallucinations Using Semantic Entropy (Nature 2024)](https://www.nature.com/articles/s41586-024-07421-0)
- [Chain-of-Verification Reduces Hallucination (ACL Findings 2024)](https://aclanthology.org/2024.findings-acl.212/)
- [Improving Factuality through Multiagent Debate (ICML 2024)](https://arxiv.org/abs/2305.14325)
- [SelfCheckGPT (EMNLP 2023)](https://arxiv.org/abs/2303.08896)
- [FActScore (EMNLP 2023)](https://aclanthology.org/2023.emnlp-main.741/)
- [Google AGREE Framework (NAACL 2024)](https://aclanthology.org/2024.naacl-long.346/)
- [ReConcile: Round-Table Conference (ACL 2024)](https://arxiv.org/abs/2309.13007)

### Surveys

- [Comprehensive Survey of Hallucination in LLMs (arXiv, Oct 2025)](https://arxiv.org/abs/2510.06265)
- [Survey on Hallucination: Principles, Taxonomy (ACM TOIS)](https://dl.acm.org/doi/10.1145/3703155)
- [Agent-as-a-Judge Survey (arXiv 2601.05111)](https://arxiv.org/html/2601.05111v1)
- [Survey on LLM-as-a-Judge (Zheng et al.)](https://arxiv.org/abs/2411.15594)
- [The Mirage of Hallucination Detection (2025)](https://arxiv.org/html/2504.18114v2)

### Needle-in-Haystack & Context

- [Context Rot (Chroma, 2025)](https://www.trychroma.com/research/context-rot)
- [Lost in the Haystack: Smaller Needles (2025)](https://arxiv.org/abs/2505.18148v1)
- [Found in the Middle: Calibrating Positional Bias (2024)](https://arxiv.org/abs/2406.16008)
- [Sequential-NIAH Benchmark (2025)](https://arxiv.org/abs/2504.04713)
- [Semantic Entropy Probes (2024)](https://arxiv.org/abs/2406.15927)

### Clinical/Medical Specific

- [MedHallu Benchmark (2025)](https://arxiv.org/html/2502.14302v1)
- [MedHELM (2025)](https://arxiv.org/html/2505.23802v2)
- [Clinical Safety Framework (npj Digital Medicine)](https://www.nature.com/articles/s41746-025-01670-7)
- [RAG in Healthcare Review (MDPI 2025)](https://www.mdpi.com/2673-2688/6/9/226)
- [i-MedRAG: Iterative Medical RAG (PMC 2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11997844/)
- [Verifying Facts in Patient Care Documents (NEJM AI)](https://ai.nejm.org/doi/full/10.1056/AIdbp2500418)

### Tools & Techniques

- [Patronus Lynx](https://www.patronus.ai/blog/lynx-state-of-the-art-open-source-hallucination-detection-model)
- [Vectara HHEM 2.1](https://www.vectara.com/blog/hhem-2-1-a-better-hallucination-detection-model)
- [Deterministic Quoting for Healthcare](https://mattyyeung.github.io/deterministic-quoting)
- [MARCH: Multi-Agent Reinforced Self-Check (2025)](https://arxiv.org/html/2603.24579)
- [LLMxMapReduce (ACL 2025)](https://aclanthology.org/2025.acl-long.1341.pdf)
- [Google LangExtract](https://github.com/google/langextract)
- [HaluGate (vLLM, 2025)](https://blog.vllm.ai/2025/12/14/halugate.html)
- [UQLM (CVS Health)](https://github.com/cvs-health/uqlm)
- [DeepEval Docs](https://deepeval.com/docs/metrics-hallucination)
- [Langfuse Docs](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge)
- [RAGAS Docs](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)

### Frameworks

- [LangGraph](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [Awesome Hallucination Detection (Edinburgh NLP)](https://github.com/EdinburghNLP/awesome-hallucination-detection)
- [Vectara Hallucination Leaderboard](https://huggingface.co/spaces/vectara/leaderboard)

---

# Part 2: Deep Dive Research

---

## 12. Real-World Clinical AI Hallucination Incidents

### Documented Failures

**Google Med-Gemini (2024)**: Referenced a nonexistent brain structure called the "basilar ganglia" in its own showcase paper. Conflated basal ganglia and basilar artery. Google quietly edited their blog post but never corrected the research paper.

**Ambient Clinical Documentation (2025)**: Study of ambient digital scribe platforms found **26.3% error rate** in clinical notes, with **3.0 errors per case having potential for moderate-to-severe harm**. Systems hallucinated details and "invented things no one ever said."

**AI Medical Summaries (2024)**: GPT-4o produced 21 summaries with incorrect information and 50 with overly generalized information. In an ED context, **42% of GPT-4 summaries exhibited hallucinations** and **47% omitted clinically relevant information**.

**FDA's Own AI Tool**: The FDA's internal Elsa AI tool experienced hallucinations by "citing studies that don't exist" when generating meeting summaries.

**Adversarial Study (2025, Communications Medicine)**: 300 physician-validated cases with embedded fabrications (fictitious lab tests, invented signs, made-up syndromes). **Hallucination rates: 50-82.7%** across six LLMs under default settings. Prompt engineering reduced but did not eliminate errors (66% → 44%).

### The 1.47% vs 44% Paradox

The npj Digital Medicine framework study (12,999 clinician-annotated sentences) found:

- Overall hallucination rate: only **1.47%** of sentences
- But **44% of those hallucinations were clinically major** (potentially life-threatening)
- Omission rate (**3.45%**) exceeded hallucination rate by 2.3x

Low aggregate rates mask concentrated, high-severity risks. A system that's "98.5% accurate" can still kill patients.

### Clinical Hallucination Taxonomy

| Type            | Frequency | Clinical Risk                                |
| --------------- | --------- | -------------------------------------------- |
| **Fabrication** | 43%       | Inventing information absent from source     |
| **Negation**    | 30%       | Flipping "no history of X" to "history of X" |
| **Contextual**  | 17%       | Mixing unrelated clinical topics             |
| **Causality**   | 10%       | Speculating on causes without evidence       |

**Major hallucinations by section**: Plan (21%), Assessment (10.5%), Symptoms (5.2%). Plan errors are most dangerous — they directly affect treatment decisions.

### Production Systems That Work

**Hippocratic AI — Constellation Architecture** (U.S. Patent 12,142,371):

- **16+ specialized models** cross-check a primary conversational model
- Dedicated engines: Overdose Engine, Condition-Specific OTC Engine, Medication Reconciliation Engine
- Single-LLM prototype: 80% accuracy → Constellation: **99.02%**
- 150M+ clinical interactions across 50+ health systems, claims "no safety issues"
- **This is the strongest production evidence that multi-agent verification works**

**Nuance DAX Copilot (Microsoft)**:

- Clinical Safeguards API (private preview) double-checks AI outputs
- Checks for: fabricated vs source-supported content, medical context awareness, source provenance, clinical code validation

**Epic Systems**:

- GPT-4 integration via Azure OpenAI
- ~2/3 of Epic providers have used generative AI features
- Mount Sinai integrated OpenEvidence AI for "strictly sourced, cited, and grounded" answers

---

## 13. Clinical Faithfulness: Format-Specific Findings

### SOAP Note Processing Accuracy

The most comprehensive study (Tariq et al., npj Digital Medicine, 450 notes, 12,999 annotated sentences):

- **SOAP templating reduced major hallucinations by 75%** and major omissions by 58% vs unstructured generation
- Most effective mitigation: structured prompting + explicit "output unknown for absent information" instructions
- **No research exists comparing DAP vs DSAP formats** — SOAP dominates the literature

### Negation: The #1 Clinical Killer

- **30% of all clinical hallucinations** involve negation errors
- Fine-tuned LLaMA 3.1-8B: **0.975 accuracy** on negated assertions vs GPT-4o at **0.891**
- Larger models handle negation better (~2.5% degradation at 70B vs much larger drops at 3B)
- **BioBERT achieves 0.957** at 100x lower compute cost — fine-tuned small models beat general LLMs here

**Mitigation**: Use structured assertion labels in extraction schemas, not free-text reasoning. Implement post-processing validation rules for negation patterns.

### Temporal Reasoning Failures

- **Performance degrades after Day 3** of patient history — additional context introduces noise
- LLMs **fail to discard outdated/disproven diagnoses** when synthesizing longitudinal records
- RAG produces fewer hallucinations but **disrupts temporal dependencies** by fragmenting timelines

**Mitigation**: Pre-sort notes chronologically. Provide explicit date markers. Don't rely on LLM to infer temporal ordering.

### ASAM Criteria: No Published Research Exists

**Zero published studies** on LLMs performing ASAM Level of Care determinations. Likely failure modes:

- Dimensional conflation (blending ratings across the 6 dimensions)
- Severity calibration (distinguishing 2.1 from 2.5 requires precise threshold reasoning)
- Withdrawal timeline assessment (Dimension 1 requires temporal reasoning — a documented LLM weakness)
- Recovery environment nuance (Dimension 6 — LLMs underweight social context vs biomedical findings)

### TJC Compliance Auditing: Also Uncharted Territory

**No published academic research** on AI/LLMs for Joint Commission or CARF compliance gap detection. This means:

- No established ground truth to validate against
- Must be validated by clinical compliance experts
- Significant first-mover opportunity but also significant undetected error risk

### Substance Use Disorder Documentation Challenges

- **18.4% of SUD clinical notes** contain stigmatizing language (546K notes studied)
- Fine-tuned Llama-3 8B: **97.2% accuracy** identifying stigmatizing terms
- Severity terminology differs between ICD-10, DSM-5, and clinical vernacular
- Coded/euphemistic language varies across providers ("using," "clean," "dirty")
- Harm reduction terminology is rapidly evolving

---

## 14. Adversarial Testing & Red-Teaming

### The Benchmarking Gap

**DAS Framework finding**: Despite median MedQA accuracy exceeding 80%, **94% of previously correct answers failed under dynamic adversarial perturbations**. Static benchmarks massively overstate real-world reliability.

### What Triggers Clinical Hallucination

| Trigger                         | Mechanism                                                                |
| ------------------------------- | ------------------------------------------------------------------------ |
| **Ambiguous clinical language** | Terms with multiple meanings                                             |
| **Contradictory notes**         | Conflicting medication lists across encounters                           |
| **Missing data**                | Model "fills in gaps" with plausible fabrications                        |
| **Short vignettes**             | Less context = higher hallucination rates                                |
| **Copy-forward artifacts**      | Outdated EHR data treated as current                                     |
| **Authority impersonation**     | "Educational authority" framing: **83.3% success rate** bypassing safety |

### Can Verification Systems Be Fooled?

**Yes.** Key vulnerabilities:

- RAG retrieval can fail to surface the correct passage
- LLM-as-judge fails on domain-specific correctness (64-68% agreement vs 72-75% human inter-expert)
- Self-consistency can't detect systematic errors where the model consistently hallucinates the same thing
- Intrinsic pattern-based detectors lack proper calibration for high-certainty hallucinations

**Most robust approach**: Deterministic fact-checking via atomic proposition decomposition into structured tuples `(entity, attribute, value, temporal_marker)` + six rule-based logical consistency checks. Achieved **79.13% accuracy on MIMIC-III** (outperforming Claude-2 + DOSSIER at 78.62%) with **0.89 precision and 0.82 recall** — and no LLM required.

### Failure Mode Taxonomy

**20 failure modes across 7 categories:**

| Category             | Examples                                                          |
| -------------------- | ----------------------------------------------------------------- |
| **Factual Errors**   | Fabrication, factual hallucination, input-conflicting claims      |
| **Omission Errors**  | Critical omission (3.45% rate), partial extraction                |
| **Misattribution**   | Wrong note/provider/date, temporal scrambling, patient confusion  |
| **Reasoning Errors** | Severity misestimation, diagnostic hallucination, unsound logic   |
| **Reference Errors** | Fabricated citations, outdated guidelines, nonexistent procedures |
| **Bias Errors**      | Demographic stereotypes, amalgamated conditions                   |
| **Format Errors**    | Schema violations, numerical/unit mismatches                      |

### Abstention: Models Almost Never Refuse When They Should

LLMs achieved only **71.43% precision and 13.16% recall** on clinically appropriate abstention decisions. They almost never say "I don't know" when they should.

### Building Evaluation Datasets

- **80-560 annotated samples** needed for stable metrics (task-dependent)
- Start with **100 golden cases**, scored 3 times each (take median) — reduces false-positive regressions by ~60%
- Double-annotate everything; resolve disagreements in consensus sessions
- **Cohen's Kappa > 0.80** required for clinical applications
- Include both positive cases and negative cases (information genuinely absent)
- Version-control annotations alongside code

### Regression Testing for LLM Outputs

| Test Type               | Purpose                                      | Threshold    |
| ----------------------- | -------------------------------------------- | ------------ |
| Semantic similarity     | Preserve clinical meaning after model update | >= 0.9       |
| Schema validation       | Required JSON fields present                 | 100%         |
| Classification accuracy | Compliance statuses correct                  | >= 90%       |
| Pattern matching        | No fabricated citations                      | 0 violations |
| Factual consistency     | Extracted facts match source                 | >= 95%       |
| Completeness            | All dimensions/standards addressed           | 100%         |

Score each golden case **3 times, take the median**. Use K-S tests to detect systematic shifts vs isolated noise.

---

## 15. Context Engineering

### Core Principles (Anthropic, September 2025)

Context engineering is "the art of providing all the context for the task to be plausibly solvable by the LLM." It's broader than prompt engineering — encompasses everything entering the context window.

1. **Finite attention budget** — n² pairwise token relationships; adding tokens has non-linear cost
2. **High-signal minimalism** — smallest possible set of tokens that maximize desired outcome
3. **Progressive disclosure** — maintain lightweight references, load full content on demand
4. **Right-altitude calibration** — between overly brittle hardcoded logic and excessively vague guidance

### Effective Context Capacity

| Advertised  | Effective | Rule of Thumb                    |
| ----------- | --------- | -------------------------------- |
| 200K tokens | ~120-130K | **Stay under 65% of advertised** |
| 128K tokens | ~80-85K   | Same ratio applies               |

**65% of enterprise AI failures in 2025** were attributed to context drift or memory loss. At 95% per-step reliability over 20 steps, combined success drops to **36%**.

### Optimal Structure for Clinical Document Processing

```
[Cached] System prompt + TJC/ASAM standards (cache_control breakpoints)
[Beginning] Instructions — exploits primacy bias
[Middle] Clinical documents — lower-priority supporting material here
[End] Query restated — exploits recency bias
```

**Prompt caching impact**: A 30K-token standards reference costs $0.09/request on Sonnet. With cache hit: **$0.009** (90% savings). Cache reads cost 10% of base input.

### XML Tagging (Claude Is Trained On This)

```xml
<standards>
  <standard id="CTS.02.02.01">
    <elements_of_performance>
      <ep number="1">...</ep>
      <ep number="2">...</ep>
    </elements_of_performance>
  </standard>
</standards>

<patient_documents>
  <document type="assessment" date="2024-01-15">
    <content>...</content>
  </document>
  <document type="progress_note" format="SOAP" date="2024-01-22">
    <content>...</content>
  </document>
</patient_documents>
```

XML creates unambiguous boundaries. Claude was specifically trained with XML tags — this is a genuine capability advantage.

### Context Compression Targets

| Content Type                | Compression Ratio |
| --------------------------- | ----------------- |
| Old conversation history    | 3:1 to 5:1        |
| Tool outputs/observations   | 10:1 to 20:1      |
| Recent messages (5-7 turns) | Never compress    |
| System prompt               | Never compress    |

**Trigger compression at 70% of available context budget.**

---

## 16. Implementation Patterns (Code-Level)

### Atomic Claim Decomposition

FActScore approach: sentence → atomic facts → verify each independently.

```
Input: "Patient reports daily alcohol use of 6-8 drinks for 3 years
        and denies any withdrawal symptoms."

Atomic facts:
- Patient reports daily alcohol use
- Alcohol consumption is 6-8 drinks per day
- Duration of use is 3 years
- Patient denies withdrawal symptoms
```

**Libraries**: FActScore (`pip install factscore`), Instructor (`pip install instructor`) for Pydantic-enforced decomposition with retries.

### Citation Verification: Three-Tier Pipeline

**Tier 1 — Exact lookup** (threshold >= 0.92): RapidFuzz string matching

```python
from rapidfuzz import fuzz
score = fuzz.partial_ratio(cited_text, source_text)
# >= 0.92: Valid    0.70-0.91: Partial    < 0.70: Hallucinated
```

**Tier 2 — Fuzzy retrieval** (threshold >= 0.70): BM25 + temporal proximity

**Tier 3 — Embedding similarity**: sentence-transformers, cosine >= 0.85

**"Assisted Fuzzy" approach** (TimeStampEval): RapidFuzz pre-filter → LLM verification on short snippets. **+50 accuracy points, half the latency, 96% cost reduction per correct result.**

### Structured Output with Evidence

```python
class Finding(BaseModel):
    element: str
    status: Literal["pass", "fail", "partial", "insufficient_evidence"]
    rationale: str
    citations: list[Citation]
    evidence_gap: Optional[str] = None
    confidence: float = Field(..., description="0.0-1.0")
```

**Critical limitation**: Claude's Citations API and Structured Outputs are **mutually exclusive** (400 error if both enabled). Workaround: use Citations API for generation, parse into Pydantic in application code.

### Deterministic Quoting

1. Chunk source documents, assign reference IDs
2. Present chunks to LLM with XML `<quote><title>REF_ID</title>` tags
3. LLM selects which reference to cite
4. Post-process: replace LLM's text with **original verbatim text from database**

**Result**: Zero hallucination in quoted sections. Surrounding text hallucination: 12% → 2%.

**Alternative**: Claude's built-in Citations API returns `cited_text` guaranteed verbatim from source with `start_char_index` and `end_char_index`.

### Cost Optimization: Task-to-Model Routing

| Task                | Model               | Rationale                     |
| ------------------- | ------------------- | ----------------------------- |
| Claim decomposition | **Haiku** ($1/$5)   | Mechanical task               |
| Citation matching   | **No LLM**          | RapidFuzz (free)              |
| Clinical analysis   | **Sonnet** ($3/$15) | Needs reasoning, not frontier |
| JSON formatting     | **Haiku** ($1/$5)   | Reformatting only             |
| QA verification     | **Sonnet** ($3/$15) | Independent judgment          |
| Edge case review    | **Opus** ($5/$25)   | Only for flagged cases        |

**Cache the standards text** (static across patients). Batch API gives 50% discount for async jobs. One developer: **$80/month → $24/month** (70% reduction) with Haiku routing + caching.

---

## 17. FDA & Regulatory Landscape

### Current Regulatory Posture

- **FDA Warning Letter (2026)**: Manufacturer penalized for failing to validate AI-generated documents. FDA made clear: **organizations remain fully responsible for AI outputs regardless of AI errors**.
- **Digital Health Advisory Committee (Nov 2024)**: Identified hallucination and sycophancy as novel risks. Recommended mandatory disclosure of hallucination rates via standardized model cards.
- **Draft Guidance (Jan 2025)**: "AI tools do not make regulatory decisions or replace human judgment."
- **Clinical validation gaps**: Of 950 FDA-authorized AI devices, 43% of recalls occurred within one year. 510(k) pathway doesn't require prospective human testing.

### HIPAA and Multi-Agent Verification

**Every LLM API provider processing PHI needs a signed BAA.** Both Anthropic and OpenAI offer them.

**Minimum Necessary Standard**: Each verification agent should receive only the PHI needed for its specific task. A citation-checking agent doesn't need full demographics.

**PHI Sanitization**: Hybrid rule-based regex + BERT-based NER achieves 99.4% precision / 97.6% recall. But residual leakage remains possible.

**Audit Logging**: HIPAA requires 6-year retention. Multi-agent systems need dual logging: interaction logs + decision logs with cryptographic hashing. LLM providers don't provide adequate audit trails — must be built by the deploying org.

**Architectural Recommendation**: Four specialized agents for HIPAA compliance:

1. Policy Decision Agent (evaluates access)
2. Middleware Agent (enforces policy in real-time)
3. Post-Inference Redaction Agent (removes residual PHI)
4. Audit Agent (maintains immutable logs)

---

## 18. Key Takeaways for Our ASAM/TJC System

### Highest-Priority Findings

1. **Negation is our #1 risk** (30% of clinical hallucinations). "Denies withdrawal" → "reports withdrawal" errors will directly corrupt ASAM dimensional ratings. Use structured assertion labels, not free text.

2. **Omissions > fabrications** (3.45% vs 1.47%). Our TJC audit will tend toward false negatives (missing documentation that exists). This is the safer failure direction for an audit tool.

3. **SOAP templating cuts errors 75%**. Structure the extraction prompts around explicit SOAP/DAP/DSAP sections.

4. **Multi-model verification is proven**: Hippocratic AI went from 80% → 99.02% with 16+ cross-checking models. Even 2-3 checker agents will dramatically help.

5. **No benchmarks exist** for ASAM or TJC LLM tasks. Our system operates in unvalidated territory — communicate this clearly.

6. **Cache the standards** (90% cost reduction). TJC/ASAM criteria are static across patients — perfect for prompt caching.

7. **Use deterministic quoting** for citations. Either Claude's Citations API or manual reference-ID substitution. Zero hallucination in quoted text.

8. **Build a golden dataset** of 100+ annotated cases for regression testing. Score 3x, take median. This is the foundation of quality.

### Recommended Implementation Order

1. **Prompt caching** on TJC/ASAM standards (free win, 90% cost savings)
2. **XML structured tagging** for document sections (free win, better parsing)
3. **Structured output with evidence fields** (free win, forces grounding)
4. **RapidFuzz citation verification** (replace exact substring matching)
5. **Multi-pass extraction** (hunt for gaps on second pass)
6. **Parallel checker agents** (citation, completeness, consistency, standards fidelity)
7. **Deterministic quoting** (zero hallucination in quoted sections)
8. **Golden dataset + regression tests** (ongoing quality assurance)

---

## Additional Sources (Deep Dive)

### Clinical Incidents & Production Systems

- [Google Med-Gemini hallucinated nonexistent body part (InsideHook)](https://www.insidehook.com/wellness/google-medical-ai-hallucinated-nonexistent-part-brain)
- [Hippocratic AI safety-focused LLM patent](https://hippocraticai.com/safety-focused-llm-patent/)
- [Ambient digital scribe error rates (ScienceDirect, 2025)](https://www.sciencedirect.com/science/article/pii/S2949761225000999)
- [Multi-model adversarial hallucination attacks (Communications Medicine, 2025)](https://www.nature.com/articles/s43856-025-01021-3)
- [FDA Warning Letter on AI Overreliance (Morgan Lewis, 2026)](https://www.morganlewis.com/blogs/asprescribed/2026/04/fdas-warning-letter-suggests-growing-scrutiny-of-ai-overreliance)
- [Microsoft Clinical Safeguards at Ignite 2025](https://techcommunity.microsoft.com/blog/healthcareandlifesciencesblog/highlights-from-ignite-2025-how-agentic-ai-and-microsoft-copilot-are-empowering/4474658)

### Clinical Faithfulness

- [Clinical safety framework (npj Digital Medicine, 2025)](https://www.nature.com/articles/s41746-025-01670-7)
- [Negation in LLMs (arXiv, March 2025)](https://arxiv.org/html/2503.22395v1)
- [Clinical assertion detection (arXiv, March 2025)](https://arxiv.org/html/2503.17425v1)
- [TIMER: Temporal Instruction Modeling (npj Digital Medicine, 2025)](https://www.nature.com/articles/s41746-025-01965-9)
- [Detecting Stigmatizing Language in SUD notes (PMC, 2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12363688/)
- [ASAM Criteria 4th Edition](https://www.asam.org/asam-criteria/asam-criteria-4th-edition)

### Adversarial Testing

- [DAS Red-Teaming Framework](https://arxiv.org/html/2508.00923)
- [Granular Fact-Checking for Healthcare LLMs](https://arxiv.org/html/2512.16189v1)
- [LLM Uncertainty Proxies (JAMIA)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11648734/)
- [Medical LLM Abstention (arXiv)](https://arxiv.org/html/2601.12471v2)
- [LLM Regression Testing (Evidently AI)](https://www.evidentlyai.com/blog/llm-regression-testing-tutorial)

### Context Engineering

- [Anthropic: Effective Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Context Rot (Chroma, 2025)](https://www.trychroma.com/research/context-rot)
- [Claude Prompt Caching Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Claude XML Tags Guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/use-xml-tags)
- [ACON: Agent Context Optimization (arXiv)](https://arxiv.org/pdf/2510.00615)

### Implementation

- [FActScore (GitHub)](https://github.com/shmsw25/factscore)
- [Instructor Library](https://python.useinstructor.com/)
- [Deterministic Quoting](https://mattyyeung.github.io/deterministic-quoting)
- [Claude Citations API](https://platform.claude.com/docs/en/build-with-claude/citations)
- [Claude Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Citation-Hallucination-Detection Pipeline](https://github.com/Vikranth3140/Citation-Hallucination-Detection)
- [HIPAA Compliant Agentic AI (arXiv, 2025)](https://arxiv.org/html/2504.17669v1)
