"""Domain exceptions.

Services raise these instead of returning error strings, so a view, a DRF
endpoint, a Celery task and a management command all get the same failure
semantics. ``DomainError`` carries a user-safe message; internals stay in logs.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for every expected, user-visible business failure."""

    status_code = 400
    default_message = "That action could not be completed."

    def __init__(self, message: str | None = None, *, code: str = "", **context):
        self.message = message or self.default_message
        self.code = code or self.__class__.__name__
        self.context = context
        super().__init__(self.message)


class PermissionDenied(DomainError):
    status_code = 403
    default_message = "You do not have permission to perform this action."


class NotVerified(DomainError):
    status_code = 403
    default_message = "Verify your email address before using this feature."


class InvalidState(DomainError):
    """A state-machine transition that the spec does not allow."""

    default_message = "This item is not in a state that allows that action."


class ValidationFailed(DomainError):
    default_message = "Please correct the highlighted fields."

    def __init__(self, message=None, *, errors: dict | None = None, **kwargs):
        super().__init__(message, **kwargs)
        self.errors = errors or {}


# --------------------------------------------------------------------------- #
# Financial failures — deliberately distinct so the money path can be audited
# and alerted on separately from ordinary validation noise.
# --------------------------------------------------------------------------- #
class FinancialError(DomainError):
    default_message = "This financial operation could not be completed."


class InsufficientFunds(FinancialError):
    default_message = "Insufficient available SkillCoin balance."

    def __init__(self, message=None, *, required=None, available=None, **kwargs):
        self.required = required
        self.available = available
        if message is None and required is not None and available is not None:
            message = (
                f"Insufficient balance: {required:,.2f} SKC required, "
                f"{available:,.2f} SKC available."
            )
        super().__init__(message, **kwargs)


class AllocationMismatch(FinancialError):
    """SUM(task allocations) != escrow amount."""

    default_message = "Task allocations must add up to exactly the escrow amount."


class DuplicateTransaction(FinancialError):
    default_message = "That external transaction ID has already been submitted."


class EscrowLocked(FinancialError):
    default_message = "These escrow funds are locked and cannot be moved right now."
