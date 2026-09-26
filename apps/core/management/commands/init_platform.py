"""Initialize SkillBridge with essential base data (taxonomy and superuser).

Usage:
    python manage.py init_platform
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

CATEGORIES = {
    "Web Development": [
        "Django",
        "Python",
        "React",
        "Next.js",
        "PostgreSQL",
        "REST APIs",
        "HTML",
        "CSS",
        "JavaScript",
        "Tailwind",
    ],
    "Mobile Development": ["Flutter", "React Native", "Kotlin", "Swift", "Firebase"],
    "Design": ["UI Design", "UX Research", "Figma", "Branding", "Illustration"],
    "Data & AI": ["Data Analysis", "Pandas", "Machine Learning", "SQL", "Dashboards"],
    "Writing": ["Copywriting", "Technical Writing", "Editing", "Localisation"],
    "Marketing": ["SEO", "Content Strategy", "Paid Social", "Email Marketing"],
    "DevOps": ["Linux", "CI/CD", "Nginx", "Monitoring", "Backups"],
    "Business": ["Bookkeeping", "Market Research", "Project Management"],
}

ADMIN_EMAIL = "admin@skillbridge.local"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin!2345"


class Command(BaseCommand):
    help = "Initializes the platform with base categories, skills and a superuser account."

    def add_arguments(self, parser):
        parser.add_argument(
            "--admin-email",
            default=ADMIN_EMAIL,
            help=f"Admin email (default: {ADMIN_EMAIL})",
        )
        parser.add_argument(
            "--admin-password",
            default=ADMIN_PASSWORD,
            help="Admin password (default: Admin!2345)",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Initializing SkillBridge platform..."))

        admin_email = options["admin_email"]
        admin_password = options["admin_password"]

        with transaction.atomic():
            admin_user = self._setup_admin(admin_email, admin_password)
            cat_count, skill_count = self._setup_taxonomy()

        self.stdout.write(self.style.SUCCESS("\nPlatform initialized successfully!"))
        self.stdout.write(f"  - Categories created: {cat_count}")
        self.stdout.write(f"  - Skills created:     {skill_count}")
        self.stdout.write(f"  - Superuser ready:    {admin_user.email} (Username: {admin_user.username})")
        self.stdout.write(f"  - Admin Password:     {admin_password}")

    def _setup_admin(self, email: str, password: str):
        from apps.accounts.models import User

        admin = User.objects.filter(email=email).first()
        if admin is None:
            admin = User.objects.create_superuser(
                email=email,
                username=ADMIN_USERNAME,
                password=password,
                first_name="Platform",
                last_name="Admin",
            )
            self.stdout.write(f"Created superuser: {admin.email}")
        else:
            self.stdout.write(f"Superuser already exists: {admin.email}")
        return admin

    def _setup_taxonomy(self) -> tuple[int, int]:
        from apps.profiles.models import Category, Skill

        cat_count = 0
        skill_count = 0

        for order, (cat_name, skill_names) in enumerate(CATEGORIES.items()):
            category, cat_created = Category.objects.get_or_create(
                name=cat_name,
                defaults={
                    "order": order,
                    "is_featured": order < 4,
                    "description": f"{cat_name} work on SkillBridge.",
                },
            )
            if cat_created:
                cat_count += 1

            for s_name in skill_names:
                _, s_created = Skill.objects.get_or_create(
                    name=s_name,
                    defaults={"category": category},
                )
                if s_created:
                    skill_count += 1

        return cat_count, skill_count
