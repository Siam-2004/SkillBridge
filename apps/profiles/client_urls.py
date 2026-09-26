"""Public client profiles, mounted at ``/clients/``."""

from django.urls import path

from apps.profiles import views

app_name = "clients"

urlpatterns = [
    path("<str:username>/", views.client_public, name="client_public"),
]
