"""Rebuild every public rating from the reviews behind it.

Ratings are recalculated whenever a review is written or moderated, so this is
a safety net rather than a requirement: if a stored average and its reviews
ever disagree, this is what makes them agree again.

    python manage.py recalculate_ratings
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Recalculate every user's rating summary from their reviews."

    def handle(self, *args, **options):
        from apps.accounts.models import Role, User
        from apps.reviews.services import recalculate_rating

        users = User.objects.filter(role__in=[Role.CLIENT, Role.FREELANCER])
        total = users.count()
        changed = 0

        for user in users.iterator(chunk_size=200):
            summary = recalculate_rating(user)
            if summary.total_reviews:
                changed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Recalculated {total} account(s); {changed} have at least one review."
            )
        )
