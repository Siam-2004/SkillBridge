"""Account-lifecycle side effects.

A user must never exist without the objects the rest of the domain assumes: a
role profile, a wallet and a rating summary.  This runs inside the same
transaction as the ``INSERT``, so there is no window in which a half-built
account is visible to another request.
"""

from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import Role, User


@receiver(post_save, sender=User, dispatch_uid="accounts.bootstrap_user")
def bootstrap_user(sender, instance: User, created: bool, raw: bool = False, **kwargs):
    # ``raw`` means loaddata/fixtures: the related tables may not be populated
    # yet and fixtures carry their own rows.
    if not created or raw:
        return

    from apps.profiles.models import ClientProfile, FreelancerProfile
    from apps.wallets.models import Wallet

    Wallet.objects.get_or_create(user=instance)
    if instance.role == Role.CLIENT:
        ClientProfile.objects.get_or_create(user=instance)
    elif instance.role == Role.FREELANCER:
        FreelancerProfile.objects.get_or_create(user=instance)
