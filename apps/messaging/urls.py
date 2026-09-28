"""Conversation routes."""
from django.urls import path
from apps.messaging import views
app_name = "messaging"
urlpatterns = [
    path("", views.conversation_list, name="list"),
    path("job/<uuid:job_id>/start/", views.start_job_conversation, name="start_job"),
    path("<uuid:public_id>/", views.detail, name="detail"),
    path("<uuid:public_id>/send/", views.send, name="send"),
    path("<uuid:public_id>/poll/", views.poll, name="poll"),
]
