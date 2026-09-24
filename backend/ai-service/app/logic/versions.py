"""Single source of every version stamp.

Three stamps travel with a material and are persisted on it, so the platform
can answer, later: which model read this text, what string was embedded, and
under which identity scheme was its id derived.

Bump a stamp whenever the behaviour it names changes. A stamp that lies is
worse than no stamp: it makes a past decision look reproducible when it is not.
"""

from __future__ import annotations

#: The path from raw text to standard format. v3 is the fine-tuned
#: qwen2.5-3b-cpse-lora-v2 adapter. v2 was the deterministic chain that used to
#: live in ai-service (clean -> tokenize -> expand -> extract -> classify ->
#: canonical); it is gone, and a row carrying that stamp was produced by code
#: this service no longer contains.
PIPELINE_VERSION = "pipeline-v3-lora"

#: The abbreviation taxonomy in data/config/abbreviations.csv, which the
#: extraction engine expands against. Bump it when the table changes enough to
#: alter what a description normalises to.
DICTIONARY_VERSION = "dict-v1"

#: How material_id is derived. v1 was row-position based; v2 is the CPSE's own
#: code. A corpus built under a different scheme has DIFFERENT ids for the same
#: materials, so anything stored has to say which one it was made under.
IDENTITY_SCHEME_VERSION = "identity-v2"
