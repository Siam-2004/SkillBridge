"""Negotiation room and the transition into a final agreement.

The invariant enforced throughout: at most one ``ACTIVE`` offer exists per
negotiation, and only its receiver may act on it.  Every state change goes
through ``_supersede`` so an old offer can never be left actionable.
"""

