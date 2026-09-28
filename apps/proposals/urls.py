"""Proposal routes."""
from django.urls import path
from apps.proposals import views
app_name = "proposals"
urlpatterns = [
    path("mine/", views.my_proposals_view, name="my_proposals"),
    path("job/<uuid:job_id>/apply/", views.create_proposal, name="create"),
    path("job/<uuid:job_id>/", views.proposals_for_job_view, name="for_job"),
    path("<uuid:public_id>/", views.proposal_detail, name="detail"),
    path("<uuid:public_id>/withdraw/", views.withdraw_proposal_view, name="withdraw"),
    path("<uuid:public_id>/reject/", views.reject_proposal_view, name="reject"),
]
