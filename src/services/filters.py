"""Filter application logic for school search queries.

This module previously contained a duplicate ``SchoolFilters`` dataclass and
``build_filter_clauses`` helper.  The canonical ``SchoolFilters`` lives in
:mod:`src.db.base`, and filtering is handled directly by each repository
implementation (e.g. :mod:`src.db.sqlite_repo`).

This file is kept as a placeholder to avoid breaking any existing imports
that reference the module.
"""
