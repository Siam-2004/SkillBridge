"""The public people directory.

Two prefixes share this module: ``/freelancers/`` and ``/clients/``. Keeping
them together means the two public profile pages cannot drift apart.
"""

from django.urls import path

from apps.profiles import views

app_name = "directory"

urlpatterns = [
    path("", views.freelancer_list, name="freelancer_list"),
    path("<str:username>/", views.freelancer_public, name="freelancer_public"),
]
