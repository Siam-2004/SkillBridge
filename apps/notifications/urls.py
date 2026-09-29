from django.urls import path
from apps.notifications import views
app_name = 'notifications'
urlpatterns = [path('', views.notification_list, name='list'), path('read-all/', views.read_all, name='read_all'), path('<uuid:public_id>/read/', views.read_one, name='read_one')]
