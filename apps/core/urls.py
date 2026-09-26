"""Public content pages."""

from django.urls import path

from apps.core import views

app_name = "core"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("search/", views.search, name="search"),
    path("categories/", views.categories, name="categories"),
    path("jobs/", views.jobs, name="jobs"),
    path("about/", views.about, name="about"),
    path("how-it-works/", views.how_it_works, name="how_it_works"),
    path("help/", views.help_centre, name="help"),
    path("terms/", views.terms, name="terms"),
    path("privacy/", views.privacy, name="privacy"),
    path("contact/", views.contact, name="contact"),
]
