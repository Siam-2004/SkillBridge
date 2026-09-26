"""The Django admin, branded as the Skillbridge operations console.

There is no separate admin application: the specification makes Django's own
admin the primary interface for every operator task, so the work goes into
configuring it well rather than rebuilding it.
"""

from django.contrib.admin import AdminSite


class SkillbridgeAdminSite(AdminSite):
    site_title = "Skillbridge admin"
    site_header = "Skillbridge operations"
    index_title = "Platform administration"
