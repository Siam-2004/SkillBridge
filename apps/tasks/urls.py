from django.urls import path
from apps.tasks import views

app_name = 'tasks'

urlpatterns = [
    path('project/<uuid:project_public_id>/create/', views.task_create, name='create'),
    path('<int:task_id>/status/', views.task_status_update, name='status'),
    path('<int:task_id>/subtasks/create/', views.subtask_create, name='subtask_create'),
    path('subtasks/<int:subtask_id>/assign/', views.subtask_assign, name='subtask_assign'),
    path('subtasks/<int:subtask_id>/status/', views.subtask_status_update, name='subtask_status'),
    path('<int:task_id>/files/upload/', views.task_file_upload, name='file_upload'),
    path('<int:task_id>/files/<int:file_id>/download/', views.task_file_download, name='file_download'),
]
