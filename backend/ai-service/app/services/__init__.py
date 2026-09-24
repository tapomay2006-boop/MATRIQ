"""STEP 3 - Business logic.

Where the work happens: a service talks to the database through app/models/,
calls the algorithms in app/logic/, and returns a schema. Services know nothing
about HTTP - they return None instead of raising 404.

    extraction    the LoRA engine's lifecycle: raw text -> standard format
    standardized  the boundary: check what is new, add only that
    indexing      keep the vector index reconciled with Postgres
    materials     the read side of the master
    jobs          background work that outlives its request
"""
