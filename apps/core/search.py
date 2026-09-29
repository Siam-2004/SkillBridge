from __future__ import annotations
import re
from django.db.models import Case, IntegerField, Q, Value, When
_WHITESPACE = re.compile('\\s+')

def build_search_text(*parts) -> str:
    chunks = []
    for part in parts:
        if not part:
            continue
        if isinstance(part, (list, tuple, set)):
            chunks.extend((str(p) for p in part if p))
        else:
            chunks.append(str(part))
    return _WHITESPACE.sub(' ', ' '.join(chunks)).strip().lower()[:4000]

def terms(keyword: str) -> list[str]:
    words = [w for w in re.split('[^\\w]+', (keyword or '').lower()) if len(w) > 1]
    return sorted(set(words), key=len, reverse=True)[:8]

def text_filter(keyword: str, *fields: str) -> Q:
    query = Q()
    for term in terms(keyword):
        clause = Q()
        for field in fields:
            clause |= Q(**{f'{field}__icontains': term})
        query &= clause
    return query

def relevance(keyword: str, primary: str='title'):
    word = (keyword or '').strip()
    if not word:
        return Value(0, output_field=IntegerField())
    return Case(When(**{f'{primary}__iexact': word}, then=Value(3)), When(**{f'{primary}__icontains': word}, then=Value(2)), default=Value(1), output_field=IntegerField())
