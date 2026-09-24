"""STEP 3 - Database tables (SQLAlchemy).

One class per table. Importing this package registers every mapper, which is
what main.py needs before it can create the schema.

Four tables, and that is the whole schema:

    extraction_session        one run of Phase 1, awaiting review
    extraction_record         what the model said, and what a reviewer left
    abbreviation              CPSE taxonomy added at runtime
    standardization_batch     what Phase 1 offered and what was admitted
    material                  one standard-format row + its vector state
    national_id_counter       the one row that hands out national ids
    audit_log                 what changed the master, and who said so
    job                       background work that outlives its request

The first three are Phase 1 working state; nothing in them is part of the
master until POST /standardized/add accepts it.
"""

from app.models.extraction import Abbreviation, ExtractionRecord, ExtractionSession
from app.models.job import Job, JobKind, JobStatus
from app.models.material import AuditLog, Material, NationalIdCounter, PlantLocation
from app.models.standardized import StandardizationBatch

__all__ = [
    "Abbreviation",
    "AuditLog",
    "ExtractionRecord",
    "ExtractionSession",
    "Job",
    "JobKind",
    "JobStatus",
    "Material",
    "NationalIdCounter",
    "PlantLocation",
    "StandardizationBatch",
]
