from django.urls import path
from apps.negotiations import views
app_name = 'negotiations'
urlpatterns = [path('', views.negotiation_list, name='list'), path('open/<uuid:proposal_id>/', views.open_room, name='open'), path('<uuid:public_id>/', views.room, name='room'), path('<uuid:public_id>/counter/', views.counter, name='counter'), path('<uuid:public_id>/accept/', views.accept, name='accept'), path('<uuid:public_id>/reject/', views.reject, name='reject'), path('<uuid:public_id>/cancel/', views.cancel, name='cancel')]
