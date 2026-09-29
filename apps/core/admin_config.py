from django.contrib.admin.apps import AdminConfig

class SkillbridgeAdminConfig(AdminConfig):
    default_site = 'apps.core.admin_site.SkillbridgeAdminSite'
