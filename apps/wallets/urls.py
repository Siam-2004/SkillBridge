"""Wallet routes."""

from django.urls import path

from apps.wallets import views

app_name = "wallets"

urlpatterns = [
    path("", views.wallet, name="wallet"),
    path("deposit/", views.deposit_view, name="deposit"),
    path("withdraw/", views.withdraw_view, name="withdraw"),
    path("transactions/", views.transactions, name="transactions"),
]
