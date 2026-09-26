"""Create a demo marketplace, by driving the real services.

Nothing here writes a row directly where a service exists to do it. That is
deliberate: the seed therefore exercises the same budget reservation, escrow
funding, task allocation and payment release that a real user would, and it
fails loudly if any of them is broken.

    python manage.py seed_demo

Running it twice is safe: accounts, categories and skills are reused. To start
from nothing, delete ``db.sqlite3`` and run ``migrate`` again — demo accounts
cannot simply be deleted, because their wallets and ledger rows are protected
against deletion, which is the behaviour this seed exists to demonstrate.
"""

from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

D = Decimal
PASSWORD = "Demo!2345"
ADMIN_PASSWORD = "Admin!2345"

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

FREELANCERS = [
    (
        "Arif",
        "Khan",
        "Django engineer",
        "Dhaka",
        1400,
        ["Django", "Python", "PostgreSQL", "REST APIs"],
    ),
    (
        "Nabila",
        "Roy",
        "Product designer",
        "Chattogram",
        1200,
        ["UI Design", "Figma", "UX Research"],
    ),
    (
        "Tanvir",
        "Ahmed",
        "Full-stack developer",
        "Dhaka",
        1600,
        ["React", "Next.js", "JavaScript", "Django"],
    ),
    (
        "Farzana",
        "Akter",
        "Mobile developer",
        "Sylhet",
        1300,
        ["Flutter", "Firebase", "Kotlin"],
    ),
    (
        "Rafi",
        "Hossain",
        "Data analyst",
        "Dhaka",
        1100,
        ["Data Analysis", "SQL", "Pandas", "Dashboards"],
    ),
    (
        "Sadia",
        "Islam",
        "Technical writer",
        "Khulna",
        900,
        ["Technical Writing", "Editing"],
    ),
    (
        "Imran",
        "Chowdhury",
        "DevOps engineer",
        "Dhaka",
        1800,
        ["Linux", "CI/CD", "Nginx", "Monitoring"],
    ),
    (
        "Mehjabin",
        "Haque",
        "Marketing strategist",
        "Dhaka",
        1000,
        ["SEO", "Content Strategy", "Email Marketing"],
    ),
]

CLIENTS = [
    ("Rina", "Haque", "Cloudhaat", "Retail"),
    ("Kamrul", "Islam", "Nirvana Foods", "Food and beverage"),
    ("Shahin", "Alam", "BRIX Logistics", "Logistics"),
    ("Tahmina", "Noor", "Aurora Health", "Healthcare"),
]

JOBS = [
    (
        "Build a logistics dashboard",
        "Web Development",
        42000,
        30,
        "A Django dashboard showing consignments, drivers and delivery status in "
        "one place. Role-based access so drivers see only their own runs.",
        "Consignment list with live status\nDriver and vehicle management\n"
        "Role-based access control\nDeployment and handover notes",
        ["Django", "Python", "PostgreSQL"],
    ),
    (
        "React storefront for a bakery",
        "Web Development",
        26000,
        25,
        "A fast storefront with online ordering and pickup scheduling. Content "
        "managed by our marketing person, so it needs a simple editor.",
        "Storefront with product pages\nOrdering and pickup scheduling\n"
        "Simple content editor\nBasic analytics",
        ["React", "Next.js", "JavaScript"],
    ),
    (
        "Redesign our mobile app onboarding",
        "Design",
        18000,
        18,
        "Our drop-off between install and first order is bad. We need the first "
        "five minutes rethought, not repainted.",
        "Audit of the current flow\nNew onboarding flow in Figma\n"
        "Prototype for user testing\nHandover to the dev team",
        ["UI Design", "UX Research", "Figma"],
    ),
    (
        "Sales data analysis and dashboard",
        "Data & AI",
        22000,
        20,
        "Two years of sales data in spreadsheets. We need to know what actually "
        "drives repeat orders, and a dashboard we can keep using.",
        "Data cleaning and consolidation\nAnalysis of repeat-order drivers\n"
        "Dashboard with monthly refresh\nWritten summary of findings",
        ["Data Analysis", "SQL", "Dashboards"],
    ),
    (
        "Flutter app for field inspections",
        "Mobile Development",
        38000,
        35,
        "Offline-first inspection app for field staff. Photos, forms and sync "
        "when a connection comes back.",
        "Offline-first data capture\nPhoto attachment and compression\n"
        "Background sync\nAndroid and iOS builds",
        ["Flutter", "Firebase"],
    ),
    (
        "Technical documentation for our API",
        "Writing",
        14000,
        15,
        "Our API works; nobody can tell how. We need reference documentation and "
        "a getting-started guide that a new developer can follow.",
        "API reference for every endpoint\nGetting-started guide\n"
        "Three worked examples\nStyle guide for future additions",
        ["Technical Writing", "Editing"],
    ),
    (
        "Set up CI and monitoring",
        "DevOps",
        20000,
        12,
        "We deploy by hand and find out about outages from customers. Both of "
        "those need to stop.",
        "CI pipeline with tests\nAutomated deployment\nUptime and error monitoring\n"
        "Runbook for common failures",
        ["Linux", "CI/CD", "Monitoring"],
    ),
    (
        "SEO and content plan",
        "Marketing",
        16000,
        21,
        "We rank for nothing. We want a plan we can execute ourselves after the "
        "first three months.",
        "Technical SEO audit\nKeyword and topic map\nThree-month content plan\n"
        "Handover workshop",
        ["SEO", "Content Strategy"],
    ),
]


class Command(BaseCommand):
    help = "Create a demo marketplace with realistic data."

    def handle(self, *args, **options):
        random.seed(20240915)
        self.stdout.write("Seeding Skillbridge demo data…")
        admin = self._admin()
        skills, categories = self._taxonomy()
        freelancers = self._freelancers(skills, categories)
        clients = self._clients()
        self._settings_and_homepage()

        jobs = self._jobs(clients, categories, skills, admin)
        proposals = self._proposals(jobs, freelancers)

        # Take three jobs to different points in the lifecycle, so every screen
        # has something real to show.
        self._to_completed(jobs[0], proposals, admin)
        self._to_active(jobs[1], proposals)
        self._to_negotiating(jobs[2], proposals)

        self.stdout.write(self.style.SUCCESS("\nDone. Sign in with:"))
        self.stdout.write(f"  Admin       admin@skillbridge.demo / {ADMIN_PASSWORD}")
        self.stdout.write(f"  Client      rina.haque@skillbridge.demo / {PASSWORD}")
        self.stdout.write(f"  Freelancer  arif.khan@skillbridge.demo / {PASSWORD}")
        self.stdout.write("")

    # -- pieces ------------------------------------------------------------ #
    def _admin(self):
        from apps.accounts.models import Role, User

        admin = User.objects.filter(email="admin@skillbridge.demo").first()
        if admin is None:
            admin = User.objects.create_superuser(
                email="admin@skillbridge.demo",
                username="admin",
                password=ADMIN_PASSWORD,
                first_name="Platform",
                last_name="Admin",
            )
        self.stdout.write("  admin account ready")
        return admin

    def _taxonomy(self):
        from apps.profiles.models import Category, Skill

        skills, categories = {}, {}
        for order, (name, skill_names) in enumerate(CATEGORIES.items()):
            category, _ = Category.objects.get_or_create(
                name=name,
                defaults={
                    "order": order,
                    "is_featured": order < 4,
                    "description": f"{name} work on Skillbridge.",
                },
            )
            categories[name] = category
            for skill_name in skill_names:
                skill, _ = Skill.objects.get_or_create(
                    name=skill_name, defaults={"category": category}
                )
                skills[skill_name] = skill
        self.stdout.write(f"  {len(categories)} categories, {len(skills)} skills")
        return skills, categories

    def _account(self, first, last, role):
        from apps.accounts.models import User

        username = f"{first}.{last}".lower()
        email = f"{username}@skillbridge.demo"
        user = User.objects.filter(email=email).first()
        if user:
            return user
        user = User.objects.create_user(
            email=email,
            username=username,
            password=PASSWORD,
            role=role,
            first_name=first,
            last_name=last,
        )
        User.objects.filter(pk=user.pk).update(
            is_email_verified=True, email_verified_at=timezone.now()
        )
        user.refresh_from_db()
        return user

    def _freelancers(self, skills, categories):
        from apps.accounts.models import Role
        from apps.portfolios.services import create_item
        from apps.profiles.models import FreelancerProfile
        from apps.profiles.services import (
            add_education,
            add_experience,
            set_freelancer_skills,
            update_freelancer_profile,
        )

        made = []
        for first, last, title, location, rate, skill_names in FREELANCERS:
            user = self._account(first, last, Role.FREELANCER)
            update_freelancer_profile(
                user=user,
                professional_title=title,
                bio=(
                    f"{title} based in {location}. I work on a small number of "
                    "projects at a time and hand over documentation with every one."
                ),
                location=location,
                hourly_rate=D(rate),
                years_experience=random.randint(3, 11),
                availability=FreelancerProfile.Availability.FULL_TIME,
                experience_level=random.choice(["INTERMEDIATE", "EXPERT"]),
                is_available_for_hire=True,
                languages="Bangla, English",
            )
            profile = FreelancerProfile.objects.get(user=user)
            set_freelancer_skills(
                profile=profile,
                entries=[
                    {
                        "skill_id": skills[n].pk,
                        "level": random.randint(2, 4),
                        "years": random.randint(2, 8),
                    }
                    for n in skill_names
                    if n in skills
                ],
            )
            profile.categories.set(
                [
                    c
                    for name, c in categories.items()
                    if any(s in CATEGORIES[name] for s in skill_names)
                ]
            )
            add_experience(
                profile=profile,
                actor=user,
                position=title,
                company=f"{last} Studio",
                start_date=timezone.now().date() - timedelta(days=365 * 4),
                is_current=True,
                description="Client work across product and platform engineering.",
            )
            add_education(
                profile=profile,
                actor=user,
                institution="University of Dhaka",
                degree="BSc",
                field="Computer Science",
                start_date=timezone.now().date() - timedelta(days=365 * 10),
                end_date=timezone.now().date() - timedelta(days=365 * 6),
            )
            create_item(
                profile=profile,
                actor=user,
                title=f"{skill_names[0]} project for a local business",
                description=(
                    f"A {title.lower()} engagement delivered end to end: discovery, "
                    "build, handover and two weeks of support afterwards."
                ),
                skills=[skills[n] for n in skill_names[:3] if n in skills],
                technologies=", ".join(skill_names[:4]),
                role="Lead",
                outcome="Delivered on time and still in use.",
                is_public=True,
                completed_on=timezone.now().date()
                - timedelta(days=random.randint(60, 400)),
            )
            made.append(user)
        self.stdout.write(f"  {len(made)} freelancers with profiles and portfolios")
        return made

    def _clients(self):
        from apps.accounts.models import Role
        from apps.profiles.services import update_client_profile

        made = []
        for first, last, company, industry in CLIENTS:
            user = self._account(first, last, Role.CLIENT)
            update_client_profile(
                user=user,
                company_name=company,
                industry=industry,
                location="Dhaka",
                bio=f"We are {company}. We hire for focused pieces of work with clear outcomes.",
                company_description=f"{company} operates in {industry.lower()}.",
            )
            made.append(user)
        self.stdout.write(f"  {len(made)} clients")
        return made

    def _fund(self, user, amount, admin):
        """Credit a wallet the way a real deposit does.

        Skipped if the wallet already holds anything, so running the seed twice
        does not mint a second 200,000 SkillCoin out of nowhere.
        """
        from apps.payments.services import approve_deposit, submit_deposit
        from apps.wallets.selectors import get_wallet

        if get_wallet(user).total > 0:
            return

        deposit = submit_deposit(
            user=user,
            amount=D(amount),
            payment_method="BKASH",
            external_transaction_id=f"SEED-{user.pk:04d}-{timezone.now():%H%M%S%f}",
            sender_account="01712345678",
        )
        approve_deposit(deposit=deposit, admin=admin)

    def _jobs(self, clients, categories, skills, admin):
        from apps.marketplace.models import Job
        from apps.marketplace.services import create_job

        for client in clients:
            self._fund(client, 200000, admin)
        self.stdout.write("  client wallets funded through the deposit flow")

        made = []
        for index, (
            title,
            category,
            budget,
            days,
            description,
            requirements,
            skill_names,
        ) in enumerate(JOBS):
            client = clients[index % len(clients)]
            existing = Job.objects.filter(client=client, title=title).first()
            if existing:
                made.append(existing)
                continue
            job = create_job(
                client=client,
                title=title,
                category=categories[category],
                description=description,
                requirements=requirements,
                budget=D(budget),
                deadline=timezone.now() + timedelta(days=days),
                skills=[skills[n] for n in skill_names if n in skills],
                estimated_days=days,
                publish=True,
            )
            made.append(job)
        self.stdout.write(f"  {len(made)} jobs published, budgets reserved")
        return made

    def _proposals(self, jobs, freelancers):
        from apps.proposals.services import submit_proposal

        by_job = {}
        for job in jobs:
            already = list(job.proposals.all())
            if already:
                by_job[job.pk] = already
                continue
            wanted = {s.name for s in job.skills.all()}
            matching = [
                f
                for f in freelancers
                if wanted
                & {e.skill.name for e in f.freelancer_profile.skill_entries.all()}
            ] or freelancers[:3]

            for freelancer in matching[:3]:
                amount = (job.budget * D(random.uniform(0.82, 0.98))).quantize(
                    D("0.01")
                )
                proposal = submit_proposal(
                    job=job,
                    freelancer=freelancer,
                    cover_letter=(
                        f"I have delivered {random.randint(3, 9)} projects close to this "
                        f"brief. My plan: scope in week one, build in "
                        f"{max(job.estimated_days // 7, 1)} sprints with a demo at the end "
                        "of each, then hand over with documentation.\n\n"
                        "Happy to start immediately and work against milestones you approve."
                    ),
                    proposed_amount=amount,
                    estimated_days=job.estimated_days + random.randint(-3, 5),
                    deliverables=job.requirements,
                    revision_limit=random.choice([2, 3]),
                    additional_message="Available for a call any weekday.",
                )
                by_job.setdefault(job.pk, []).append(proposal)
        total = sum(len(v) for v in by_job.values())
        self.stdout.write(f"  {total} proposals")
        return by_job

    def _agree(self, job, proposals):
        """Proposal → negotiation → accepted agreement."""
        from apps.negotiations.services import accept_offer, open_negotiation

        proposal = proposals[job.pk][0]
        negotiation = open_negotiation(proposal=proposal, actor=job.client)
        return accept_offer(offer=negotiation.current_offer, actor=job.client)

    @transaction.atomic()
    def _to_negotiating(self, job, proposals):
        from apps.negotiations.services import open_negotiation, send_offer

        proposal = proposals[job.pk][0]
        negotiation = open_negotiation(proposal=proposal, actor=job.client)
        send_offer(
            negotiation=negotiation,
            sender=job.client,
            amount=(proposal.proposed_amount * D("0.92")).quantize(D("0.01")),
            deadline=timezone.now() + timedelta(days=job.estimated_days),
            deliverables=job.requirements,
            revision_limit=2,
            message="Close. Could you do it for a little less if we cut the last item?",
        )
        self.stdout.write(f"  “{job.title}” is mid-negotiation")

    def _to_active(self, job, proposals):
        from apps.escrow.services import fund_project, set_task_allocation
        from apps.tasks.services import create_task
        from apps.teams.services import create_team, invite_member

        agreement = self._agree(job, proposals)
        project = fund_project(agreement=agreement, client=job.client)

        # The hired freelancer builds the team — never the client.
        team = create_team(
            project=project,
            owner=project.freelancer,
            name=f"{project.title[:40]} team",
            objective="Deliver the agreed scope on time.",
        )
        others = [p.freelancer for p in proposals[job.pk][1:2]]
        for member in others:
            invite_member(team=team, inviter=project.freelancer, email=member.email)

        titles = [line for line in job.requirements.split("\n") if line.strip()]
        share = (project.final_price / max(len(titles), 1)).quantize(D("0.01"))
        made = []
        # Spread the task deadlines evenly up to the project deadline, never past
        # it — the service refuses a task due after the project is due.
        span = max((project.deadline - timezone.now()).days, len(titles))
        step = max(span // max(len(titles), 1), 1)
        for index, title in enumerate(titles):
            task = create_task(
                project=project,
                actor=project.freelancer,
                title=title.strip(),
                description=f"Deliver: {title.strip()}",
                assignee=project.freelancer,
                deadline=timezone.now() + timedelta(days=step * (index + 1)),
            )
            made.append(task)

        # Allocate so the total matches the escrow exactly, remainder on the last.
        allocated = D("0.00")
        for task in made[:-1]:
            set_task_allocation(task=task, actor=project.freelancer, amount=share)
            allocated += share
        set_task_allocation(
            task=made[-1],
            actor=project.freelancer,
            amount=project.final_price - allocated,
        )
        self.stdout.write(
            f"  “{job.title}” is active with a team and {len(made)} tasks"
        )

    def _to_completed(self, job, proposals, admin):
        from apps.escrow.services import fund_project, set_task_allocation
        from apps.payments.services import request_withdrawal
        from apps.projects.services import approve_project, mark_ready_for_review
        from apps.reviews.services import submit_review
        from apps.tasks.services import approve_task, create_task, submit_work

        agreement = self._agree(job, proposals)
        project = fund_project(agreement=agreement, client=job.client)

        titles = [line for line in job.requirements.split("\n") if line.strip()]
        share = (project.final_price / max(len(titles), 1)).quantize(D("0.01"))
        made, allocated = [], D("0.00")
        for title in titles:
            task = create_task(
                project=project,
                actor=project.freelancer,
                title=title.strip(),
                assignee=project.freelancer,
                deadline=min(timezone.now() + timedelta(days=7), project.deadline),
            )
            made.append(task)
        for task in made[:-1]:
            set_task_allocation(task=task, actor=project.freelancer, amount=share)
            allocated += share
        set_task_allocation(
            task=made[-1],
            actor=project.freelancer,
            amount=project.final_price - allocated,
        )

        for task in made:
            submit_work(
                task=task,
                actor=project.freelancer,
                message="Delivered and ready for review. Notes in the documentation link.",
                demo_url="https://demo.skillbridge.local()/preview",
                documentation="Setup, deployment and handover notes are included.",
            )
            approve_task(
                task=task, actor=project.client, note="Looks right, thank you."
            )

        mark_ready_for_review(
            project=project,
            actor=project.freelancer,
            note="Everything on the list is delivered.",
        )
        project = approve_project(
            project=project, actor=project.client, note="Good work throughout."
        )
        project.refresh_from_db()

        submit_review(
            project=project,
            reviewer=project.client,
            scores={
                "work_quality": 5,
                "communication": 5,
                "deadline_management": 4,
                "professionalism": 5,
            },
            comment="Clear communication and delivered what was agreed. Would hire again.",
            would_work_again=True,
        )
        submit_review(
            project=project,
            reviewer=project.freelancer,
            scores={
                "communication": 5,
                "requirement_clarity": 4,
                "professionalism": 5,
                "cooperation": 5,
                "payment_reliability": 5,
            },
            comment="Knew what they wanted and approved work promptly.",
            would_work_again=True,
        )

        request_withdrawal(
            user=project.freelancer,
            amount=D("5000"),
            payment_method="BKASH",
            account_number="01712345678",
        )
        self.stdout.write(f"  “{job.title}” completed, reviewed and part-withdrawn")

    def _settings_and_homepage(self):
        from apps.core.models import HomepageSection, SiteSetting

        for key, value, label, group in [
            ("support_email", "support@skillbridge.demo", "Support email", "general"),
            ("platform_name", "Skillbridge", "Platform name", "general"),
            ("review_window_hours", "48", "Review window (hours)", "money"),
        ]:
            SiteSetting.objects.get_or_create(
                key=key,
                defaults={
                    "value": value,
                    "label": label,
                    "group": group,
                    "is_public": True,
                },
            )

        HomepageSection.objects.get_or_create(
            slot=HomepageSection.Slot.HERO,
            defaults={
                "title": "Hire with the money already in escrow.",
                "subtitle": (
                    "Skillbridge holds the budget before the work starts and releases "
                    "it on terms both sides signed. Freelancers know they will be "
                    "paid. Clients know nothing moves until they have seen the work."
                ),
            },
        )
        self.stdout.write("  site settings and homepage content")
