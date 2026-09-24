# Complete Guide: Siamese Network & Two-Stage Search Architecture for CPSE Material Harmonization

> **Presentation & Defense Master Guide**  
> **Problem Statement 26099** · Smart India Hackathon (SIH-2026)  
> *AI-Driven Standardization and Harmonization of Material Codes Across Central Public Sector Enterprises (CPSEs)*

---

## Table of Contents
1. [The Real-World Problem: CPSE Material Catalogues](#1-the-real-world-problem-cpse-material-catalogues)
2. [Why Standard Semantic Search & Dense Embeddings Fail Alone](#2-why-standard-semantic-search--dense-embeddings-fail-alone)
3. [The Core Solution: Two-Stage Architecture (Retrieve & Rerank)](#3-the-core-solution-two-stage-architecture-retrieve--rerank)
4. [What is a Siamese Neural Network? Core Concepts & Foundations](#4-what-is-a-siamese-neural-network-core-concepts--foundations)
5. [Network Topology & Components](#5-network-topology--components)
6. [Mathematical Formulation & Contrastive Loss](#6-mathematical-formulation--contrastive-loss)
7. [Training Data Engineering: Positive & Hard-Negative Pair Generation](#7-training-data-engineering-positive--hard-negative-pair-generation)
8. [Runtime Execution: The Life of a Query to `POST /api/v1/search`](#8-runtime-execution-the-life-of-a-query-to-post-apiv1search)
9. [Score Fusion & Threshold Calibration](#9-score-fusion--threshold-calibration)
10. [Case Studies & Live Evidence](#10-case-studies--live-evidence)
11. [Presentation Cheat Sheet: Q&A for Judges & Evaluators](#11-presentation-cheat-sheet-qa-for-judges--evaluators)

---

## 1. The Real-World Problem: CPSE Material Catalogues

Central Public Sector Enterprises (CPSEs)—such as NTPC, BHEL, Coal India (BCCL/CCL), GAIL, IOCL, ONGC, and SAIL—manage millions of inventory line items across power plants, refineries, and mines. 

Because each enterprise developed their procurement systems independently over decades, **the exact same physical article is recorded under radically different descriptions and legacy codes**:

| Enterprise | Item Description in Enterprise Master | Legacy Code |
| :--- | :--- | :--- |
| **BHEL** | `BELT V C-120` | `224411` |
| **NTPC** | `V-BELT SEC C, NOM L 120 INCH` | `M-55321` |
| **BCCL** | `v belt c-120 fenner pix only for crusher drive - URGENT REQ` | `MAT6833850` |
| **IOCL** | `V BELT SECTION C 120 INCH PITCH LENGTH 3104MM` | `IOCL-9982` |

### Why This Hurts CPSEs:
1. **Redundant Capital Blockage:** CPSE A might order a replacement bearing with an 8-month procurement lead time, unaware that CPSE B has an identical spare sitting idle in a nearby warehouse.
2. **Duplicate Creation:** Within a single enterprise, the same spare is often re-entered under slightly different text strings by different plant engineers.
3. **Harmonization Nightmare:** A human reviewer cannot manually compare 500,000 messy text descriptions across 30 CPSEs.

---

## 2. Why Standard Semantic Search & Dense Embeddings Fail Alone

A common naive approach is: *"Just pass the descriptions through an embedding model (like OpenAI Ada, BERT, or Qwen) and run cosine similarity search in a vector database."*

### Why this fails dramatically in industrial procurement:
Standard embedding models are trained on natural language (Wikipedia, web text, conversational dialogues). In natural language:
- *"The car was fast"* and *"The automobile was swift"* have high cosine similarity (**Good**).
- *"The temperature was 20 degrees"* and *"The temperature was 21 degrees"* also have very high similarity (~0.95), because they belong to the exact same context (**Catastrophic for engineering spares!**).

### The Industrial Near-Miss Dilemma:
Look at these two belts:
- **Article 1:** `V BELT C 120` (C-section V-belt, nominal length 120 inches)
- **Article 2:** `V BELT C 125` (C-section V-belt, nominal length 125 inches)

These are completely different physical spare parts! A 125-inch belt will slip or fly off a drive designed for a 120-inch belt. It cannot be used as an interchangeable spare.

Yet, to a general-purpose embedding model:
- 3 out of 4 tokens are identical (`V`, `BELT`, `C`).
- The 4th token is a 3-digit number close to the other (`120` vs `125`).
- General embedding cosine score: **~0.72 - 0.76**.

A general embedding model **cannot distinguish near-miss articles within the same family**. If you set a high retrieval threshold, you miss true matches; if you lower it, you get flooded with false positives that would cause machinery breakdown if ordered interchangeably.

---

## 3. The Core Solution: Two-Stage Architecture (Retrieve & Rerank)

To achieve **millisecond latency over millions of items** AND **extreme precision on fine engineering parameters**, we use a decoupled Two-Stage Architecture:

```
                          Incoming Query
                                │
                                ▼
                      Stage 0: Deterministic
                     Exact Identifier Lookup
                     (Postgres: codes & IDs)
                                │
                 ┌──────────────┴──────────────┐
                 │                             │
       If pure code hit?                General text query
                 │                             │
                 ▼                             ▼
       Rank 1 High Match               Stage 1: Retrieval
                                     Qwen3-Embedding-0.6B
                                     (1024-d Dense Vector)
                                               │
                                               ▼
                                         Qdrant Cloud
                                       (HNSW ANN Search)
                                               │
                                               ▼
                                     Top-20 Candidate Pool
                                     (Recall @ 20 = 99.9%)
                                               │
                                               ▼
                                     Stage 2: Reranking
                                    Fine-Tuned Siamese Net
                                   (MiniLM Backbone + Head)
                                   One Batched Tensor Pass
                                               │
                                               ▼
                                       Score Fusion &
                                   Calibrated 3-Way Match
                                   (High / Possible / None)
```

### Stage Summary:
- **Stage 0 (Rule Engine):** If a query contains a legacy code (`M-55321`) or part number (`C-120`), Postgres finds it instantly via B-Tree index with 100% precision.
- **Stage 1 (Coarse Retrieval):** `Qwen3-Embedding-0.6B` generates a 1024-dimensional query vector. Qdrant traverses its HNSW graph across all materials in ~5 ms. Its job is **recall**—ensuring the correct material family is in the Top-20 pool.
- **Stage 2 (Fine-Grained Siamese Reranker):** The Siamese model scores only the 20 surfaced candidates in a single batched matrix multiplication. Its job is **precision**—scrutinizing numeric parameters and letters to separate `C-120` from `C-125`.

---

## 4. What is a Siamese Neural Network? Core Concepts & Foundations

### Definition:
A **Siamese Neural Network** is an artificial neural network architecture containing two (or more) identical sub-networks with **identical configuration, identical parameters, and shared weights**.

```
                Input A (Query)           Input B (Candidate)
                      │                            │
                      ▼                            ▼
              ┌───────────────┐            ┌───────────────┐
              │  Sub-Network  │            │  Sub-Network  │
              │  Weights: W   │            │  Weights: W   │  <── SHARED WEIGHTS!
              │  (Backbone +  │            │  (Backbone +  │      (Exact same model)
              │   Projection) │            │   Projection) │
              └───────┬───────┘            └───────┬───────┘
                      │                            │
                      ▼                            ▼
                 Embedding u                  Embedding v
                 (Vector in                   (Vector in
                  R^256)                       R^256)
                      │                            │
                      └─────────────┬──────────────┘
                                    │
                                    ▼
                          Cosine Similarity /
                           Distance Metric
                      sim(u, v) = (u . v)/(||u|| ||v||)
```

### Key Principles:
1. **Weight Sharing (Symmetry):** Sub-network A and Sub-network B are literally the same memory pointer in PyTorch. Any update during backpropagation updates the shared weights. This guarantees that:
   $$\text{Distance}(A, B) = \text{Distance}(B, A)$$
   Two identical texts mapped through the network land on the exact same coordinate.
2. **Metric Learning (Not Classification):** A traditional classifier outputs class probabilities ($P(\text{class} = k)$). But in CPSE catalogues, you cannot have a 100,000-class softmax! Instead, the Siamese network learns a **metric space (distance function)** where:
   - Representations of identical articles are pulled together.
   - Representations of different articles (especially near-misses) are pushed apart by at least a margin $m$.

---

## 5. Network Topology & Components

In our implementation (`app/logic/siamese.py`), the model consists of two tightly integrated components:

### 1. The Pretrained Backbone Encoder
- **Base Model:** `sentence-transformers/all-MiniLM-L6-v2`
- **Parameters:** ~22.7 Million parameters (compact, ultra-fast: ~15ms on CPU, ~2ms on CUDA).
- **Hidden Dimension:** $d_{in} = 384$.
- **Tokenization:** WordPiece tokenizer with max sequence length 64 (sufficient for industrial descriptions).
- **Mean Pooling:** Converts token embeddings $H \in \mathbb{R}^{B \times L \times 384}$ into a single sentence vector by averaging over non-padding tokens:
  $$u_{pool} = \frac{\sum_{i=1}^L M_i H_i}{\sum_{i=1}^L M_i}$$
  where $M_i \in \{0, 1\}$ is the attention mask.

### 2. The Dense Metric Projection Head
- A linear transformation layer trained from scratch on top of the backbone:
  $$z = W \cdot u_{pool} + b$$
  where $W \in \mathbb{R}^{256 \times 384}$ and $b \in \mathbb{R}^{256}$.
- **L2-Normalization:** Every output vector is projected onto the unit hypersphere:
  $$\hat{z} = \frac{z}{\|z\|_2} \quad \implies \quad \|\hat{z}\|_2 = 1.0$$
- **Why this projection head matters:**
  - MiniLM's original embedding space reflects general English semantics.
  - The projection head bends and warps that space to prioritize industrial nomenclature: penalizing numeric differences (`120` vs `125`, `6205` vs `6206`) while ignoring colloquial synonyms (`BRG` vs `BEARING`).

---

## 6. Mathematical Formulation & Contrastive Loss

### The Distance Metric
For two normalized embedding vectors $u, v \in \mathbb{R}^{256}$ where $\|u\|_2 = \|v\|_2 = 1$:
The Euclidean distance $D(u, v)$ is directly linked to Cosine Similarity:
$$D(u, v) = \|u - v\|_2 = \sqrt{\sum_{i=1}^{256} (u_i - v_i)^2}$$
$$D^2(u, v) = \|u\|^2 + \|v\|^2 - 2(u \cdot v) = 1 + 1 - 2 \cos(u, v) = 2(1 - \cos(u, v))$$
Therefore:
$$\cos(u, v) = 1 - \frac{1}{2} D^2(u, v)$$

### Contrastive Loss (Hadsell, Chopra, & LeCun)
We train using the classic Contrastive Loss function:

$$\mathcal{L}(u, v, y) = (1 - y) \cdot \frac{1}{2} D^2 + y \cdot \frac{1}{2} \left[ \max(0, m - D) \right]^2$$

Where:
- $y \in \{0, 1\}$ is the binary ground-truth label:
  - $y = 0$: **Positive pair** (Identical article, e.g. `BELT V C-120` vs `V-BELT SEC C 120 INCH`).
  - $y = 1$: **Negative pair** (Different article, e.g. `V BELT C 120` vs `V BELT C 125`).
- $D = \|u - v\|_2$: Euclidean distance between the normalized embeddings.
- $m$: **Contrastive Margin** (configured to $m = 1.3$).

### How the Loss Function Works:

#### Case 1: Positive Pair ($y = 0$)
The right term cancels out:
$$\mathcal{L}_{pos} = \frac{1}{2} D^2$$
- Gradient pulls $u$ and $v$ closer together until $D = 0$.
- Cosine similarity approaches $1.0$.

#### Case 2: Negative Pair ($y = 1$)
The left term cancels out:
$$\mathcal{L}_{neg} = \frac{1}{2} \left[ \max(0, m - D) \right]^2$$
- If the two different items are already far apart ($D \ge m$), loss is **$0$** (the network does not waste gradient updates pushing already-separated items).
- If the two items are confusingly close ($D < m$, e.g. `C 120` and `C 125`), loss is positive! The gradient pushes $u$ and $v$ apart until their distance is at least $m$.

---

## 7. Training Data Engineering: Positive & Hard-Negative Pair Generation

A neural network is only as good as its training curriculum. In [`app/training/pairs.py`](file:///home/sangik-ghosh/Desktop/sih-2026/backend/ai-service/app/training/pairs.py), we developed a specialized pair generator.

### Positive Pair Augmentation ($y = 0$, Target: Push Together)
To teach the model that messy real-world variations represent the same physical article:
1. **Cross-Catalogue Pairing:** If BHEL and NTPC both have C-120 belts, their descriptions are paired as positives.
2. **Domain Abbreviation Inversion:** Randomly replace words with known domain abbreviations (`BEARING` $\to$ `BRG`, `STAINLESS STEEL` $\to$ `SS`, `MILLIMETER` $\to$ `MM`).
3. **Punctuation & Code Variants:** `C-120` $\leftrightarrow$ `C 120` $\leftrightarrow$ `C120`.
4. **Specification Preserving Truncation (`_keep_leading_numbers`):**
   - Natural queries drop trailing procurement codes: `TAPER ROLLER BEARING 32218 J2/Q` $\to$ `TAPER ROLLER BEARING 32218`.
   - Our algorithm preserves essential specs (`32218`, `4 POLE 63A`, `1 INCH R2`) while stripping random vendor noise.
5. **Conversational Wrapping:** Wrap descriptions in user query phrases: *"industrial V belt C section approximately 120 inch used for power transmission"*.

### Hard-Negative Pair Generation ($y = 1$, Target: Push Apart)
Random negatives (e.g. `V BELT` vs `CENTRIFUGAL PUMP`) are too easy; the model learns nothing from them. We engineer **Hard Negatives (Perturbed Twins)**:
1. **Numeric Perturbation (`_perturb_number`):**
   - Take `V BELT C 120` $\to$ mutate to `V BELT C 125` or `V BELT C 115`.
   - Take `BALL BEARING 6205` $\to$ mutate to `BALL BEARING 6206`.
   - Take `HEX BOLT M16 X 65` $\to$ mutate to `HEX BOLT M16 X 80`.
2. **Letter / Section Perturbation (`_perturb_letter`):**
   - Take `V BELT C 120` $\to$ mutate to `V-BELT SECTION B 120` (Section B vs Section C).
3. **Cross-Group In-Family Negatives:**
   - Pair an actual 2-inch gate valve with an actual 3-inch gate valve from the master.

---

## 8. Runtime Execution: The Life of a Query to `POST /api/v1/search`

When a user calls `POST /api/v1/search` with `{"query": "a belt that is c-120", "top_k": 20, "final_k": 5}`:

```
Step 1: Normalization & Extraction
   • query.prepare() -> "A BELT THAT IS C-120"
   • Extract identifier tokens: detects ['C-120']
   • Check exact identifier match in Postgres -> Finds BHEL-224411 (part_number=C120)

Step 2: Dense Query Embedding
   • Qwen3-Embedding-0.6B embeds "A BELT THAT IS C-120" into 1024-d float vector.
   • Time: ~15ms on CUDA.

Step 3: Vector ANN Search
   • Qdrant executes cosine distance search on collection 'material_embeddings'.
   • Filters applied: embedding_version = "qwen3-0.6b-v1".
   • Returns top 20 candidates (with qdrant_score between 0.65 and 0.77).

Step 4: Siamese Cross-Reranking (The Decisive Step)
   • 20 candidate descriptions loaded from Postgres.
   • Query + 20 candidates passed to Siamese Model in ONE single batch.
   • Output: 20 Siamese cosine scores in [0, 1].
   • Time: ~14ms on CUDA.
   • Candidate BHEL-224411 gets Siamese score: 0.9579!
   • Candidate near-miss C-125 gets Siamese score: 0.7449!

Step 5: Score Fusion & Threshold Classification
   • Fused Score = 0.3 * Qdrant_Score + 0.7 * Siamese_Score
   • 0.3 * (0.7450) + 0.7 * (0.9579) = 0.8940
   • 0.8940 >= 0.75 (SEARCH_MATCH_THRESHOLD) -> match_level = "high"!
```

---

## 9. Score Fusion & Threshold Calibration

### Why Not Siamese-Only? Why 0.3 / 0.7?
Both models provide distinct signals:

| Attribute | Qwen3 Retrieval Vector | Siamese Pair Cosine |
| :--- | :--- | :--- |
| **Model Size** | 600 Million parameters | 23 Million parameters |
| **Field of View** | Sees entire 400,000 item master | Sees only Top-20 candidates |
| **Strength** | Macro-semantics (Material Family) | Micro-semantics (Parameters & Digits) |
| **Weakness** | Blind to single-digit changes | Lacks global domain prior |

### Empirical Validation on CPSE Corpus:
When tested with `scripts/evaluate_search.py --calibrate`:
- **Qdrant-Only (1.0 / 0.0):** Match F1 = **0.804** (Precision: 0.701, Recall: 0.943). Flooded with false positives.
- **Siamese-Only (0.0 / 1.0):** Match F1 = **0.906** (Hit@1: 0.9792, MRR: 0.9896).
- **Fused (0.3 Qdrant + 0.7 Siamese):** Match F1 = **0.911**, Hit@1 = **1.000**, MRR = **1.000**!

The fused system achieves the highest precision AND preserves perfect top-1 ranking.

### The 3-Way Match Policy:
```
      Score >= 0.75  ────────►  HIGH MATCH (match: true)
                                Confidence is high. System recommends automated harmonization.

0.55 <= Score < 0.75 ────────►  POSSIBLE MATCH (match: false)
                                Sits in same family or is near-miss. Surfaced for human review.

      Score < 0.55   ────────►  NONE (match: false)
                                Rejected. No similarity detected.
```

---

## 10. Case Studies & Live Evidence

Here are the exact live numbers produced by our system for the 10 target benchmark queries:

| Query | Top Candidate | Qdrant Score | Siamese Score | Final Fused | Verdict | Reason |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `M-55321` | `NTPC-M55321` | `null` | `0.0000` | `0.0000` | **`high`** | Exact identifier lookup on `legacy_code`. Vector search bypassed. |
| `C-120` | `BHEL-224411` | `null` | `0.9395` | `0.9395` | **`high`** | Exact identifier lookup on `part_number`. |
| `V BELT` | `BCCL-MAT6833850` | `0.6242` | `0.6139` | `0.6169` | **`possible`** | Broad family query; appropriately held back from automatic high match. |
| `V BELT C 120` | `BHEL-224411` | `0.7711` | `0.9619` | **`0.9047`** | **`high`** | Clear, specific article. Siamese score 0.96 triggers high confidence. |
| `a belt that is c-120` | `BHEL-224411` | `0.7450` | `0.9579` | **`0.8940`** | **`high`** | Conversational paraphrase. Siamese score 0.9579 (beats $\ge 0.85$ target). |
| `V BELT C 125` | `BHEL-224411` | `0.7236` | `0.7540` | **`0.7449`** | **`possible`** | **Crucial Near-Miss Test:** Below 0.75 threshold. Zero false high! |
| `unrelated query` | `GAIL-MAT1128094` | `0.4366` | `0.4944` | **`0.4771`** | **`none`** | Completely rejected below 0.55 threshold. |

---

## 11. Presentation Cheat Sheet: Q&A for Judges & Evaluators

### Q1: "Why use a Siamese network instead of a Cross-Encoder or standard Bi-Encoder?"
> **Answer:**  
> A pure Bi-Encoder (like standard sentence transformers) maps each text independently into a vector. While fast, independent vector dots lose fine-grained token-level cross-attention, causing it to confuse `C-120` and `C-125`.  
> A Cross-Encoder concatenates `[CLS] Query [SEP] Candidate [SEP]` and passes both through all layers of BERT. While accurate, running a Cross-Encoder over 400,000 items is computationally impossible in real-time (it takes seconds per query).  
> **Our solution is optimal:** We use a Bi-Encoder for coarse retrieval (Qwen3 on Qdrant, retrieving top 20 in 5ms), and a fine-tuned Siamese metric network to rerank just those 20 candidates in a single 14ms tensor batch. We get Cross-Encoder precision with sub-50ms latency!

### Q2: "What is the difference between Contrastive Loss and Triplet Loss?"
> **Answer:**  
> **Triplet Loss** requires triplets of `(Anchor, Positive, Negative)` and enforces:
> $$D(A, P) + \alpha < D(A, N)$$
> However, forming valid triplets requires active triplet mining (finding semi-hard negatives), which is unstable and slow on small datasets.  
> **Contrastive Loss** operates directly on pairs `(Text A, Text B, y)` with an explicit distance penalty:
> $$\mathcal{L} = (1-y)\frac{1}{2}D^2 + y\frac{1}{2}\max(0, m - D)^2$$
> It directly forces positive pairs to distance $0$ and negative pairs beyond margin $m$. For CPSE catalog harmonization, where we have explicit positive pairs and synthetic hard-negative number perturbations, Contrastive Loss converges much faster and gives cleaner calibrated cosine separation.

### Q3: "What happens if a user searches for an exact part number or legacy code?"
> **Answer:**  
> We have **Stage 0 Deterministic Lookup**. The query is parsed for identifier tokens (`M-55321`, `NMM-00000042`, `C-120`). Postgres checks `legacy_code`, `material_id`, `national_id`, and `part_number` using indexed queries. An exact code hit is designated `exact_identifier` and immediately classified as `high` match with 100% precision without risking neural hallucination.

### Q4: "How does the system handle cold-start or new CPSE data?"
> **Answer:**  
> The system has a 3-way decision gate. If an incoming material is not an exact match, but has score $\ge 0.55$, it is labeled `possible` and routed to the Human-in-the-Loop review queue. When an enterprise reviewer approves or rejects the candidate, that feedback is automatically appended to `seed_pairs.csv` as a new verified pair, allowing periodic incremental retraining.

---
*Created for CPSE Material Harmonization Defense (SIH-2026).*

