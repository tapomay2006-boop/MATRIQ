"""The algorithms - plain Python, no HTTP and no database.

Services call these. Because nothing here touches a request or a session, every
file is directly unit-testable.

    extraction  -> standard_format -> standardize      raw text to a stored row
    embedding   -> retrieval                           that row to a vector
    existence                                          is this row already here?

`extraction.py` is vendored from backend/pipeline-one; `identity.py` derives
the material id; `versions.py` holds the stamps that travel with a row.

pipeline-one's `session_store.py` is deliberately NOT vendored: review sessions
are rows in Postgres here (models/extraction.py, services/sessions.py), because
a process-local dict listed nothing after a restart and was invisible to a
second worker.
"""
