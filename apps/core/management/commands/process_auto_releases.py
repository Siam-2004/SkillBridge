"""Release task payments whose 48-hour review window has closed.

Optional. The window is a stored timestamp and every task, project and payment
page settles what is due when it loads, so the rule holds whether or not this
ever runs. Provided because running it is cheaper than waiting for somebody to
open a page, and because an operator may want to see what happened.

    python manage.py process_auto_releases
    python manage.py process_auto_releases --dry-run
"""

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Release payments whose 48-hour review window has closed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=200,
            help="Most tasks to settle in one run (default 200).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what is due without releasing anything.",
        )

    def handle(self, *args, **options):
        from apps.escrow.services import due_for_auto_release, process_auto_releases

        due = list(due_for_auto_release(limit=options["limit"]))
        if not due:
            self.stdout.write("Nothing is due for release.")
            return

        self.stdout.write(f"{len(due)} task(s) past their review window:")
        for task in due:
            overdue = timezone.now() - task.review_window_ends_at
            self.stdout.write(
                f"  {task.public_id}  {task.skillcoin_allocation:>12,.2f} SKC  "
                f"{task.title[:44]:<44}  {int(overdue.total_seconds() // 3600)}h overdue"
            )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — nothing was released."))
            return

        result = process_auto_releases(limit=options["limit"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Released {result['released']}, skipped {result['skipped']} "
                f"(disputed or locked), failed {result['failed']}."
            )
        )
