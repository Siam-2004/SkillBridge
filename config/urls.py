"""Project URLs.

One URLconf for the whole site. Each app owns its routes under a prefix and
declares its own ``app_name``, so templates reverse names like
``marketplace:job_detail`` without knowing where the app is mounted.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Public pages
    path("", core_views.home, name="home"),
    path("", include("apps.core.urls")),
    # Identity
    path("accounts/", include("apps.accounts.urls")),
    path("profiles/", include("apps.profiles.urls")),
    # People & Portfolios
    path("freelancers/", include("apps.profiles.directory_urls")),
    path("clients/", include("apps.profiles.client_urls")),
    path("portfolios/", include("apps.portfolios.urls")),
    # Money
    path("wallet/", include("apps.wallets.urls")),
]

handler403 = "apps.core.views.error_403"
handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
