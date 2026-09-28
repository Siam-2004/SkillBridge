from django.urls import path
from apps.agreements import views
app_name = "agreements"
urlpatterns = [
    path("", views.my_contracts, name="my_contracts"),
    path("my-contracts/", views.my_contracts, name="my_contracts_alias"),
    path("<uuid:public_id>/", views.agreement_detail, name="detail"),
    path("<uuid:public_id>/submit/", views.submit_work_view, name="submit_work"),
    path("<uuid:public_id>/approve/", views.approve_and_pay_view, name="approve_and_pay"),
]
