from django.urls import path
from apps.marketplace import views
app_name = 'marketplace'
urlpatterns = [path('', views.job_list, name='job_list'), path('post/', views.job_create, name='job_create'), path('mine/', views.my_jobs, name='my_jobs'), path('saved/', views.saved_jobs, name='saved_jobs'), path('<uuid:public_id>/', views.job_detail_view, name='job_detail'), path('<uuid:public_id>/edit/', views.job_edit, name='job_edit'), path('<uuid:public_id>/publish/', views.job_publish, name='job_publish'), path('<uuid:public_id>/cancel/', views.job_cancel, name='job_cancel'), path('<uuid:public_id>/save/', views.job_save_toggle, name='job_save')]
