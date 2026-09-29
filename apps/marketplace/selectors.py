"""Job search and filtering.

Search runs entirely through the Django ORM against a denormalised
``search_text`` column, so it behaves identically on every machine and needs no
search server. Ranking floats title matches above body matches.
"""


