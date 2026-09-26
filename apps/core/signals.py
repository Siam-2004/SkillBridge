"""Signal wiring for the core app.

Currently only a placeholder import target: the SQLite pragmas are attached in
``apps.py`` because they must be connected before the first query, and the
per-app signals live with their own apps.
"""
