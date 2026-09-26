"""Profile management (the signed-in user's own profile)."""

from django.urls import path

from apps.profiles import views

app_name = "profiles"

urlpatterns = [
    path("client/dashboard/", views.client_dashboard, name="client_dashboard"),
    path(
        "freelancer/dashboard/", views.freelancer_dashboard, name="freelancer_dashboard"
    ),
    path("client/edit/", views.edit_client, name="edit_client"),
    path("freelancer/edit/", views.edit_freelancer, name="edit_freelancer"),
    path("freelancer/skills/", views.edit_skills, name="edit_skills"),
    path("freelancer/experience/add/", views.add_experience, name="add_experience"),
    path(
        "freelancer/experience/<int:pk>/delete/",
        views.delete_experience,
        name="delete_experience",
    ),
    path("freelancer/education/add/", views.add_education, name="add_education"),
    path(
        "freelancer/education/<int:pk>/delete/",
        views.delete_education,
        name="delete_education",
    ),
]
