"""Escrow: funding it, splitting it, and paying it out.

This module owns the escrow *row*; the coins themselves are moved by
``wallets.ledger``. Every function that changes an escrow balance keeps the
``escrow_balances_reconcile`` constraint true — held + released + refunded
equals funded — so the database rejects any arithmetic slip.

The rule that shapes the release functions: when a project's money is already
in escrow, paying a task must not touch the client's available balance again.
``release_task_payment`` therefore only ever moves escrow → freelancer, and the
client's spendable balance is not even a parameter.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

import logging

from django.conf import settings

from apps.agreements.models import Agreement
from apps.audit.models import AuditLog
from apps.audit.services import record_audit
from apps.core.models import ActivityVerb
from apps.core.services import record_activity
from apps.core.exceptions import (
    AllocationMismatch,
    EscrowLocked,
    InsufficientFunds,
    InvalidState,
    PermissionDenied,
    ValidationFailed,
)
from apps.core.money import ZERO, positive_coin, to_coin
from apps.core.permissions import require_admin, require_verified_client
from apps.escrow.models import Escrow, EscrowAllocation
from apps.notifications.models import NotificationType
from apps.notifications.services import notify
from apps.wallets import ledger

logger = logging.getLogger("skillbridge.money")


def _project_url(project) -> str:
    return f"/projects/{project.public_id}/"


@transaction.atomic()
def fund_project(*, agreement: Agreement, client):
    """Move the agreed amount into escrow and open the project.

    The coins are already *reserved* against the job, so this is a
    reserved → escrow move.  If the agreement grew during negotiation beyond
    what is reserved, the remainder is taken from available — and if that is
    short, funding is refused rather than partially applied.
    """
    require_verified_client(client)
    agreement = Agreement.objects.select_for_update().get(pk=agreement.pk)

    if agreement.client_id != client.pk:
        raise PermissionDenied("Only the client on this agreement can fund it.")
    if not agreement.is_accepted:
        raise InvalidState("The agreement must be accepted before funding.")
    if Escrow.objects.filter(agreement=agreement).exists():
        raise InvalidState("This agreement is already funded.")

    from apps.marketplace.models import Job
    from apps.projects.models import Project

    job = Job.objects.select_for_update().get(pk=agreement.job_id)
    amount = positive_coin(agreement.final_amount)

    wallet = ledger.lock_wallet(client)
    from_reserved = min(job.reserved_amount, amount)
    from_available = amount - from_reserved
    if from_available > ZERO and wallet.available_balance < from_available:
        raise InsufficientFunds(
            f"Funding needs {amount:,.2f} SKC. {from_reserved:,.2f} SKC is reserved "
            f"for this job and {from_available:,.2f} SKC more is required, but only "
            f"{wallet.available_balance:,.2f} SKC is available.",
            required=from_available,
            available=wallet.available_balance,
        )

    project = Project.objects.create(
        job=job,
        agreement=agreement,
        client=client,
        freelancer=agreement.freelancer,
        title=job.title,
        description=job.description,
        final_price=amount,
        deadline=agreement.deadline,
        status=Project.Status.ACTIVE,
    )

    hold_txn = None
    if from_reserved > ZERO:
        hold_txn = ledger.hold_escrow(
            user=client,
            amount=from_reserved,
            project=project,
            job=job,
            actor=client,
            wallet=wallet,
        )
    if from_available > ZERO:
        top_up = ledger.hold_escrow_from_available(
            user=client,
            amount=from_available,
            project=project,
            job=job,
            actor=client,
            wallet=wallet,
        )
        hold_txn = hold_txn or top_up

    job.reserved_amount = job.reserved_amount - from_reserved
    job.status = Job.Status.IN_PROGRESS
    job.save(update_fields=["reserved_amount", "status", "updated_at"])

    escrow = Escrow.objects.create(
        project=project,
        client=client,
        agreement=agreement,
        funded_amount=amount,
        held_amount=amount,
        released_amount=ZERO,
        refunded_amount=ZERO,
        status=Escrow.Status.ACTIVE,
        hold_transaction=hold_txn,
    )

    # Open the project conversation so client, owner and members share one room.
    from apps.messaging.services import open_project_conversation

    open_project_conversation(project=project, actor=client)

    record_activity(
        ActivityVerb.ESCROW_FUNDED,
        f"Funded {amount:,.2f} SKC into escrow for “{project.title}”",
        actor=client,
        job=job,
        project=project,
        target=escrow,
        amount=amount,
    )
    record_activity(
        ActivityVerb.PROJECT_CREATED,
        f"Project “{project.title}” started",
        actor=client,
        job=job,
        project=project,
        target=project,
        target_url=project.get_absolute_url(),
    )
    notify(
        agreement.freelancer,
        NotificationType.ESCROW_FUNDED,
        f"“{project.title}” is funded and ready",
        message=f"{amount:,.2f} SKC is held in escrow. You can now build your team "
        "and create tasks.",
        actor=client,
        target_url=_project_url(project),
        level="SUCCESS",
        email=True,
    )

    from apps.core.selectors import invalidate_platform_stats
    from apps.projects.services import refresh_profile_counters

    transaction.on_commit(invalidate_platform_stats)
    refresh_profile_counters(project)
    return project


@transaction.atomic()
def set_task_allocation(*, task, actor, amount, note: str = "") -> EscrowAllocation:
    """Assign a slice of escrow to a task.

    Refuses any split that would total more than the funded escrow.  The exact
    equality is checked at release time by
    :func:`assert_allocations_balanced`, because a team naturally builds the
    split up task by task.
    """
    from apps.tasks.models import Task

    task = Task.objects.select_for_update().get(pk=task.pk)
    project = task.project
    escrow = Escrow.objects.select_for_update().get(project=project)

    if actor.pk != project.freelancer_id and not actor.is_platform_admin:
        raise PermissionDenied("Only the team owner can set task allocations.")
    if task.is_paid:
        raise InvalidState("This task has already been paid; its allocation is fixed.")
    if escrow.is_locked:
        raise EscrowLocked(escrow.lock_reason or "Escrow is locked by a dispute.")

    amount = to_coin(amount)
    if amount < ZERO:
        raise ValidationFailed("An allocation cannot be negative.")

    others = (
        Task.objects.filter(project=project)
        .exclude(pk=task.pk)
        .exclude(status=Task.Status.CANCELLED)
        .aggregate(total=Sum("skillcoin_allocation"))["total"]
        or ZERO
    )
    if others + amount > escrow.funded_amount:
        raise AllocationMismatch(
            f"Allocations would total {others + amount:,.2f} SKC but escrow holds "
            f"{escrow.funded_amount:,.2f} SKC. "
            f"{escrow.funded_amount - others:,.2f} SKC is still unallocated."
        )

    previous = task.skillcoin_allocation
    task.skillcoin_allocation = amount
    task.save(update_fields=["skillcoin_allocation", "updated_at"])

    # One live allocation row per task. The history of who changed it, and from
    # what, is in the audit trail rather than in a second table.
    record, _ = EscrowAllocation.objects.update_or_create(
        task=task,
        defaults={
            "escrow": escrow,
            "freelancer": task.assignee or project.freelancer,
            "amount": amount,
            "status": EscrowAllocation.Status.ALLOCATED,
            "note": note[:300],
        },
    )
    record_audit(
        AuditLog.Action.ALLOCATION_SET,
        record,
        actor=actor,
        previous={"amount": str(previous)},
        new={"amount": str(amount)},
        reason=note or "Task allocation changed",
        amount=amount,
        project=project,
        task=task,
    )
    record_activity(
        ActivityVerb.ALLOCATION_SET,
        f"Allocated {amount:,.2f} SKC to task “{task.title}”",
        actor=actor,
        project=project,
        task=task,
        target=record,
        amount=amount,
    )
    return record


def assert_allocations_balanced(project) -> None:
    """block release unless the split matches escrow exactly."""
    escrow = Escrow.objects.get(project=project)
    allocated = escrow.allocated_total
    if allocated != escrow.funded_amount:
        difference = escrow.funded_amount - allocated
        raise AllocationMismatch(
            f"Task allocations total {allocated:,.2f} SKC but escrow holds "
            f"{escrow.funded_amount:,.2f} SKC "
            f"({'under' if difference > 0 else 'over'}-allocated by "
            f"{abs(difference):,.2f} SKC). Balance the allocations to release payment."
        )


@transaction.atomic()
def register_release(*, escrow: Escrow, amount) -> Escrow:
    """Book a release against the escrow row. Called only by payments.services."""
    escrow = Escrow.objects.select_for_update().get(pk=escrow.pk)
    amount = positive_coin(amount)
    if escrow.is_locked:
        raise EscrowLocked(escrow.lock_reason or "Escrow is locked by a dispute.")
    if amount > escrow.held_amount:
        raise InsufficientFunds(
            f"Escrow holds {escrow.held_amount:,.2f} SKC; cannot release "
            f"{amount:,.2f} SKC.",
            required=amount,
            available=escrow.held_amount,
        )

    escrow.held_amount -= amount
    escrow.released_amount += amount
    if escrow.held_amount <= ZERO:
        escrow.status = Escrow.Status.RELEASED
        escrow.released_at = timezone.now()
    else:
        escrow.status = Escrow.Status.PARTIALLY_RELEASED
    escrow.save(
        update_fields=[
            "held_amount",
            "released_amount",
            "status",
            "released_at",
            "updated_at",
        ]
    )
    return escrow


@transaction.atomic()
def register_refund(*, escrow: Escrow, amount) -> Escrow:
    """Book a refund against the escrow row. Called only by payments.services."""
    escrow = Escrow.objects.select_for_update().get(pk=escrow.pk)
    amount = positive_coin(amount)
    if amount > escrow.held_amount:
        raise InsufficientFunds(
            f"Escrow holds {escrow.held_amount:,.2f} SKC; cannot refund "
            f"{amount:,.2f} SKC.",
            required=amount,
            available=escrow.held_amount,
        )

    escrow.held_amount -= amount
    escrow.refunded_amount += amount
    if escrow.held_amount <= ZERO:
        escrow.status = (
            Escrow.Status.REFUNDED
            if escrow.released_amount <= ZERO
            else Escrow.Status.RELEASED
        )
        escrow.released_at = timezone.now()
    escrow.save(
        update_fields=[
            "held_amount",
            "refunded_amount",
            "status",
            "released_at",
            "updated_at",
        ]
    )
    return escrow


@transaction.atomic()
def set_escrow_lock(*, escrow: Escrow, locked: bool, reason: str = "") -> Escrow:
    """Freeze or unfreeze releases — used when a dispute opens/closes."""
    escrow = Escrow.objects.select_for_update().get(pk=escrow.pk)
    escrow.is_locked = locked
    escrow.lock_reason = reason[:300] if locked else ""
    if locked:
        escrow.status = Escrow.Status.DISPUTED
    elif escrow.status == Escrow.Status.DISPUTED:
        escrow.status = (
            Escrow.Status.PARTIALLY_RELEASED
            if escrow.released_amount > ZERO
            else Escrow.Status.ACTIVE
        )
    escrow.save(update_fields=["is_locked", "lock_reason", "status", "updated_at"])
    return escrow


# --------------------------------------------------------------------------- #
# Releasing money out of escrow
# --------------------------------------------------------------------------- #
@transaction.atomic()
def release_task_payment(
    *,
    task,
    actor=None,
    trigger: str = EscrowAllocation.Trigger.CLIENT_APPROVAL,
    amount=None,
    note: str = "",
) -> EscrowAllocation:
    """Pay one task's allocation out of escrow.

    Idempotent by construction: the task row is locked and re-checked, so a
    client clicking "approve" at the same moment the auto-release sweep runs
    cannot pay twice. The ``allocation_released_requires_transaction``
    constraint is the backstop.
    """
    from apps.tasks.models import Task

    task = (
        Task.objects.select_for_update()
        .select_related("project", "project__client", "project__freelancer", "assignee")
        .get(pk=task.pk)
    )
    project = task.project

    if task.payment_state == Task.PaymentState.RELEASED:
        raise InvalidState("This task has already been paid.")
    if task.payment_state == Task.PaymentState.DISPUTED:
        raise EscrowLocked(
            "This task's payment is paused by an open dispute. It will be "
            "settled by the dispute resolution."
        )
    if task.payment_state not in {
        Task.PaymentState.AWAITING_CLIENT_ACTION,
        Task.PaymentState.AUTO_RELEASE_PENDING,
    }:
        raise InvalidState("This task is not awaiting payment.")

    escrow = Escrow.objects.select_for_update().get(project=project)
    if escrow.is_locked:
        raise EscrowLocked(escrow.lock_reason or "Escrow is locked by a dispute.")

    amount = positive_coin(amount if amount is not None else task.skillcoin_allocation)
    if (
        amount > task.skillcoin_allocation
        and trigger != EscrowAllocation.Trigger.DISPUTE_RESOLUTION
    ):
        raise ValidationFailed(
            f"{amount:,.2f} SKC exceeds this task's allocation of "
            f"{task.skillcoin_allocation:,.2f} SKC."
        )

    payee = task.assignee or project.freelancer

    # Authorisation: the client approves, an administrator can force, and the
    # 48-hour rule has no actor at all.
    if trigger == EscrowAllocation.Trigger.CLIENT_APPROVAL:
        if actor is None or actor.pk != project.client_id:
            raise PermissionDenied("Only the client can approve this payment.")
    elif trigger == EscrowAllocation.Trigger.ADMIN_RELEASE:
        require_admin(actor)

    automatic = trigger == EscrowAllocation.Trigger.AUTO_RELEASE

    # Escrow → freelancer. The client's available balance is untouched.
    debit, credit = ledger.release_payment(
        client=project.client,
        freelancer=payee,
        amount=amount,
        project=project,
        task=task,
        actor=actor,
        automatic=automatic,
    )
    register_release(escrow=escrow, amount=amount)

    allocation, _ = EscrowAllocation.objects.update_or_create(
        task=task,
        defaults={
            "escrow": escrow,
            "freelancer": payee,
            "amount": amount,
            "status": EscrowAllocation.Status.RELEASED,
            "released_at": timezone.now(),
            "trigger": trigger,
            "released_by": actor,
            "note": note[:300],
            "debit_transaction": debit,
            "credit_transaction": credit,
        },
    )

    task.payment_state = task.PaymentState.RELEASED
    task.payment_transaction = credit
    task.released_at = timezone.now()
    task.auto_released = automatic
    task.review_window_ends_at = None
    # A paid task is a finished task, however it came to be paid. Leaving an
    # auto-released task at SUBMITTED would block the project from ever being
    # marked ready, because that check requires every task to be resolved.
    if task.status in {task.Status.APPROVED, task.Status.SUBMITTED}:
        task.status = task.Status.COMPLETED
        task.completed_at = timezone.now()
    task.save(
        update_fields=[
            "payment_state",
            "payment_transaction",
            "released_at",
            "auto_released",
            "review_window_ends_at",
            "status",
            "completed_at",
            "updated_at",
        ]
    )

    record_audit(
        AuditLog.Action.AUTO_RELEASE if automatic else AuditLog.Action.PAYMENT_RELEASE,
        allocation,
        actor=actor,
        new={
            "amount": str(amount),
            "payee": payee.email,
            "trigger": trigger,
            "escrow_held_after": str(escrow.held_amount),
        },
        reason=note or f"Task payment via {trigger}",
        amount=amount,
        task=task,
        project=project,
    )
    record_activity(
        (
            ActivityVerb.PAYMENT_AUTO_RELEASED
            if automatic
            else ActivityVerb.PAYMENT_RELEASED
        ),
        f"{amount:,.2f} SKC released to {payee.full_name} for “{task.title}”"
        + (" (48-hour rule)" if automatic else ""),
        actor=actor,
        project=project,
        task=task,
        target=allocation,
        amount=amount,
    )
    notify(
        payee,
        NotificationType.PAYMENT_RELEASED,
        f"{amount:,.2f} SKC received",
        message=f"Payment for “{task.title}” on “{project.title}”"
        + (
            " was released automatically after the 48-hour review window."
            if automatic
            else " has been released."
        ),
        actor=actor,
        target_url="/wallet/",
        level="SUCCESS",
        email=True,
    )
    if automatic:
        notify(
            project.client,
            NotificationType.PAYMENT_RELEASED,
            f"{amount:,.2f} SKC auto-released for “{task.title}”",
            message="The 48-hour review window closed without an approval or a "
            "dispute, so the escrowed payment was released as agreed.",
            target_url=_project_url(project),
            email=True,
        )

    from apps.projects.services import recompute_progress

    recompute_progress(project)
    logger.info(
        "task payment released task=%s amount=%s trigger=%s payee=%s",
        task.public_id,
        amount,
        trigger,
        payee.pk,
    )
    return allocation


def due_for_auto_release(*, limit: int = 200):
    """Tasks whose review window has closed with no action taken.

    The window is a stored timestamp, so this is a pure query: correctness does
    not depend on anything having run on a schedule.
    """
    from apps.tasks.models import Task

    return (
        Task.objects.filter(
            payment_state__in=[
                Task.PaymentState.AWAITING_CLIENT_ACTION,
                Task.PaymentState.AUTO_RELEASE_PENDING,
            ],
            review_window_ends_at__isnull=False,
            review_window_ends_at__lte=timezone.now(),
            skillcoin_allocation__gt=ZERO,
        )
        .select_related("project", "project__escrow")
        .order_by("review_window_ends_at")[:limit]
    )


def process_auto_releases(*, limit: int = 200) -> dict:
    """Release every task whose 48-hour window has closed.

    Called three ways, all of them safe: by the management command, and lazily
    whenever a task or payment page is opened. One task per transaction, so a
    single bad row cannot block every other payout.
    """
    released, skipped, failed = 0, 0, 0
    for task in list(due_for_auto_release(limit=limit)):
        escrow = getattr(task.project, "escrow", None)
        # A disputed project or locked escrow pauses the rule.
        if escrow is None or escrow.is_locked:
            skipped += 1
            continue
        if task.project.status == task.project.Status.DISPUTED:
            skipped += 1
            continue
        try:
            with transaction.atomic():
                release_task_payment(
                    task=task,
                    actor=None,
                    trigger=EscrowAllocation.Trigger.AUTO_RELEASE,
                )
            released += 1
        except InvalidState:
            skipped += 1
        except Exception:
            failed += 1
            logger.exception("auto-release failed task=%s", task.public_id)

    if released or failed:
        logger.info(
            "auto-release sweep released=%s skipped=%s failed=%s",
            released,
            skipped,
            failed,
        )
    return {"released": released, "skipped": skipped, "failed": failed}


@transaction.atomic()
def release_remaining_escrow(*, project, actor=None, note: str = "") -> list:
    """Pay out everything still held when the project is finally approved.

    Any approved-but-unpaid task is paid at its allocation; anything left over
    goes to the hired freelancer as a final project payment, so escrow always
    ends at zero.
    """
    from apps.tasks.models import Task

    escrow = Escrow.objects.select_for_update().get(project=project)
    if escrow.is_locked:
        raise EscrowLocked(escrow.lock_reason or "Escrow is locked by a dispute.")

    allocations = []
    pending = (
        Task.objects.select_for_update()
        .filter(
            project=project,
            payment_state__in=[
                Task.PaymentState.AWAITING_CLIENT_ACTION,
                Task.PaymentState.AUTO_RELEASE_PENDING,
            ],
            skillcoin_allocation__gt=ZERO,
        )
        .order_by("order")
    )
    for task in pending:
        allocations.append(
            release_task_payment(
                task=task,
                actor=actor,
                trigger=EscrowAllocation.Trigger.PROJECT_APPROVAL,
                note=note or "Released on final project approval.",
            )
        )

    escrow.refresh_from_db()
    if escrow.held_amount > ZERO:
        allocations.append(
            _release_project_remainder(
                project=project, escrow=escrow, actor=actor, note=note
            )
        )
        return allocations


@transaction.atomic()
def _release_project_remainder(*, project, escrow: Escrow, actor, note: str):
    """Final, non-task payment of whatever escrow still holds."""
    amount = escrow.held_amount
    debit, credit = ledger.release_payment(
        client=project.client,
        freelancer=project.freelancer,
        amount=amount,
        project=project,
        actor=actor,
    )
    register_release(escrow=escrow, amount=amount)

    allocation = EscrowAllocation.objects.create(
        escrow=escrow,
        task=None,
        freelancer=project.freelancer,
        amount=amount,
        status=EscrowAllocation.Status.RELEASED,
        released_at=timezone.now(),
        trigger=EscrowAllocation.Trigger.PROJECT_APPROVAL,
        released_by=actor,
        note=note[:300] or "Final project payment.",
        debit_transaction=debit,
        credit_transaction=credit,
    )
    record_audit(
        AuditLog.Action.PAYMENT_RELEASE,
        allocation,
        actor=actor,
        new={"amount": str(amount), "kind": "PROJECT"},
        reason="Final project payment",
        amount=amount,
        project=project,
    )
    record_activity(
        ActivityVerb.PAYMENT_RELEASED,
        f"Final payment of {amount:,.2f} SKC released to "
        f"{project.freelancer.full_name}",
        actor=actor,
        project=project,
        target=allocation,
        amount=amount,
    )
    notify(
        project.freelancer,
        NotificationType.PAYMENT_RELEASED,
        f"Final payment: {amount:,.2f} SKC",
        message=f"“{project.title}” is complete and the remaining escrow has been released.",
        actor=actor,
        target_url="/wallet/",
        level="SUCCESS",
        email=True,
    )
    return allocation


@transaction.atomic()
def issue_refund(*, project, amount, reason: str, actor=None):
    """Return escrowed coin to the client."""
    if not reason.strip():
        raise ValidationFailed("A refund requires a written reason.")
    escrow = Escrow.objects.select_for_update().get(project=project)
    amount = positive_coin(amount)

    txn = ledger.refund_escrow(
        client=project.client,
        amount=amount,
        project=project,
        actor=actor,
        reason=reason,
    )
    register_refund(escrow=escrow, amount=amount)

    record_audit(
        AuditLog.Action.REFUND,
        txn,
        actor=actor,
        new={"amount": str(amount)},
        reason=reason,
        amount=amount,
        project=project,
    )
    record_activity(
        ActivityVerb.REFUND_ISSUED,
        f"{amount:,.2f} SKC refunded to the client",
        actor=actor,
        project=project,
        target=txn,
        amount=amount,
    )
    notify(
        project.client,
        NotificationType.PAYMENT_RELEASED,
        f"{amount:,.2f} SKC refunded",
        message=f"Refund for “{project.title}”: {reason[:300]}",
        actor=actor,
        target_url="/wallet/",
        level="SUCCESS",
        email=True,
    )
    return txn
