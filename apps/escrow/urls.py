"""Escrow routes."""

from django.urls import path

from apps.escrow import views

app_name = "escrow"

urlpatterns = [
    path("<uuid:public_id>/", views.detail, name="detail"),
]
