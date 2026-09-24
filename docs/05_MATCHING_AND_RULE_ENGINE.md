# 05 · Matching & Rule Engine

> ## ⚠ Superseded — the matching and rule engine has been removed entirely
>
> `ai-service` was restructured on 2026-09-10. Phase 1 (raw CSV/XLSX/TXT →
> the eight canonical CPSE attributes) now belongs to the fine-tuned
> **Qwen2.5-3B + `qwen2.5-3b-cpse-lora-v2`** extractor, vendored into
> `ai-service` from `backend/pipeline-one`. Everything downstream of the
> standard format is the **vector embedding DB**: check what is new, add only
> that.
>
> **Removed:** `compare.py`, `score.py`, `fusion.py`, `calibration.py`, `rules.py`, `matcher.py`, `explain.py`, `metrics.py`, `ground_truth.py`, `lifecycle.py`, the four-way relationship verdict, the five hard rules, and the `match_result` / `review` / national-code tables.
> 
> There is no relationship verdict in `ai-service` today. The only decision it makes is whether an incoming row is worth embedding, and that rule is 40 lines in `app/logic/existence.py`.
>
> Current design: [`backend/ai-service/README.md`](../backend/ai-service/README.md)
> · API: [`AI_SERVICE_API_SPECIFICATION.md`](AI_SERVICE_API_SPECIFICATION.md)
>
> This document is kept for the design reasoning behind the removed stack,
> which is worth reading before search is built on top of the index. **It does
> not describe code that exists.**

---

> Scope: how a score plus a set of rules becomes one of four verdicts, and how
> that verdict is defended to a materials engineer.

---

## 1. The four verdicts

| Verdict | Claim | Action |
|---|---|---|
| `EXACT_DUPLICATE` | Same article. Every comparable attribute agrees, nothing is missing, no rule objected. | Merge candidate |
| `NEAR_DUPLICATE` | Probably the same article, but the evidence is incomplete. | Human confirms |
| `FUNCTIONALLY_EQUIVALENT` | **Different** articles that can substitute for each other. | Engineer decides |
| `NOT_EQUIVALENT` | Different articles. | Reject |

`FUNCTIONALLY_EQUIVALENT` is the one that gets misused. It is a *positive claim*
about interchangeability, not a resting place for pairs that scored in the
middle. §6 shows the guard that enforces this.

```python
RELATIONSHIP_RANK = {
    NOT_EQUIVALENT: 0,
    FUNCTIONALLY_EQUIVALENT: 1,
    NEAR_DUPLICATE: 2,
    EXACT_DUPLICATE: 3,
}
```

The rank exists so `cap_relationship` can only ever move a verdict **down**:

```python
def cap_relationship(proposed, ceiling):
    if ceiling is None:
        return proposed
    return proposed if RELATIONSHIP_RANK[proposed] <= RELATIONSHIP_RANK[ceiling] else ceiling
```

No rule anywhere can raise a verdict. That asymmetry is the safety property of
the whole engine.

---

## 2. The pipeline for one pair

```
compare(left, right)              → ComparisonResult
matcher.score(left, right, cmp)   → Score
rules.evaluate(cat_l, cat_r, cmp) → RuleVerdict
_decide(score, rules, cmp, shared_missing) → (final, proposed, reason)
```

`rules.evaluate` never sees the score. Rules read structure only, so a rule can
never be argued out of its objection by a high similarity number.

---

## 3. Score → proposal

```python
def _propose(score):
    if score >= 0.90: return EXACT_DUPLICATE
    if score >= 0.72: return NEAR_DUPLICATE
    if score >= 0.55: return FUNCTIONALLY_EQUIVALENT
    return NOT_EQUIVALENT
```

Thresholds live in settings. This is the **only** place the score influences the
verdict. Everything after it can lower the result.

---

## 4. The five rules

Each returns a `RuleOutcome(rule, status, detail, ceiling, advisory)`.

### `CATEGORY`

| Condition | Status | Ceiling |
|---|---|---|
| Either side `UNCLASSIFIED` | `REVIEW` | `NEAR_DUPLICATE` |
| Categories differ | `REJECT` | `NOT_EQUIVALENT` |
| Same category | `PASS` | — |

A pair that survived blocking can still differ in category when the query was
unclassified and compared against everything.

### `IDENTITY_CONFLICT`

Any `IDENTITY_DEFINING` attribute with different values on both sides →
`REJECT`, ceiling `NOT_EQUIVALENT`.

This is the rule that makes the system defensible. Two valves at 0.94 textual
similarity whose `nominal_size` is 50 mm and 80 mm are rejected outright, and the
detail names both values:

```
Identity-defining conflict (nominal_size: 50 vs 80).
```

### `IDENTITY_EVIDENCE`

An `IDENTITY_DEFINING` attribute stated on one side only → `REVIEW`, ceiling
`NEAR_DUPLICATE`. The detail says so explicitly:

```
Identity attribute(s) not stated on one side: grade.
Missing is not treated as a conflict.
```

A bolt whose grade is simply unstated is a near duplicate awaiting confirmation,
not a rejection. Getting this wrong would reject most of the corpus, because most
of the corpus is incomplete.

### `DISCRIMINATING`

A `DISCRIMINATING` attribute conflict → `REVIEW`, ceiling
`FUNCTIONALLY_EQUIVALENT`. Two bearings identical but for `seal_type` are not the
same part and are plausibly interchangeable — exactly the case an engineer should
see:

```
Discriminating conflict (seal_type: 2RS vs ZZ). Needs engineer sign-off.
```

### `UOM` — advisory only

```python
RuleOutcome("UOM", RuleStatus.REVIEW,
            "Units of measure differ. Advisory: verify the issue unit.",
            advisory=True)
```

This is the most consequential decision in the file, and it is a concession to
the data. In `CPSE_SIH26099.csv` the UOM column is randomised: one bearing
appears with **eight different units**, and 286 of 404 rows carry a
`UOM_MISMATCH` flag. If UOM could veto, nearly every true duplicate would be
rejected.

So the mismatch is reported, stored and shown — and never allowed to change a
verdict.

### Advisory vs binding

```python
@property
def binding(self):
    return [o for o in self.outcomes if not o.advisory]
```

`status`, `ceiling` and `reason` are all computed over `binding` only.
`triggered` and `advisories` include everything, so the advisory finding still
reaches the reviewer.

This distinction was added after a real defect: the stored `reason` on a
downgraded pair cited the UOM advisory rather than the identity conflict that
actually caused the downgrade. `reason` now returns the **first binding
non-`PASS`** outcome — the finding that changed the verdict, not merely the first
one in the list.

---

## 5. `RuleVerdict`

```python
status    REJECT if any binding REJECT, else REVIEW if any binding REVIEW, else PASS
ceiling   the LOWEST binding ceiling (min by rank) — the strictest objection wins
rejected  status is REJECT
reason    detail of the first binding non-PASS outcome
triggered every non-PASS outcome, advisories included
advisories details of non-PASS advisory outcomes
```

---

## 6. `_decide` — the verdict

```python
proposed = _propose(score.value)

if rules.rejected:
    return NOT_EQUIVALENT, proposed, rules.reason

final = cap_relationship(proposed, rules.ceiling)
```

Then two guards that no threshold can override.

### Guard 1 — an exact duplicate requires complete evidence

```python
if final is EXACT_DUPLICATE and (
    comparison.identity_conflicts
    or comparison.identity_missing
    or schema_missing
):
    final = NEAR_DUPLICATE
```

`schema_missing` is the set of identity attributes the **category schema expects
that neither record states**. The comparison cannot see those — it works from the
union of attributes actually present, so an attribute absent on both sides simply
does not appear.

That was a real defect. Two records that both failed to state `grade` compared as
perfectly agreeing and reached `EXACT_DUPLICATE` on evidence neither of them
supplied. The engine now computes:

```python
shared_missing = tuple(sorted(set(query.missing_identity) & set(other.missing_identity)))
```

and passes it in. Absence of evidence on both sides is not evidence of identity.

### Guard 2 — functional equivalence must be claimed, not defaulted into

```python
if final is FUNCTIONALLY_EQUIVALENT and not any(
    o.ceiling is FUNCTIONALLY_EQUIVALENT for o in rules.outcomes
):
    final = NEAR_DUPLICATE if not comparison.conflicting else NOT_EQUIVALENT
```

A score of 0.60 with thin evidence lands in the functional band by arithmetic
accident. But "these two different articles can substitute for each other" is a
positive engineering claim, and only the `DISCRIMINATING` rule is entitled to
make it. Without that rule having fired, the pair is a weak near-duplicate (no
conflicts) or simply not equivalent (conflicts present).

This is why `FUNCTIONALLY_EQUIVALENT` is rare — 10 pairs out of ~3,000 on the
full corpus. That is the intended shape.

### The reason string

```
capped   "Capped from EXACT_DUPLICATE: Identity attribute(s) not stated on one side: grade."
exact    "All 4 comparable attributes agree, no conflicts, no missing identity evidence."
near     "No conflicts, but seal_type not stated on one side."
near     "No conflicts, but neither record states grade, which the category treats
          as identity-defining."
not      "Identity-defining conflict (nominal_size: 50 vs 80)."
```

Every stored match has one. It names the specific attribute and both values.

---

## 7. Ranking

```python
candidates.sort(
    key=lambda c: (RELATIONSHIP_RANK[c.relationship], c.score.value), reverse=True
)
```

Relationship first, score second. A `NOT_EQUIVALENT` pair that scored 0.88 before
rules must never outrank a genuine `NEAR_DUPLICATE` at 0.75 — the rules already
decided, and ranking is not permitted to relitigate it.

---

## 8. Clustering

`engine.cluster(corpus, min_relationship=...)` is union-find over every pair at
or above the given relationship, returning connected components of size > 1.
Path compression on `find`.

Clustering is intentionally kept off the main matching path. Transitivity is not
guaranteed — A≈B and B≈C does not make A≈C when the near-duplicate reason
differs on each edge — so a cluster is a **review grouping**, not a merge
instruction.

---

## 9. Worked examples

All three are real output from the current corpus.

### Rejected on identity, three ways at once

```
IOCL-000017  high tensile bolt m24 x 100mm grade 8.8 galvanized (REQ AS PER ATTACHED SPEC)
BHEL-000068  m.s. hex bolt & nut m16x65mm long is:1363

signals            identity_agreement 0.000  match_ratio 0.000
                   completeness 0.429  category_match 1.0  lexical 0.369
penalties          identity_conflict x3 (0.003)
                   missing_identity x1 (0.800)
score              0.0006
rules              IDENTITY_CONFLICT, IDENTITY_EVIDENCE, UOM → REJECT
proposed_before    NOT_EQUIVALENT
final              NOT_EQUIVALENT
reason             Identity-defining conflict (length: 100 vs 65;
                   material: HIGH TENSILE vs MILD STEEL; thread_size: 24 vs 16).
```

Three identity conflicts compound to 0.15³ ≈ 0.003. Both are hex bolts in the
same category with 0.37 lexical overlap — and the rule would have rejected the
pair at any score.

### A perfect score downgraded by absent evidence

```
IOCL-000017  high tensile bolt m24 x 100mm grade 8.8 galvanized (REQ AS PER ATTACHED SPEC)
CCL-000036   high tensile bolt m24 x 100mm grade 8.8 galvanized (** OEM ONLY **)

matched            finish, length, material, property_class, thread_size
conflicting        none
score              1.0
proposed_before    EXACT_DUPLICATE
rules              UOM (advisory only) — binding status PASS
final              NEAR_DUPLICATE
reason             No conflicts, but neither record states head_type, which the
                   category treats as identity-defining.
```

Two descriptions identical but for the procurement noise, five attributes
agreeing, a score of exactly 1.0 — and still not an exact duplicate, because
`FASTENER` treats `head_type` as identity-defining and **neither** record states
it. This is Guard 1 doing the only job it has. No threshold can override it.

### A discriminating conflict, and UOM overruled

```
CCL-000002   BEARING, BALL, 6205-2RS1
NTPC-000258  BEARING BALL RADIAL 6205 2RS SKF/FAG MAKE ONLY (** OEM ONLY **)

matched            bearing_number, bearing_type
conflicting        seal_type: 2RS1 vs 2RS
score              0.6779
rules              DISCRIMINATING → REVIEW, ceiling FUNCTIONALLY_EQUIVALENT
                   UOM → REVIEW (advisory)
final              FUNCTIONALLY_EQUIVALENT
reason             Discriminating conflict (seal_type: 2RS1 vs 2RS).
                   Needs engineer sign-off.
advisories         Units of measure differ. Advisory: verify the issue unit.
```

The `DISCRIMINATING` rule fired, so Guard 2 permits the functional verdict —
this is a genuine interchangeability question for an engineer, not an arithmetic
accident. The UOM finding is reported and ignored; the material's `uom_raw` is
unchanged.

---

## 10. Evaluation

`app/logic/ground_truth.py` builds a 60-pair gold set from five construction rules,
interleaved by label so no class dominates, and scores the engine against it:
precision, recall and F1 per relationship, plus overall accuracy.
`NEEDS_EXPERT_REVIEW` pairs are **excluded** rather than guessed.

Current result: **58 evaluated, 2 skipped, accuracy 1.000**.

**That number is circular and must be reported as such.** The gold labels were
derived from the same attributes the matcher compares, so the engine is being
scored against a restatement of its own inputs. It demonstrates internal
consistency — the rules do what they say — and nothing about real-world accuracy.

The `EvaluationResponse` carries a `caveat` field saying exactly this, so the
number cannot be quoted without it.

It becomes a real measurement when a domain expert reviews and corrects
`data/ground_truth/pairs.csv`. That review, together with the 60 role assignments
in `category_attributes.csv`, is the highest-value expert input this system can
receive.

---

## 11. Known limits

| Limit | Consequence |
|---|---|
| Blocking is single-key | A misclassified material never meets its true duplicate |
| Extraction is regex | An attribute phrased unusually reads as `MISSING`, capping the pair at `NEAR_DUPLICATE` |
| Roles are hand-assigned | A wrong role silently changes every verdict in that category |
| Weights are chosen, not fitted | Defensible, auditable, and untested against ground truth |
| Clustering assumes transitivity | Treated as a review grouping only, never an automatic merge |

---

**Next:** [06 · API Specification](06_API_SPECIFICATION.md)
