"""Admin application config.

Kept out of ``apps.py`` because Django treats every ``AppConfig`` subclass in
that module as a candidate default for the app itself, and this one configures
``django.contrib.admin`` rather than ``apps.core``.
"""

from django.contrib.admin.apps import AdminConfig


class SkillbridgeAdminConfig(AdminConfig):
    default_site = "apps.core.admin_site.SkillbridgeAdminSite"
