"""Search helpers that work on SQLite.

There is no search engine and no database-specific full-text extension. Each
searchable model keeps a denormalised ``search_text`` column holding everything
worth matching on, refreshed whenever the record changes. A query is then one
``icontains`` against that column instead of six ``OR``s across joined tables.

Ranking is deliberately simple: a hit in the title outranks a hit in the body.
That is enough for a marketplace of this size, and it behaves identically on
every machine the project runs on.
"""

from __future__ import annotations

import re

from django.db.models import Case, IntegerField, Q, Value, When

_WHITESPACE = re.compile(r"\s+")


def build_search_text(*parts) -> str:
    """Join everything searchable about a record into one lowercase blob."""
    chunks = []
    for part in parts:
        if not part:
            continue
        if isinstance(part, (list, tuple, set)):
            chunks.extend(str(p) for p in part if p)
        else:
            chunks.append(str(part))
    return _WHITESPACE.sub(" ", " ".join(chunks)).strip().lower()[:4000]


def terms(keyword: str) -> list[str]:
    """Split a query into the words worth matching, longest first."""
    words = [w for w in re.split(r"[^\w]+", (keyword or "").lower()) if len(w) > 1]
    return sorted(set(words), key=len, reverse=True)[:8]


def text_filter(keyword: str, *fields: str) -> Q:
    """Match every term of ``keyword`` in any one of ``fields``.

    Terms are ANDed and fields are ORed, so "django dashboard" finds records
    mentioning both words somewhere, which is what a person typing two words
    means.
    """
    query = Q()
    for term in terms(keyword):
        clause = Q()
        for field in fields:
            clause |= Q(**{f"{field}__icontains": term})
        query &= clause
    return query


def relevance(keyword: str, primary: str = "title"):
    """Annotation that floats exact and primary-field matches to the top."""
    word = (keyword or "").strip()
    if not word:
        return Value(0, output_field=IntegerField())
    return Case(
        When(**{f"{primary}__iexact": word}, then=Value(3)),
        When(**{f"{primary}__icontains": word}, then=Value(2)),
        default=Value(1),
        output_field=IntegerField(),
    )
