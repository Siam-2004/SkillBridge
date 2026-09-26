"""Recompute every derived counter from source data.

All the denormalised figures on a profile and every public rating
are caches over rows that already exist, so they can always be rebuilt.
Run this after a data migration, a bulk import, or any time an operator
suspects a counter has drifted.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Count, Q


class Command(BaseCommand):
    help = "Recompute profile counters, ratings, skill usage and search vectors."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-search",
            action="store_true",
            help="Leave full-text search vectors alone (the slowest step).",
        )

    def handle(self, *args, **options):
        from apps.accounts.models import Role, User
        from apps.marketplace.models import Job
        from apps.profiles.models import Skill
        from apps.profiles.models import ClientProfile, FreelancerProfile
        from apps.projects.models import Project
        from apps.projects.services import refresh_profile_counters
        from apps.reviews.services import recalculate_rating

        # -- profiles that have projects -------------------------------- #
        touched = 0
        for project in Project.objects.select_related("client", "freelancer").iterator(
            chunk_size=100
        ):
            refresh_profile_counters(project)
            touched += 1
        self.stdout.write(f" projects processed: {touched}")

        # -- clients with jobs but no project yet ------------------------ #
        for profile in ClientProfile.objects.select_related("user").iterator(
            chunk_size=200
        ):
            ClientProfile.objects.filter(pk=profile.pk).update(
                jobs_posted=Job.objects.alive()
                .filter(client=profile.user)
                .exclude(status=Job.Status.DRAFT)
                .count(),
                total_hired=Project.objects.filter(client=profile.user)
                .values("freelancer")
                .distinct()
                .count(),
            )
        self.stdout.write(f" client profiles: {ClientProfile.objects.count()}")

        # -- freelancer proposal success --------------------------------- #
        from apps.proposals.models import Proposal

        for profile in FreelancerProfile.objects.select_related("user").iterator(
            chunk_size=200
        ):
            counts = Proposal.objects.filter(freelancer=profile.user).aggregate(
                submitted=Count("id"),
                accepted=Count("id", filter=Q(status=Proposal.Status.ACCEPTED)),
            )
            FreelancerProfile.objects.filter(pk=profile.pk).update(
                proposals_submitted=counts["submitted"] or 0,
                proposals_accepted=counts["accepted"] or 0,
            )
        self.stdout.write(f" freelancer profiles: {FreelancerProfile.objects.count()}")

        # -- ratings ----------------------------------------------- #
        rated = 0
        for user in User.objects.filter(
            role__in=[Role.CLIENT, Role.FREELANCER]
        ).iterator(chunk_size=200):
            recalculate_rating(user)
            rated += 1
        self.stdout.write(f" ratings recalculated: {rated}")

        # -- skill popularity ---------------------------------------------- #
        from django.db.models import Count

        updated = 0
        for skill in Skill.objects.annotate(
            uses=Count("jobs", distinct=True) + Count("freelancers", distinct=True)
        ):
            if skill.usage_count != skill.uses:
                Skill.objects.filter(pk=skill.pk).update(usage_count=skill.uses)
                updated += 1
        self.stdout.write(f" skills updated: {updated} of {Skill.objects.count()}")

        # -- search text ---------------------------------------------------- #
        if options["skip_search"]:
            self.stdout.write(" search text: skipped")
        else:
            counts = self._reindex
            self.stdout.write(f" search text: {counts}")

        self.stdout.write(self.style.SUCCESS("All derived metrics recomputed."))

    def _reindex(self) -> dict:
        """Rebuild every denormalised ``search_text`` column."""
        from apps.marketplace.models import Job
        from apps.marketplace.services import reindex_job
        from apps.portfolios.models import Portfolio
        from apps.portfolios.services import reindex_item
        from apps.profiles.models import ClientProfile, FreelancerProfile
        from apps.profiles.services import reindex_client, reindex_freelancer

        counts = {}
        for label, queryset, fn in (
            ("jobs", Job.objects.all(), reindex_job),
            (
                "freelancers",
                FreelancerProfile.objects.select_related("user"),
                reindex_freelancer,
            ),
            ("clients", ClientProfile.objects.select_related("user"), reindex_client),
            ("portfolio", Portfolio.objects.all(), reindex_item),
        ):
            n = 0
            for obj in queryset.iterator(chunk_size=200):
                fn(obj)
                n += 1
                counts[label] = n
                return counts
