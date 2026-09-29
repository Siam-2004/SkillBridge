from __future__ import annotations
import logging
from decimal import Decimal
from django.db import transaction
from django.db.models import F
from apps.core.exceptions import FinancialError, InsufficientFunds, ValidationFailed
from apps.core.money import ZERO, positive_coin
from apps.core.services import _jsonable
from apps.wallets.models import Wallet, WalletTransaction
logger = logging.getLogger('skillbridge.money')
Bucket = WalletTransaction.Bucket
Type = WalletTransaction.Type
BUCKET_FIELD = {Bucket.AVAILABLE: 'available_balance', Bucket.RESERVED: 'reserved_balance', Bucket.ESCROW: 'escrow_balance'}

def lock_wallet(user_or_wallet) -> Wallet:
    if isinstance(user_or_wallet, Wallet):
        wallet_id = user_or_wallet.pk
    else:
        wallet, _ = Wallet.objects.get_or_create(user=user_or_wallet)
        wallet_id = wallet.pk
    return Wallet.objects.select_for_update().get(pk=wallet_id)

def lock_wallets(*users) -> dict[int, Wallet]:
    ids = sorted({u.pk for u in users if u is not None})
    wallets = {}
    for uid in ids:
        wallet, _ = Wallet.objects.get_or_create(user_id=uid)
        wallets[uid] = Wallet.objects.select_for_update().get(pk=wallet.pk)
    return wallets

@transaction.atomic()
def move(*, user, amount, transaction_type: str, from_bucket: str, to_bucket: str, wallet: Wallet | None=None, actor=None, description: str='', job=None, project=None, task=None, counterparty=None, related: WalletTransaction | None=None, reason: str='', allow_frozen: bool=False, **metadata) -> WalletTransaction:
    amount = positive_coin(amount)
    if from_bucket == to_bucket:
        raise FinancialError('A movement must change bucket.')
    if from_bucket == Bucket.EXTERNAL and to_bucket == Bucket.EXTERNAL:
        raise FinancialError('A movement must touch the wallet.')
    wallet = wallet if wallet is not None else lock_wallet(user)
    if wallet.is_frozen and (not allow_frozen) and (from_bucket != Bucket.EXTERNAL):
        raise FinancialError(f"This wallet is frozen: {wallet.frozen_reason or 'contact support'}.")
    before_total = wallet.total
    before_snapshot = {'available': str(wallet.available_balance), 'reserved': str(wallet.reserved_balance), 'escrow': str(wallet.escrow_balance)}
    if from_bucket != Bucket.EXTERNAL:
        field = BUCKET_FIELD[from_bucket]
        current: Decimal = getattr(wallet, field)
        if current < amount:
            raise InsufficientFunds(required=amount, available=current, code=f'insufficient_{field}')
        setattr(wallet, field, current - amount)
    if to_bucket != Bucket.EXTERNAL:
        field = BUCKET_FIELD[to_bucket]
        setattr(wallet, field, getattr(wallet, field) + amount)
    if from_bucket == Bucket.EXTERNAL:
        wallet.lifetime_deposited += amount
    if to_bucket == Bucket.EXTERNAL:
        wallet.lifetime_withdrawn += amount
    if transaction_type == Type.PROJECT_PAYMENT:
        wallet.lifetime_earned += amount
    if transaction_type == Type.ESCROW_HOLD:
        wallet.lifetime_spent += amount
    wallet.version = F('version') + 1
    wallet.save(update_fields=['available_balance', 'reserved_balance', 'escrow_balance', 'version', 'updated_at', 'lifetime_deposited', 'lifetime_withdrawn', 'lifetime_earned', 'lifetime_spent'])
    wallet.refresh_from_db(fields=['version', 'available_balance', 'reserved_balance', 'escrow_balance'])
    after_total = wallet.total
    delta = after_total - before_total
    txn = WalletTransaction.objects.create(wallet=wallet, user=wallet.user, transaction_type=transaction_type, status=WalletTransaction.Status.COMPLETED, amount=amount, delta=delta, from_bucket=from_bucket, to_bucket=to_bucket, balance_before=before_total, balance_after=after_total, available_after=wallet.available_balance, reserved_after=wallet.reserved_balance, escrow_after=wallet.escrow_balance, job_id=getattr(job, 'id', job) if job else None, project_id=getattr(project, 'id', project) if project else None, task_id=getattr(task, 'id', task) if task else None, counterparty=counterparty, related_transaction=related, actor=actor, description=description[:300], metadata=_jsonable(metadata))
    logger.info('ledger %s user=%s %s→%s amount=%s total=%s→%s txn=%s', transaction_type, wallet.user_id, from_bucket, to_bucket, amount, before_total, after_total, txn.internal_transaction_id)
    return txn

def credit_deposit(*, user, amount, actor=None, deposit=None, **kw) -> WalletTransaction:
    return move(user=user, amount=amount, transaction_type=Type.DEPOSIT, from_bucket=Bucket.EXTERNAL, to_bucket=Bucket.AVAILABLE, actor=actor, description=f'Deposit approved ({deposit.get_payment_method_display()})' if deposit else 'Deposit approved', external_transaction_id=getattr(deposit, 'external_transaction_id', ''), deposit=deposit, **kw)

def reserve_job_budget(*, user, amount, job, actor=None, **kw) -> WalletTransaction:
    return move(user=user, amount=amount, transaction_type=Type.BUDGET_RESERVATION, from_bucket=Bucket.AVAILABLE, to_bucket=Bucket.RESERVED, job=job, actor=actor, description=f'Budget reserved for job “{job.title[:80]}”', **kw)

def release_job_budget(*, user, amount, job, actor=None, reason='', **kw) -> WalletTransaction:
    return move(user=user, amount=amount, transaction_type=Type.BUDGET_RELEASE, from_bucket=Bucket.RESERVED, to_bucket=Bucket.AVAILABLE, job=job, actor=actor, reason=reason, description=f'Reserved budget released for job “{job.title[:80]}”', **kw)

def hold_escrow(*, user, amount, project, job=None, actor=None, **kw) -> WalletTransaction:
    return move(user=user, amount=amount, transaction_type=Type.ESCROW_HOLD, from_bucket=Bucket.RESERVED, to_bucket=Bucket.ESCROW, project=project, job=job, actor=actor, description=f'Escrow funded for project “{project.title[:80]}”', **kw)

def hold_escrow_from_available(*, user, amount, project, job=None, actor=None, **kw) -> WalletTransaction:
    return move(user=user, amount=amount, transaction_type=Type.ESCROW_HOLD, from_bucket=Bucket.AVAILABLE, to_bucket=Bucket.ESCROW, project=project, job=job, actor=actor, description=f'Escrow top-up for project “{project.title[:80]}”', **kw)

def release_payment(*, client, freelancer, amount, project, task=None, actor=None, automatic: bool=False, **kw) -> tuple[WalletTransaction, WalletTransaction]:
    amount = positive_coin(amount)
    label = 'Automatic release' if automatic else 'Payment released'
    detail = f' for task “{task.title[:60]}”' if task is not None else ''
    debit = move(user=client, amount=amount, transaction_type=Type.ESCROW_RELEASE, from_bucket=Bucket.ESCROW, to_bucket=Bucket.EXTERNAL, project=project, task=task, counterparty=freelancer, actor=actor, description=f'{label}{detail}', automatic=automatic, **kw)
    credit = move(user=freelancer, amount=amount, transaction_type=Type.PROJECT_PAYMENT, from_bucket=Bucket.EXTERNAL, to_bucket=Bucket.AVAILABLE, project=project, task=task, counterparty=client, actor=actor, related=debit, description=f'{label}{detail}', automatic=automatic, **kw)
    WalletTransaction.objects.filter(pk=debit.pk).update(related_transaction=credit)
    debit.refresh_from_db(fields=['related_transaction'])
    return (debit, credit)

def refund_escrow(*, client, amount, project, actor=None, reason: str='', **kw) -> WalletTransaction:
    return move(user=client, amount=amount, transaction_type=Type.REFUND, from_bucket=Bucket.ESCROW, to_bucket=Bucket.AVAILABLE, project=project, actor=actor, reason=reason, description=f'Refund for project “{project.title[:80]}”', **kw)

def reserve_withdrawal(*, user, amount, withdrawal=None, actor=None, **kw) -> WalletTransaction:
    return move(user=user, amount=amount, transaction_type=Type.WITHDRAWAL, from_bucket=Bucket.AVAILABLE, to_bucket=Bucket.RESERVED, actor=actor, description='Withdrawal requested', withdrawal=withdrawal, **kw)

def payout_withdrawal(*, user, amount, withdrawal, actor=None, **kw) -> WalletTransaction:
    return move(user=user, amount=amount, transaction_type=Type.WITHDRAWAL, from_bucket=Bucket.RESERVED, to_bucket=Bucket.EXTERNAL, actor=actor, description=f'Withdrawal paid out ({withdrawal.get_payment_method_display()})', external_transaction_id=withdrawal.external_transaction_id, withdrawal=withdrawal, **kw)

def reverse_withdrawal(*, user, amount, withdrawal, actor=None, reason: str='', **kw) -> WalletTransaction:
    return move(user=user, amount=amount, transaction_type=Type.WITHDRAWAL_REVERSAL, from_bucket=Bucket.RESERVED, to_bucket=Bucket.AVAILABLE, actor=actor, reason=reason, description='Withdrawal request rejected — funds returned', withdrawal=withdrawal, **kw)

def adjust(*, user, amount, bucket: str, credit: bool, actor, reason: str, **kw) -> WalletTransaction:
    if not reason.strip():
        raise ValidationFailed('An adjustment requires a written reason.')
    if not actor or not actor.is_platform_admin:
        raise FinancialError('Only an administrator can post an adjustment.')
    return move(user=user, amount=amount, transaction_type=Type.ADJUSTMENT, from_bucket=Bucket.EXTERNAL if credit else bucket, to_bucket=bucket if credit else Bucket.EXTERNAL, actor=actor, reason=reason, description=f'Administrative adjustment: {reason[:200]}', allow_frozen=True, **kw)
move_available_to_escrow = hold_escrow_from_available
release_escrow_to_freelancer = release_payment
complete_withdrawal = payout_withdrawal
reject_withdrawal = reverse_withdrawal

def verify_ledger(user) -> dict:
    from django.db.models import Sum
    wallet = Wallet.objects.get(user=user)
    ledger_total = WalletTransaction.objects.filter(user=user, status=WalletTransaction.Status.COMPLETED).aggregate(total=Sum('delta'))['total'] or ZERO
    stored = wallet.total
    return {'user': user, 'stored_total': stored, 'ledger_total': ledger_total, 'difference': stored - ledger_total, 'balanced': stored == ledger_total}
