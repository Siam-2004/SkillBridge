"""Prove that every stored balance still matches its ledger.

A balance and its ledger row are written in the same transaction, so a
discrepancy should be impossible. If one appears, the platform has a bug and
somebody needs to know today rather than at the next audit.

    python manage.py reconcile_wallets
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Re-derive every wallet from its ledger and report any disagreement."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        from apps.wallets.services import reconcile_wallets

        result = reconcile_wallets(limit=options["limit"])
        self.stdout.write(f"Checked {result['wallets_checked']} wallet(s).")

        if result["balanced"]:
            self.stdout.write(self.style.SUCCESS("Every wallet matches its ledger."))
            return

        self.stdout.write(
            self.style.ERROR(
                f"{result['discrepancy_count']} wallet(s) disagree with the ledger, "
                f"by {result['total_difference']} in total:"
            )
        )
        for row in result["details"]:
            self.stdout.write(
                f"  {row['user']}: stored {row['stored_total']}, "
                f"ledger {row['ledger_total']}, difference {row['difference']}"
            )
