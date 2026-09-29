"""Negotiation room.

Deliberately separate from messaging: a chat message is prose, an ``Offer`` is a
structured, acceptable set of terms.  Only the *current* offer can be acted on,
and only by its receiver, which is enforced by ``Negotiation.current_offer``
plus the service layer.
"""

