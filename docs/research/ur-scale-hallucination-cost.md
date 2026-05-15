# Scaling Clinical QA: Hallucination Reduction, Cost Optimization, and Architecture for Utilization Review

> Research on reducing hallucinations, cutting costs, and improving latency when processing hundreds of thousands of tokens of patient records against ~100 structured questions. Compiled May 2026.

---

## Table of Contents

1. [The Problem](#1-the-problem)
2. [Why the Current Approach Is Expensive](#2-why-the-current-approach-is-expensive)
3. [Map-Reduce vs Full-Context Architectures](#3-map-reduce-vs-full-context-architectures)
4. [Question Batching and Decomposition](#4-question-batching-and-decomposition)
5. [RAG vs Long Context for Clinical Documents](#5-rag-vs-long-context-for-clinical-documents)
6. [Structured Extraction vs Free-Form QA](#6-structured-extraction-vs-free-form-qa)
7. [Multi-Pass Verification That's Cost-Efficient](#7-multi-pass-verification-thats-cost-efficient)
8. [Prompt Caching: The Single Biggest Win](#8-prompt-caching-the-single-biggest-win)
9. [Model Routing and Cascading](#9-model-routing-and-cascading)
10. [Context Compression and Smart Chunking](#10-context-compression-and-smart-chunking)
11. [Gemini-Specific Issues](#11-gemini-specific-issues)
12. [Companies Doing UR Automation](#12-companies-doing-ur-automation)
13. [The Recommended Architecture](#13-the-recommended-architecture)
14. [Cost Breakdown: From Thousands to Dollars](#14-cost-breakdown-from-thousands-to-dollars)
15. [Sources](#15-sources)

---

## 1. The Problem

You have:

- **Hundreds of thousands of tokens** of patient progress notes and clinical records
- **~100 structured questions** that must be answered against this data
- An LLM (Gemini) that **hallucinates** — which is clinically dangerous
- A pipeline that **takes a very long time** to run
- Costs of **thousands of dollars per run**

This is a well-studied engineering problem. The research points to a clear set of solutions.

---

## 2. Why the Current Approach Is Expensive

If you send 500K input tokens to Gemini 2.5 Pro for each of 100 questions, you're processing **50 million input tokens per patient**:

| Scenario                       | Input Cost                     | Output Cost                   | Total/Patient |
| ------------------------------ | ------------------------------ | ----------------------------- | ------------- |
| Gemini 2.5 Pro (>200K context) | 50M × $2.50/MTok = **$125.00** | 50K × $15.00/MTok = **$0.75** | **$125.75**   |
| Gemini 2.5 Pro (<200K context) | 50M × $1.25/MTok = **$62.50**  | 50K × $10.00/MTok = **$0.50** | **$63.00**    |

At 10 patients: $630–$1,258. At 100 patients: **$6,300–$12,575**. The problem is re-reading the same patient record 100 times. Every optimization below attacks that redundancy.

**Gemini's >200K surcharge**: Gemini 2.5 Pro charges **2x on input and 1.5x on output** above 200K tokens. Claude has NO context-length surcharge — 900K tokens costs the same per-token rate as 9K tokens.

---

## 3. Map-Reduce vs Full-Context Architectures

### Why Full Context Fails at Scale

The "lost in the middle" problem worsens with scale:

| Position                | Accuracy                    |
| ----------------------- | --------------------------- |
| Beginning (tokens 1–1K) | ~95%                        |
| Middle (tokens 5K–15K)  | 40–60% (up to **50% drop**) |
| End (last 1–2K tokens)  | ~85%                        |

Effective reliable context lengths are much shorter than advertised:

| Advertised  | Reliably Effective |
| ----------- | ------------------ |
| Claude 200K | ~130K              |
| Gemini 1M   | ~650K              |
| GPT-4 128K  | ~83K               |

**Counterintuitive finding**: Chroma's Context Rot research (2025, 18 models tested) found models perform **worse** when the haystack preserves logical flow of ideas — shuffled, incoherent haystacks improved retrieval accuracy. Clinical notes are highly structured and narratively coherent, meaning they may **exacerbate** the lost-in-the-middle effect.

**Sequential-NIAH benchmark** (2025): When multiple needles must be found (analogous to answering 100 questions), even the best model achieved only **63.5% accuracy**, with further degradation as context length or needle count increased.

### LLMxMapReduce (ACL 2025)

The most promising map-reduce framework. Results:

- Llama3-70B with the framework scored **68.66** on InfiniteBench (100K+ tokens), outperforming GPT-4 (57.34), Claude 2 (51.62), and Qwen2-72B with native 128K context (54.74)
- Successfully processed sequences up to **1.28M tokens** using a model trained on only 8K context
- No parameter tuning required — works through prompting alone
- Halves GPU requirements (2 GPUs vs 4+)

It solves the two critical map-reduce failure modes:

1. **Inter-chunk dependency** (evidence spread across chunks): Structured information protocol extracts rationale, intermediate answers, and confidence scores per chunk
2. **Inter-chunk conflict** (contradictory information across chunks): In-context confidence calibration provides consistent scoring principles

The reduce step resolves conflicts correctly **74.7% of the time**.

Code: https://github.com/thunlp/LLMxMapReduce

### BriefContext: Map-Reduce for Medical QA

- GPT-3.5-turbo: 69.19% → 72.51% (+3.32pp)
- Llama3-70B: 76.75% → 79.03% (+2.28pp)
- Llama2-70B: 55.81% → 66.47% (+10.66pp, largest gain)
- Cost overhead: only ~10% input token increase
- Preflight check reduces unnecessary invocations by 35%

### Bottom Line

For 100K–1M+ tokens of clinical records with 100 questions, **pure full-context is unreliable**. Map-reduce with structured intermediate outputs and confidence calibration is the evidence-backed approach.

---

## 4. Question Batching and Decomposition

### The 50-Question Ceiling

The most relevant study (npj Digital Medicine, 2024) ran **300,000+ experiments** testing concatenation of multiple questions against clinical notes with 10 LLMs:

- GPT-4-turbo-128K and Llama-3-70B maintained acceptable performance up to **50 simultaneous tasks**
- Beyond 50 questions, failure rates increased substantially
- **17-fold cost reduction** at 50 tasks vs sequential queries
- OpenBioLLM-8B and BioMistral-7B: near-complete failure on JSON formatting at scale
- Llama-3-70B: consistently lowest failure rates

### Batch Size and Accuracy (2025 study)

Testing batch sizes of 10, 20, 30, 40, and 50 questions per batch:

- **GPT-4o accuracy dropped from ~0.90 at N=10 to ~0.85 at N=50**
- GPT-4o excels with smaller batches (≤20 questions)
- **Fine-tuned smaller models (Qwen2.5-7B, Llama3.1-8B) surpassed GPT-4o at 30+ questions per batch** — suggesting fine-tuned small models may be better for high-volume structured QA
- Optimal batch size: **10–20 questions per call** for frontier models

### BatchPrompt (ICLR 2024)

Naive batching degrades performance because autoregressive decoding conditions each answer on previous outputs. Solution: **Batch Permutation and Ensembling (BPE)** — majority vote over repeated permutations.

- At batch size 32, BPE achieved comparable accuracy with only **15.7% of LLM calls** and **18–30% of tokens**

### Practical Recommendation

For 100 questions against large clinical records:

- **Batch questions in groups of 10–20** (sweet spot for accuracy)
- Use structured output (JSON) with explicit citation requirements
- Consider question permutation across batches to detect position-dependent errors
- For highest-stakes questions (clinical safety), run individually as verification

---

## 5. RAG vs Long Context for Clinical Documents

### The ICLR 2025 Verdict

"Long-Context LLMs Meet RAG" (ICLR 2025):

- Increasing retrieved passages does **not consistently improve** performance with long-context LLMs
- **Hard negatives** (topically similar but wrong passages) are a primary cause of degradation
- With a large set of top-k chunks, **RAG consistently outperforms** direct long-context on both 32K and 128K benchmarks
- **No silver bullet** — optimal choice depends on model, context length, task type, and retrieval quality

### Clinical-Specific Comparison (2025)

Direct comparison on clinical EHR tasks:

- **Extraction tasks** (imaging procedures): RAG fell short by only 1.72–5.56 F1 points vs full 128K context with 60 retrieved chunks
- **Temporal reasoning** (antibiotic timelines): RAG slightly **exceeded** full-context performance (+2.14 F1)
- **Subjective tasks** (diagnosis generation): RAG showed slight disadvantages

Key insight: **Claude 3.5 Sonnet actually performed worse with RAG than without** (-2% accuracy), suggesting frontier models may handle long context better than chunked retrieval. But this was at moderate context sizes, not 500K+.

### Clinical-Specific Retrieval Challenges

1. **Temporal ordering**: TIMER (2025) showed specialized temporal models outperform standard medical LLMs by **6.6% in completeness** and **6.5% in temporal boundary adherence**
2. **Cross-document reasoning**: Knowledge graph approaches enable tracking medication changes, disease trajectories, treatment responses across visits
3. **Negation and abbreviations**: Semantic chunking (respecting note boundaries) is critical — fixed-size chunking breaks clinical meaning

### Practical Recommendation

Hybrid approach:

1. Pre-index all clinical documents with temporal-aware semantic chunking
2. For each question, retrieve 5–10 most relevant chunks using hybrid retrieval (BM25 + dense embeddings + re-ranker)
3. Process in moderate context (32K–64K range) rather than stuffing everything
4. For cross-document questions, use timeline extraction pre-processing

---

## 6. Structured Extraction vs Free-Form QA

### Structured JSON Reduces Hallucinations

NAACL 2024 Industry paper:

- **Without RAG**: hallucinated steps up to 21%, hallucinated tables up to 21.4%
- **With RAG + structured JSON**: hallucinated steps below 7.5%, hallucinated tables below 4.5%
- **Out-of-domain**: hallucination rates stable at ~2% with RAG
- A 7B model with RAG matched a 15.5B baseline without RAG

**Constrained decoding** (grammar-based token filtering) eliminates format errors but doesn't reduce factual hallucinations — it only ensures hallucinations are well-formatted.

### Field-Level Confidence Scoring (CMR-EXTR, 2025)

Per-field uncertainty combining three signals:

1. **Distribution score**: Is the extracted value within plausible clinical ranges?
2. **Stability score**: Does the value stay consistent across multiple model runs (temp 0.3)?
3. **Consistency score**: Does the value satisfy mathematical relationships with other extracted fields?

Results:

- **Below 0.7 confidence: 42% error rate**
- **Above 0.7 confidence: 1% error rate**
- **42-fold difference** validates confidence thresholds for automated triage
- Variable-level accuracy: 99.65% across 52 fields per report

### The Abstention Problem

MedAbstain (2025):

- Model abstention: **71.43% precision** but only **13.16% recall**
- Models fail to say "I don't know" **87% of the time they should**
- Chain-of-thought and model scaling provide **minimal benefit** for abstention
- Reasoning fine-tuning actually **degrades abstention by 24%** (AbstentionBench, 2025)

Claude is the safest choice here — Chroma's research found Claude models exhibited the most conservative behavior with distractors, preferring to **abstain rather than hallucinate**. Gemini generates random non-input words, GPT fabricates plausibly.

### Practical Recommendation

1. **Strict JSON schemas** for all questions with required fields: `answer`, `confidence_score`, `supporting_quote`, `source_document`, `source_date`
2. **Require verbatim quotes** before any answer — Anthropic recommends this for documents over 20K tokens
3. **Verify-then-retract pattern**: after generating, review each claim and retract any without supporting quotes
4. **Field-level confidence scoring**: run extraction 3 times, flag inconsistent fields
5. **Auto-accept above 0.7, human review below 0.7** (based on CMR-EXTR's 42x error rate differential)

---

## 7. Multi-Pass Verification That's Cost-Efficient

### What Works: Anterior's Production System

**Anterior** processes **100,000 medical decisions daily** covering 50 million lives:

- **F1 score of 96%** on prior authorization decisions
- Uses an **LLM-as-judge evaluation** that scores outputs from "high confidence" to "active prediction of incorrectness"
- Generates a predicted correct output alongside actual output for comparison
- **Fewer than 10 clinical experts** managing tens of thousands of cases (competitors: 800+ nurses)
- Hallucination rate: approximately once per thousand or ten thousand cases

### Confidence-Informed Self-Consistency (CISC, ACL 2025)

Improves upon standard self-consistency voting:

- **Outperforms standard self-consistency** in nearly all configurations
- Reduces required reasoning paths by **over 40%**
- Standard self-consistency needs 18.6 responses to match CISC's accuracy with 10 samples — **46% cost reduction**

### What Does NOT Work

- **Best-of-N** (running same prompt N times and comparing): expensive, less effective than a single structured verification pass
- **Self-review in same context**: asking the model to "check its work" in the same window is unreliable
- **Multiple expensive models in parallel**: cost-prohibitive at scale

### The Three-Tier Architecture

**Tier 1 — Primary Extraction** (most expensive, run once):

- Map-reduce across document chunks
- Batch 10–20 questions per chunk
- JSON with verbatim quotes and confidence scores
- Prefix caching across question batches

**Tier 2 — Deterministic Verification** (very cheap):

- String-match all quoted text against source documents (RapidFuzz)
- Check extracted values against clinical ranges
- Cross-validate related fields (admission before discharge, etc.)
- Flag answers without supporting quotes for re-extraction

**Tier 3 — Targeted Re-extraction** (moderate cost, only flagged items):

- Re-run only failed/low-confidence questions with different chunk selection
- CISC with 10 samples only for safety-critical questions
- Escalate to human review if still uncertain

---

## 8. Prompt Caching: The Single Biggest Win

You're asking 100 questions about the same patient record. Without caching, you pay for 500K input tokens 100 times. With caching, you pay full price once and 90% less for the other 99.

### How Caching Works Across Providers

| Feature                 | Anthropic (Claude)                   | Google (Gemini)          | OpenAI (GPT-4.1)     |
| ----------------------- | ------------------------------------ | ------------------------ | -------------------- |
| **Cache read discount** | 90% off (0.1x base)                  | 90% off (0.1x base)      | 50% off (0.5x base)  |
| **Cache write cost**    | 1.25x base (5-min) or 2x base (1-hr) | Standard input price     | No extra cost        |
| **TTL**                 | 5 min or 1 hour (explicit)           | Configurable (min 1 min) | Automatic, ~5-10 min |
| **Control**             | Explicit breakpoints (up to 4)       | Explicit cache creation  | Fully automatic      |

### The Math

Optimal structure: **patient record in cached prefix, question at the end.**

```
[SYSTEM PROMPT - cached]          # ~2K tokens: UR standards, output format
[PATIENT RECORD - cached]         # ~500K tokens: the clinical document
[QUESTION - varies each call]     # ~200 tokens: the specific question
```

**Claude Sonnet 4.6, 5-min cache:**

- Call 1: 500K tokens at 1.25x = 625K token-equivalents
- Calls 2–100: 500K tokens at 0.1x = 50K token-equivalents each
- Total: 625K + (99 × 50K) = **5,575K tokens** instead of 50,000K
- **Savings: ~89%**

### With Batch API Stacked

Anthropic Batch API gives 50% discount on all tokens, stacks with caching:

| Component                     | Calculation               | Cost      |
| ----------------------------- | ------------------------- | --------- |
| Cache write (1 call, batch)   | 0.5M × $3.00 × 1.25 × 0.5 | $0.94     |
| Cache reads (99 calls, batch) | 99 × 0.5M × $0.30 × 0.5   | $7.43     |
| Output (100 calls, batch)     | 100 × 500 × $7.50/MTok    | $0.38     |
| **Total per patient**         |                           | **$8.74** |

Down from $150.75 naive approach. **94% reduction.**

---

## 9. Model Routing and Cascading

### Not All Questions Need the Same Model

**FrugalGPT** (Stanford, 2023/2024): 50–98% cost reduction by cascading cheap → expensive models. On some benchmarks, matched GPT-4 at 2% of the cost.

| Question Type      | Example                                       | Recommended Model                                 | $/MTok Input |
| ------------------ | --------------------------------------------- | ------------------------------------------------- | ------------ |
| Simple extraction  | "Patient DOB", "Primary diagnosis"            | GPT-4.1 Nano ($0.05) or Gemini Flash-Lite ($0.10) | ~$0.05–0.10  |
| Structured lookup  | "List all medications", "Document all vitals" | GPT-4.1 Mini ($0.40) or Gemini 2.5 Flash ($0.30)  | ~$0.30–0.40  |
| Clinical reasoning | "Is continued stay medically necessary?"      | Claude Sonnet ($3.00) or Gemini 2.5 Pro ($1.25)   | ~$1.25–3.00  |
| Complex judgment   | "Synthesize trajectory, recommend step-down"  | Claude Opus ($5.00)                               | ~$5.00       |

If 60 of 100 questions are simple/structured and 40 require clinical reasoning, routing cuts costs by another **50–70%** on top of caching.

### Confidence-Based Cascading

1. Send to Haiku/Flash-Lite with instruction to rate confidence 1–5
2. Confidence ≥ 4: accept answer
3. Confidence < 4: re-send to Sonnet/Pro
4. Still uncertain: escalate to Opus or human review

**Safety note**: For clinical tasks, false confidence is dangerous. Use conservative thresholds.

---

## 10. Context Compression and Smart Chunking

### LLMLingua Family (Microsoft)

- **LLMLingua**: Up to 20x compression with only 1.5% performance loss on reasoning tasks
- **LLMLingua-2** (ACL 2024): 3–6x faster, better on out-of-domain data
- **LongLLMLingua**: Specifically for long-context — improved RAG performance by **21.4%** using only 25% of tokens

Clinical notes contain enormous redundancy: repeated headers, templated sections, copy-forwarded information, administrative boilerplate. Compression is particularly effective.

**Caution**: Clinical documents contain safety-critical details (medication doses, lab values, dates) where even minor information loss can be catastrophic. Validate against clinical accuracy before deploying compression.

### Pre-Filtering Approach

Instead of compressing, use a two-stage pipeline:

1. **Stage 1 — Relevance filtering**: Cheap model (GPT-4.1 Nano, $0.05/MTok) reads full record once, extracts/tags relevant sections per question category
2. **Stage 2 — Focused answering**: Send only relevant sections (10–50K tokens instead of 500K) to the answering model

This reduces effective context by **10–50x** for many questions.

### Query Concatenation + Pre-Filtering Combined

The npj Digital Medicine study found concatenating multiple questions yields up to **17x cost reduction** (at 50 tasks per call). GPT-4-turbo-128K and Llama-3-70B maintained accuracy up to 50 simultaneous tasks.

For 100 questions: send 5–10 batches of 10–20 questions each against pre-filtered context. This cuts API calls, reduces context per call, and maintains accuracy.

---

## 11. Gemini-Specific Issues

### Why Gemini May Not Be the Right Choice for Clinical UR

| Dimension                    | Claude              | GPT-4/4o              | Gemini                          |
| ---------------------------- | ------------------- | --------------------- | ------------------------------- |
| Hallucination rate (factual) | ~3%                 | ~6–28% (varies)       | ~6%                             |
| Sycophancy rate              | Lowest              | Moderate              | **Highest (62.5%)**             |
| Abstention behavior          | Says "I don't know" | Fabricates plausibly  | **Generates random words**      |
| Long-context degradation     | Slowest             | Highest hallucination | **Most variable/unpredictable** |
| Medical accuracy (neuro)     | 83%                 | 80–82%                | 53–91% (highly variable)        |

### Specific Gemini Problems

1. **Sycophancy** (62.47%): Gemini-1.5-Pro has the highest sycophancy rate. In clinical contexts, agreeing with incorrect user assumptions is dangerous. If the system provides incorrect context or framing, Gemini is most likely to go along with it.

2. **Random word generation**: Unlike Claude (which abstains) or GPT (which hallucinates plausibly), Gemini generates **random, non-input words** starting around 500–750 words of context. This is a distinctively unreliable failure mode.

3. **Context variability**: Gemini 2.5 Pro showed the **greatest variability** in context rot testing across 18 frontier models. Inconsistency is as dangerous as inaccuracy — you can't trust that what worked once will work again.

4. **>200K surcharge**: The 2x pricing above 200K tokens makes large clinical records disproportionately expensive.

### Med-Gemini: Impressive but Limited

Google's Med-Gemini achieved 91.1% on MedQA and was tested on ICU records up to **700,000 words long**. However:

- This was a controlled benchmark, not production deployment
- The fine-tuned Med-Gemini is not publicly available
- Standard Gemini 2.5 Pro in production has the weaknesses listed above

### Recommendation

**Switch from Gemini to Claude for clinical safety reasons.** Claude's lower hallucination rate, conservative abstention behavior, and no context-length surcharge make it better suited for clinical UR. Use Gemini Flash for non-safety-critical tasks (pre-filtering, section tagging) where its cost advantage matters and its failure modes are less dangerous.

---

## 12. Companies Doing UR Automation

### Major Players

**Anterior** — The most technically transparent:

- 100,000+ medical decisions daily, 50 million lives covered
- F1 of 96% on prior auth decisions
- LLM-as-judge evaluation loop — low-confidence cases routed to human reviewers
- **Fewer than 10 clinical experts** (competitors: 800+ nurses)
- AI-to-human alignment "comparable to human-to-human reviewer alignment"

**Cohere Health** — Largest payer-side UR platform:

- $90M raised, 9 million FHIR-based authorizations processed
- "Review Assist" agentic AI: 99%+ precision, 50% faster reviews, 85% real-time handling
- Fine-tuned LLMs (base model undisclosed)

**Waystar** — Provider-side:

- "Auth Accelerate": 70% reduction in submission times, 85% auto-approval rates

**Google Cloud** — Published reference architecture (Aug 2024) for UR automation using Vertex AI Gemini API

**ASAM Criteria Navigator** (Optum): Computer-guided structured clinical interview for ASAM level-of-care, aligned with 4th Edition. Not LLM-based — structured decision-support tool.

### Architectural Pattern Across All Companies

1. Document ingestion (structured + unstructured)
2. Evidence extraction (LLM/NLP pulls relevant clinical facts)
3. Decision engine (evaluates evidence against criteria)
4. Confidence scoring (LLM-as-judge or rule-based)
5. Human-in-the-loop (low-confidence → clinical reviewers)
6. Feedback loop (human corrections feed back)

---

## 13. The Recommended Architecture

Based on all research, here is the concrete architecture for processing 100K–1M+ tokens against ~100 questions:

### Step 1: Document Preparation

```
Clinical Records (100K–1M+ tokens)
         │
         ▼
┌─────────────────────────┐
│  Semantic Chunking       │  Respect note boundaries
│  + Temporal Index        │  Preserve dates, authors, note types
│  + Pre-compute Embeddings│  For hybrid retrieval
└────────────┬────────────┘
```

### Step 2: Question Classification

```
100 UR Questions
         │
         ▼
┌─────────────────────────────────────────┐
│  Classify each question:                 │
│  • Simple extraction (DOB, diagnosis)    │ → Cheap model
│  • Structured lookup (med list, vitals)  │ → Mid-tier model
│  • Clinical reasoning (medical necessity)│ → Best model
│  • Cross-document (trajectory over time) │ → Map-reduce
└──────────────┬──────────────────────────┘
```

### Step 3: Extraction (Map Phase)

```
For each question batch (10–20 questions):
  ┌─────────────────────────────────────────────┐
  │  1. Retrieve top 5–10 relevant chunks        │
  │  2. Assemble into moderate context (32K–64K) │
  │  3. Batch questions with JSON schema          │
  │  4. Require: answer, confidence, quote,       │
  │     source_document, source_date              │
  │  5. Use prefix caching for shared context     │
  └─────────────────────────────────────────────┘
```

### Step 4: Deterministic Verification (Very Cheap)

```
For every answer:
  ✓ String-match verbatim quotes against source documents (RapidFuzz)
  ✓ Check extracted values against clinical ranges
  ✓ Cross-validate related fields
  ✓ Flag any answer missing a valid quote or confidence < 0.7
```

### Step 5: Targeted Re-extraction (Only Flagged Items)

```
  ┌───────────────────────────────────────────┐
  │  Re-run only failed/low-confidence items   │
  │  • Different chunk selection or full context│
  │  • CISC (10 samples) for safety-critical   │
  │  • Escalate to human if still uncertain    │
  └───────────────────────────────────────────┘
```

### Step 6: Final Assembly

```
  ┌───────────────────────────────────────────┐
  │  Assemble all answers into UR report       │
  │  Include: per-field confidence scores      │
  │  Highlight: items that needed re-extraction│
  │  Flag: items sent to human review          │
  └───────────────────────────────────────────┘
```

---

## 14. Cost Breakdown: From Thousands to Dollars

### Scenario: 500K token patient record, 100 questions, ~500 output tokens/answer

#### Current: Naive Approach (No Optimization)

| Provider               | Input Cost | Output Cost | Total/Patient | 100 Patients |
| ---------------------- | ---------- | ----------- | ------------- | ------------ |
| Gemini 2.5 Pro (>200K) | $125.00    | $0.75       | **$125.75**   | **$12,575**  |
| Claude Sonnet 4.6      | $150.00    | $0.75       | **$150.75**   | **$15,075**  |
| GPT-4.1                | $100.00    | $0.40       | **$100.40**   | **$10,040**  |

#### Optimization 1: Prompt Caching Only

| Provider                           | Total/Patient | Savings |
| ---------------------------------- | ------------- | ------- |
| Claude Sonnet (5-min cache)        | **$17.48**    | 88%     |
| Gemini 2.5 Pro (context cache)     | **~$15.25**   | 88%     |
| GPT-4.1 (auto cache, 50% off only) | **~$50.90**   | 49%     |

#### Optimization 2: Caching + Batch API (Claude Sonnet)

| Component                     | Cost      |
| ----------------------------- | --------- |
| Cache write (1 call, batch)   | $0.94     |
| Cache reads (99 calls, batch) | $7.43     |
| Output (100 calls, batch)     | $0.38     |
| **Total per patient**         | **$8.74** |
| **100 patients**              | **$874**  |
| **Savings vs. naive Gemini**  | **93%**   |

#### Optimization 3: Caching + Batch + Model Routing

60 simple questions → Haiku 4.5 (batch), 40 complex → Sonnet 4.6 (batch), all cached:

| Component                            | Cost       |
| ------------------------------------ | ---------- |
| Haiku: cache write + reads + output  | $1.87      |
| Sonnet: cache write + reads + output | $4.02      |
| **Total per patient**                | **~$5.88** |
| **100 patients**                     | **~$588**  |
| **Savings vs. naive Gemini**         | **95%**    |

#### Optimization 4: Everything Combined (Maximum)

Batching 10–20 questions per call + caching + batch API + routing + pre-filtering:

| Component                              | Cost       |
| -------------------------------------- | ---------- |
| Pre-filter pass (Nano, full doc, once) | ~$0.03     |
| 5–10 API calls with cached context     | ~$2.50     |
| Output                                 | ~$0.50     |
| **Total per patient**                  | **~$3.00** |
| **100 patients**                       | **~$300**  |
| **Savings vs. naive Gemini**           | **97.6%**  |

#### Nuclear Option: Gemini 2.5 Flash with Caching + Batch

If clinical quality is sufficient (needs validation):

| **Total per patient** | **~$1.25** |
| --------------------- | ---------- |
| **100 patients**      | **~$125**  |

### Summary

| Approach                      | Cost/Patient | Cost/100 Patients | vs. Current       |
| ----------------------------- | ------------ | ----------------- | ----------------- |
| Current (Gemini Pro, naive)   | $125.75      | $12,575           | Baseline          |
| Cache only                    | $17.48       | $1,748            | 86% savings       |
| Cache + Batch                 | $8.74        | $874              | 93% savings       |
| Cache + Batch + Routing       | $5.88        | $588              | 95% savings       |
| All optimizations             | $3.00        | $300              | **97.6% savings** |
| Flash (if quality sufficient) | $1.25        | $125              | 99% savings       |

---

## 15. Sources

### Map-Reduce and Long-Context

- [LLMxMapReduce (ACL 2025)](https://arxiv.org/html/2410.09342v1)
- [BriefContext MapReduce for RAG](https://arxiv.org/html/2412.15271v1)
- [Context Rot (Chroma Research, 2025)](https://www.trychroma.com/research/context-rot)
- [Sequential-NIAH Benchmark](https://arxiv.org/abs/2504.04713)
- [Lost in the Middle (TACL 2024)](https://aclanthology.org/2024.tacl-1.9/)

### Question Batching

- [Cost-Effective LLM Use at Health System Scale (npj Digital Medicine, 2024)](https://www.nature.com/articles/s41746-024-01315-1)
- [Multi-Question Answering Accuracy on Transcripts (arXiv 2509.21732)](https://arxiv.org/html/2509.21732v1)
- [BatchPrompt (ICLR 2024)](https://arxiv.org/pdf/2309.00384)

### RAG vs Long Context

- [Long-Context LLMs Meet RAG (ICLR 2025)](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5df5b1f121c915d8bdd00db6aac20827-Abstract-Conference.html)
- [LaRA Benchmark (ICML 2025)](https://openreview.net/forum?id=CLF25dahgA)
- [RAG vs Long-Context for Clinical EHR Reasoning (arXiv)](https://arxiv.org/html/2508.14817)
- [RAG in Biomedical Applications (JAMIA)](https://academic.oup.com/jamia/article/32/4/605/7954485)

### Structured Extraction and Hallucination

- [Structured Output Hallucination Reduction (NAACL 2024)](https://arxiv.org/html/2404.08189v1)
- [CMR-EXTR Field-Level Confidence (2025)](https://arxiv.org/html/2605.08045)
- [MedAbstain (2025)](https://arxiv.org/html/2601.12471v2)
- [AbstentionBench (2025)](https://arxiv.org/html/2506.09038v1)
- [Anthropic Hallucination Reduction Docs](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations)

### Verification and Production Systems

- [Anterior: LLM Evaluation for Prior Auth (ZenML)](https://www.zenml.io/llmops-database/building-scalable-llm-evaluation-systems-for-healthcare-prior-authorization)
- [CISC: Confidence-Informed Self-Consistency (ACL 2025)](https://aclanthology.org/2025.findings-acl.1030/)
- [Cohere Health Review Assist](https://www.prnewswire.com/news-releases/cohere-healths-review-assist-accelerates-clinical-reviews-for-health-plans-with-precision-ai-302482034.html)

### Cost and Pricing

- [Anthropic Claude Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Anthropic Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Anthropic Batch Processing](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Google Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [OpenAI API Pricing](https://developers.openai.com/api/docs/pricing)
- [FrugalGPT (Stanford, 2023/2024)](https://arxiv.org/abs/2305.05176)

### Gemini Clinical Performance

- [Med-Gemini (arXiv 2404.18416)](https://arxiv.org/abs/2404.18416)
- [Gemini Sycophancy in Clinical Contexts (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12474969/)
- [Gemini 1.5 Technical Report](https://arxiv.org/html/2403.05530v2)
- [LLM Hallucination Rates Comparison (Llumo)](https://www.llumo.ai/blog/comparing-hallucination-rates-across-gpt4-claude-gemini-and-more-model-hallucination-comparison)

### Clinical QA and UR

- [TIMER: Temporal Clinical Reasoning (npj Digital Medicine, 2025)](https://www.nature.com/articles/s41746-025-01965-9)
- [CLEVER Framework (JMIR AI)](https://ai.jmir.org/2025/1/e72153)
- [CuraView: Multi-Agent Hallucination Detection](https://arxiv.org/html/2605.03476)
- [Clinical Text Summarization Scoping Review (JMIR)](https://www.jmir.org/2025/1/e68998)
- [ASAM Criteria 4th Edition (NAIC Presentation)](https://content.naic.org/sites/default/files/national_meeting/ASAM%20Presentation.pdf)
- [Google Cloud UR Architecture](https://docs.google.com/architecture/use-generative-ai-utilization-management)

### Compression and Chunking

- [LLMLingua (Microsoft)](https://llmlingua.com/llmlingua.html)
- [LongLLMLingua](https://arxiv.org/abs/2310.06839)
- [Strata: Clinical Information Extraction (Nature Scientific Reports)](https://www.nature.com/articles/s41598-025-28767-z)

### Benchmarks and Evaluation

- [CSEDB: Clinical LLM Benchmark (npj Digital Medicine)](https://www.nature.com/articles/s41746-025-02277-8)
- [NEJM AI: Clinical Reasoning Benchmark](https://ai.nejm.org/doi/full/10.1056/AIdbp2500120)
- [NEJM AI: Verifying Facts in Patient Care Documents](https://ai.nejm.org/doi/full/10.1056/AIdbp2500418)
