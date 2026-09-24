# 04 · Retrieval & the Matcher Interface

> ## ⚠ Superseded — the matcher interface is gone; the retrieval half is not
>
> `ai-service` was restructured on 2026-09-10. Phase 1 (raw CSV/XLSX/TXT →
> the eight canonical CPSE attributes) now belongs to the fine-tuned
> **Qwen2.5-3B + `qwen2.5-3b-cpse-lora-v2`** extractor, vendored into
> `ai-service` from `backend/pipeline-one`. Everything downstream of the
> standard format is the **vector embedding DB**: check what is new, add only
> that.
>
> **Still true:** the vector store, Qdrant filtered ANN, the embedding-version guard and the payload projection (`app/logic/retrieval.py`) are unchanged, and the blocking keys are deliberately kept in the payload for the search that will use them.
> 
> **Removed:** `candidates.py` and the union retriever (fingerprint ∪ ANN ∪ trigram), and the matcher interface this document specifies. What the vector now answers is one question — *is this incoming row already in the index?* — in `app/logic/existence.py`.
>
> Current design: [`backend/ai-service/README.md`](../backend/ai-service/README.md)
> · API: [`AI_SERVICE_API_SPECIFICATION.md`](AI_SERVICE_API_SPECIFICATION.md)
>
> This document is kept for the design reasoning behind the removed stack,
> which is worth reading before search is built on top of the index. **It does
> not describe code that exists.**

---

> Scope: how the candidate set is narrowed, what the similarity score is and
> is not, and the exact seam where a trained model attaches.

---

## 1. Retrieval: what is built, and what it measurably buys

Candidate generation runs **three retrievers and unions them** (docs/05 §5.3),
on top of category blocking:

| Path | Finds | Implementation |
|---|---|---|
| **Category block** | Same-family candidates | `BlockOnlyRetriever` - exhaustive inside a category at this corpus size |
| **Exact fingerprint** | Identical identity attributes, different wording | `canonical_hash` equality, O(1) |
| **ANN** | Semantic neighbours *across* categories | `Qwen/Qwen3-Embedding-0.6B` (1024-d) → Qdrant filtered search |
| **Trigram** | Typos, terse codes, OEM part numbers | RapidFuzz `token_set_ratio` (production: `pg_trgm` GIN) |

The union is a **strict superset** of blocking - retrieval may only ever add
candidates, never remove one the old path found. That is asserted in
`test_union_is_a_superset_of_blocking` and re-checked by every ablation run.

### 1.1 What ANN is actually for here

Category blocking is already *exhaustive inside a category* on this corpus: 404
materials over 21 categories is ~19 comparisons per query. ANN therefore cannot
add anything **within** a block. Its job is the failure §2 names below:

> *"A material misclassified into the wrong family will never be compared
> against its true duplicate."*

So the ANN path deliberately does **not** filter by category - filtering on a
possibly-wrong category would remove the only thing it could find. It is
constrained by UOM dimension and embedding version only.

### 1.2 The measurement

`make ablation` runs the corpus through both retrievers and diffs the pairs.
Measured on the real model, not asserted:

```
corpus                404 materials, 21 categories
provider              Qwen/Qwen3-Embedding-0.6B (qwen3-0.6b-v1), 1024-d

candidates compared
  blocking only            9,356
  blocking + ANN + trgm   11,334   (1.21x)

pairs at NEAR_DUPLICATE or better
  blocking only            1,763
  with retrieval           1,763
  recovered                    0
  lost                         0
```

**ANN recovers nothing on this corpus today.** It surfaced ~2,000 extra
candidate pairs and the second stage correctly rejected every one of them - so
the vector path costs work and adds no recall at this scale, while introducing
no false positives either.

That is the honest finding, and it should be said plainly rather than implying
the embedding is doing work it is not. Two things follow:

1. **The earlier judgement in this document was right about the present.** At
   404 materials, category blocking is sufficient. The dependency does not pay
   for itself *yet*.
2. **It is wrong about the future, and the trigger is cheap to hold.** §7 lists
   the conditions under which blocking stops being sufficient. Having the
   retrieval layer built, behind an interface, with a measurement harness
   attached, means crossing that threshold is a config change and a reindex -
   not a redesign under time pressure.

The layer is therefore kept, `ANN_ENABLED` defaults on, and the ablation is the
artefact that keeps the claim honest as the corpus grows. If the number stays
zero, the number stays zero and we say so.

### 1.3 The boundary that does not move

Whatever retrieves, **the embedding never decides**:

```
    Embedding + Qdrant:  "Find materials that MIGHT be related."
    ── everything after this decides what the relationship IS ──
    compare → score → rules → verdict, on typed attributes
```

`test_retrieval_does_not_change_the_verdict` runs the same pair through both
retrievers and asserts an identical relationship and identical score. A
similarity number still cannot be defended to a materials engineer;
"`bearing_number` 6205 on both sides, no conflicts" still can.

### 1.4 Provider honesty

`EMBEDDING_PROVIDER=deterministic` is a seeded hash: the pipeline runs, tests
stay at ~3 seconds, and **retrieval is meaningless**. That is a legitimate dev
and CI mode and a dishonest demo mode, so `GET /api/v1/retrieval/model/info`
always reports `is_fallback`. A demo can never silently claim Qwen3 quality on
hash vectors.

---

## 2. Blocking

```python
def block(self, query, corpus):
    if query.category == UNCLASSIFIED:
        return [m for m in corpus if m.material_id != query.material_id]
    return [m for m in corpus
            if m.material_id != query.material_id and m.category == query.category]
```

Same category only. Complexity drops from O(N²) to O(N·k) where k is the mean
category size — on this corpus roughly 19.

An **unclassified** query blocks against nothing and is compared to the whole
corpus. That is the safe direction: rather than hiding a record because the
classifier abstained, it is compared widely, and the `CATEGORY` rule then caps it
at `NEAR_DUPLICATE` so it can never be declared an exact duplicate on the
strength of a category nobody could determine.

Blocking is a **recall boundary**. A material misclassified into the wrong family
will never be compared against its true duplicate. That is the single largest
source of missed matches in this design, and it is why classification abstains
instead of guessing, and why `category` misassignments are worth more review
attention than score tuning.

---

## 3. Comparison: the structure the score is computed from

`compare()` takes the union of attribute names on both sides and assigns each one
a state:

| Both present, equal | `MATCH` |
| Both present, different | `CONFLICT` |
| Present on one side only | `MISSING` |

Numeric attributes compare on `numeric_value` (so `3/4` equals `0.75`); everything
else compares on the normalised string.

Four derived signals come out of that:

```python
comparable         = len(matched) + len(conflicting)      # MISSING excluded
match_ratio        = len(matched) / comparable
identity_agreement = identity_matches / (identity_matches + identity_conflicts)
completeness       = comparable / len(attributes)
```

`MISSING` is deliberately absent from the numerator *and* denominator of
`match_ratio` and `identity_agreement`. It is not evidence for and not evidence
against; it only lowers `completeness`, which is a statement about how much was
knowable, not about how much agreed.

---

## 4. The score

```python
WEIGHTS = {
    "identity_agreement":   0.45,
    "attribute_match_ratio": 0.20,
    "completeness":         0.10,
    "category_match":       0.15,
    "lexical":              0.10,
}
```

Weighted sum, then **multiplicative** penalties:

```python
IDENTITY_CONFLICT_PENALTY      = 0.15   # ^ number of conflicts
DISCRIMINATING_CONFLICT_PENALTY = 0.75
MISSING_IDENTITY_PENALTY        = 0.80
```

Penalties multiply rather than subtract so that two identity conflicts are
0.15² = 0.0225 — an order of magnitude worse than one, which is the correct
shape. A subtractive penalty would floor at zero and lose that distinction.

### Why structure carries 0.90 and text 0.10

Two CPSEs describing the same bolt share almost no wording. `HEX BOLT M16X65
GR8.8` and `BOLT HEXAGONAL 16MM X 65MM GRADE 8.8` have low token overlap and are
the same article. Lexical similarity is therefore a **tie-breaker, not
evidence**.

The weighting was corrected during development for exactly this reason: at a
lexical weight of 0.25, verified duplicates scored 0.855 and fell short of the
0.90 exact threshold. Rebalancing to 0.90 structural / 0.10 lexical lets perfect
structural agreement reach the exact threshold on its own, which is the property
that matters.

The lexical component is RapidFuzz `token_set_ratio` over
`description_normalized` — order-insensitive and tolerant of the token soup in
procurement text.

### `Score` is self-describing

```python
Score(
    value=0.91,
    kind="heuristic_confidence",
    matcher_version="deterministic-v1",
    signals={"identity_agreement": 1.0, "attribute_match_ratio": 1.0, …},
    penalties=["missing_identity x1 (0.800) - evidence incomplete"],
)
```

`signals` and `penalties` are returned on `CandidateOut` and stored on
`match_result`, alongside the full `explanation` object, so any score can be
reconstructed by hand from the response. Contributions sum to the raw score,
which is asserted by `test_contributions_sum_to_the_weighted_score`.

---

## 5. What the score is not

`kind` says which of three numbers you are looking at, and it is stored beside
the value on `match_result` because they are three different claims:

| `kind` | Means | Produced by |
|---|---|---|
| `heuristic_confidence` | weighted structural agreement under weights a person chose | `DeterministicMatcher` |
| `learned_confidence` | logistic regression over the same signals | `LearnedFusionMatcher` |
| `calibrated_probability` | isotonic-mapped to empirical precision | `CalibratedMatcher` |

`make train` fits the latter two, and the engine falls back in that order when
`data/models` is empty. **The caveat that matters:** `pairs.csv` was derived from
the same attributes the matcher compares, so training on it produced a
cross-validated F1 of 1.000 — the model reproducing the heuristic, not beating
it. Those figures measure internal consistency, not accuracy, and the training
script prints that warning every run. Real supervision needs engineer-confirmed
pairs with hard negatives.

Anywhere the number is shown to a user, it should be shown with the reason
string, never alone.

---

## 6. The seam

```python
class Matcher(Protocol):
    version: str
    def score(
        self,
        left: StandardizedMaterial,
        right: StandardizedMaterial,
        comparison: ComparisonResult,
    ) -> Score: ...
```

`MatchingEngine(matcher=...)` accepts anything satisfying this. A trained
Siamese or CMRL model becomes:

```python
class LearnedMatcher:
    version = "siamese-v1"
    def score(self, left, right, comparison) -> Score:
        ...
        return Score(value=p, kind="calibrated_probability",
                     matcher_version=self.version, signals=..., penalties=[])
```

and `MatchingEngine(matcher=LearnedMatcher())` is the whole integration. What
does **not** change:

- The rule engine. Rules read `ComparisonResult`, not the score.
- The verdict logic. `_decide` consumes a `Score` and a `RuleVerdict`.
- Ranking, the API contract, the stored explanation format.
- `confidence_kind` distinguishes the two in the same table, so old and new rows
  remain interpretable side by side.

The engine passes the `ComparisonResult` into `score()` precisely so a learned
matcher can use the structural signals as features rather than re-deriving them
from raw text.

### What is needed before that is worth doing

A labelled corpus. Not the current `pairs.csv` — those labels were derived from
the same attributes the matcher compares, so training on them would teach a model
to reproduce the heuristic. Real supervision means **engineer-confirmed** pairs,
ideally a few thousand, including hard negatives: two bearings differing only in
seal type, two valves differing only in pressure class.

---

## 7. When vector retrieval starts earning its keep

The layer is built and measured (§1.2); today it recovers nothing, because
blocking on category is sufficient while categories stay small. It stops being
sufficient at either of:

| Trigger | Why | What to do |
|---|---|---|
| A single category exceeds ~5,000 members | O(k) inside the block becomes the bottleneck | Add a second blocking key (identity attribute, or CPSE), and let ANN retrieve *within* the block by adding `categories` to the `BlockingFilter` |
| Descriptions arrive that keyword rules cannot classify — other languages, transliteration, free-form vendor text | Classification abstains, blocking degrades to full scan, and recall depends on rules nobody can write fast enough | Already covered: Qwen3 is multilingual, and the ANN path is deliberately category-agnostic. Re-run `make ablation` — a non-zero *recovered* count is the signal it has begun to matter |

In both cases the embedding retrieves candidates and never decides. The
attribute comparison and the rule engine remain the authority — that boundary is
the one thing this design will not trade away.

Re-run `make ablation` whenever the corpus grows or the classifier changes. The
number in §1.2 is a measurement with a date on it, not a permanent claim.

---

**Next:** [05 · Matching & Rule Engine](05_MATCHING_AND_RULE_ENGINE.md)
