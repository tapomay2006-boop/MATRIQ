# National Unified Material Master — Architecture

Smart India Hackathon 2026 · Problem Statement **26099**
_AI-Driven Standardization and Harmonization of Material Codes Across CPSEs_
Ministry of Petroleum & Natural Gas · Chennai Petroleum Corporation Limited (CPCL)

---

## What this directory is

The architecture set for the MVP. It describes **the system as built** and marks
clearly, section by section, where something is designed but not yet
implemented.

Read them in order; each one assumes the previous.

| #   | Document                                                                   | Covers                                                                                        | Status        |
| --- | -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | ------------- |
| 01  | [System Architecture](01_SYSTEM_ARCHITECTURE.md)                           | Actors, the end-to-end journey, request paths, topology, technology decisions                 | Mixed         |
| 02  | [Backend Architecture](02_BACKEND_ARCHITECTURE.md)                         | **`api-service`** — auth, RBAC, CPSE isolation, uploads, review workflow, national codes      | _Planned_     |
| 03  | [ML Architecture](03_ML_ARCHITECTURE.md)                                   | The seven-stage deterministic pipeline                                                        | **Superseded** |
| 04  | [Retrieval & the Matcher Interface](04_RETRIEVAL_AND_MATCHER_INTERFACE.md) | Blocking, Qwen3 embeddings + Qdrant ANN — retrieval still stands, the matcher half does not   | **Part superseded** |
| 05  | [Matching & Rule Engine](05_MATCHING_AND_RULE_ENGINE.md)                   | The five rules, the four-way verdict, fusion and calibration                                  | **Superseded** |
| 06  | [API Specification](06_API_SPECIFICATION.md)                               | Part A `api-service` _(planned)_ · Part B `ai-service` _(superseded)_                         | Mixed         |
| —   | [**AI Service API**](AI_SERVICE_API_SPECIFICATION.md)                      | **`ai-service` as it is today** — extraction, the boundary, the vector DB                     | **Built**     |
| 07  | [Deployment](07_DEPLOYMENT.md)                                             | Compose topology, configuration, operations, scale triggers                                   | **Built**     |
| 08  | [Development Progress](08_DEVELOPMENT_PROGRESS.md)                         | Frontend modernization, live AI integration, DB decoupling & Neon Postgres                    | **Built**     |

---

## ⚠ Read this first

`ai-service` was restructured on **2026-09-10/11**, and docs 03–05 describe
code that has been deleted. The architecture as built is:

```
   Raw CSV/XLSX/TXT
          │
          ▼
   [ Qwen2.5-3B + qwen2.5-3b-cpse-lora-v2 ]      Phase 1, a pollable job
          │
          ▼
   Standard Format · 8 canonical CPSE attributes
          │
          ▼
   Is this row already in the vector embedding DB?
          │
   ┌──────┴──────┐
already there   new material
   │              │
ignored     Postgres + Qdrant, one transaction
```

Phase 1 — turning a raw catalogue into the eight canonical attributes — is the
fine-tuned extractor, vendored into `ai-service` from `backend/pipeline-one`.
Everything downstream of the standard format is the vector embedding DB. The
deterministic seven-stage pipeline, the matcher, the rule engine and the
national-code workflow have been **removed**; search over the index is not
built yet.

**Authoritative for what exists today:**
[`backend/ai-service/README.md`](../backend/ai-service/README.md) — the
architecture and its trade-offs · [`AI_SERVICE_API_SPECIFICATION.md`](AI_SERVICE_API_SPECIFICATION.md)
— all 22 endpoints.

Docs 03–05 are kept for the design reasoning behind the removed stack, each
with a banner saying so. Worth reading before search is built on top of the
index; not a description of code that exists.

Doc 07 describes working, tested code. Doc 02 and Part A of doc 06 are
specifications to build against. Docs 03–05 are history.

---

## The two services

```
browser ──► api-service :8000 ──► ai-service :8001 ──► Postgres
            doc 02, planned       docs 03·04·05, built         │
                                          │                     └─ source of truth
            auth · RBAC           standardization               │
            CPSE isolation        attribute extraction          ▼
            uploads               classification            Qdrant :6333
            review workflow       embedding + ANN retrieval  derived index,
            national codes        matching + rules           rebuildable
            audit                 evaluation
```

`api-service` is the only client of `ai-service`, which is why the ML service
carries no user model of its own and must never be published directly. Where
`ai-service` itself authenticates nobody: every endpoint is open to any caller
that can reach the port, so the network is the only boundary. Never expose
`:8001` publicly.

Postgres is the source of truth. Qdrant holds only vectors, every one of which
is reproducible from `canonical_text` — losing it is a job to re-run, not an
incident.

---

## The architecture in one paragraph

Material extracts arrive from several CPSEs and are normalised into a
**standardized representation**: a cleaned canonical text plus a set of **typed
technical attributes**, each carrying a **role** — identity-defining,
discriminating, or descriptive. Comparison is confined to materials in the same
category, so the corpus is scanned in O(N·k) rather than O(N²). Every candidate
pair produces a per-attribute comparison whose states are `MATCH`, `CONFLICT`
and `MISSING`; a deterministic scorer turns that structure into a confidence
value, and a rule engine holds veto authority over it. The result is one of four
verdicts with a stored, human-readable explanation, routed to a human reviewer.
An approved group receives a national material code while every CPSE's original
code is preserved forever in an append-only mapping. Every raw field survives
verbatim, and every data-quality problem is flagged rather than silently
corrected.

---

## The five commitments every document must respect

1. **Structure proposes, rules dispose.** No equivalence decision may rest on a
   similarity number alone. See [05](05_MATCHING_AND_RULE_ENGINE.md).
2. **MISSING is not DIFFERENT.** An absent attribute lowers confidence and
   blocks an exact-duplicate verdict; it is never a conflict.
   See [03 §9](03_ML_ARCHITECTURE.md), [05](05_MATCHING_AND_RULE_ENGINE.md).
3. **Raw values are never overwritten.** Standardization is additive; every
   correction is a flag next to the original. Legacy codes are never replaced —
   the national code is additive too. See [03 §12](03_ML_ARCHITECTURE.md),
   [02 §5](02_BACKEND_ARCHITECTURE.md).
4. **Every derived row is versioned and explained.** Eight version stamps —
   pipeline, tokenizer, dictionary, taxonomy, rule, matcher, embedding model and
   embedding version — travel with every decision, alongside the stored
   explanation object. See [03 §18](03_ML_ARCHITECTURE.md).
5. **Nothing claims more certainty than the data supports.** Every score carries
   a `confidence_kind` — `heuristic_confidence`, `learned_confidence` or
   `calibrated_probability` — because those are three different claims. The
   models that produce the latter two are fitted on labels derived from the same
   attributes the matcher compares, so their headline figures measure internal
   consistency, not accuracy, and every document says so.
   See [04 §5](04_RETRIEVAL_AND_MATCHER_INTERFACE.md).

---

## What is built, and what is not

|                                                                             | Status                                                                |
| --------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| S1–S7 pipeline — clean, tokenize, expand, UOM, extract, classify, canonical | **Built**, 404/404 rows classified                                    |
| Ingest by reference — per-CPSE merge, row quarantine, import jobs           | **Built** (ai-service half; the api-service upload endpoint is not)   |
| Attribute validation, `INFERRED` derivation, `AttributeStatus`              | **Built**, six validation rules                                       |
| Blocking, comparison, scoring, rules, four-way verdict                      | **Built**                                                             |
| Qwen3-Embedding-0.6B + Qdrant filtered ANN, union recall                    | **Built**, and measured — see below                                   |
| Classifier tiers 2–3 (linear head + zero-shot descriptors)                  | **Built**                                                             |
| spaCy NER (extraction step 4)                                               | **Built**, held-out span F1 0.749                                     |
| Learned fusion weights + isotonic calibration                               | **Built**, on circular labels                                         |
| Stored explanation object, signals and penalties persisted                  | **Built**                                                             |
| Internal-key auth on `ai-service`                                           | **Built**, off by default                                             |
| LLM fallback (extraction step 5)                                            | **Built**, flag-off by default, as the design requires                |
| Data-quality flagging with raw-value preservation                           | **Built**                                                             |
| Gold-label set + evaluation report                                          | **Built**, pending domain-expert review                               |
| Auth, RBAC (4 roles), CPSE isolation                                        | **Built** in `ai-service` (`auth.py`); `api-service` gateway planned  |
| Upload preview/confirm, review workflow, national code issuance             | **Built** in `ai-service` (31 endpoints); `api-service` proxy planned |
| Review UI                                                                   | **Not built** — Next.js scaffold only                                 |

**141 tests**, plus 10 Qdrant integration tests that skip unless a server is up.

### Measured on this corpus

| | |
| :--- | :--- |
| Category coverage | **404/404** classified by the keyword table; 0 abstentions |
| Duplicate check | exact signals (material id, canonical hash) decide most re-uploads without the vector being consulted at all |
| Embedded attributes | **5 of 8** — company, legacy code and quantity are excluded so the same article in two CPSEs embeds identically |

The three capabilities this section used to list — ANN ablation, classifier
tiers 2–3, spaCy NER — belonged to the removed pipeline and no longer exist.
