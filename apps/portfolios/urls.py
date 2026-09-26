"""Portfolio routes."""

from django.urls import path

from apps.portfolios import views

app_name = "portfolios"

urlpatterns = [
    path("mine/", views.my_portfolio, name="my_portfolio"),
    path("new/", views.create, name="create"),
    path("of/<str:username>/", views.public_list, name="public_list"),
    path("project/<uuid:project_id>/import/", views.from_project, name="from_project"),
    path("<uuid:public_id>/", views.detail, name="detail"),
    path("<uuid:public_id>/edit/", views.edit, name="edit"),
    path("<uuid:public_id>/delete/", views.delete, name="delete"),
    path("<uuid:public_id>/media/", views.add_media, name="add_media"),
]
