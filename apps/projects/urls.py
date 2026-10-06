from django.urls import path
from apps.projects import views

app_name = 'projects'

urlpatterns = [
    path('', views.project_list, name='list'),
    path('<uuid:public_id>/', views.project_detail, name='detail'),
    path('<uuid:public_id>/team/create/', views.create_team, name='team_create'),
    path('<uuid:public_id>/team/invite/', views.invite_member, name='team_invite'),
    path('invitations/<int:invitation_id>/respond/', views.respond_invitation, name='invitation_respond'),
    path('<uuid:public_id>/files/upload/', views.upload_file, name='file_upload'),
    path('<uuid:public_id>/files/<int:file_id>/download/', views.download_file, name='file_download'),
    path('<uuid:public_id>/comments/add/', views.add_comment, name='comment_add'),
    path('<uuid:public_id>/chat/', views.project_chat_view, name='chat'),
    path('<uuid:public_id>/chat/poll/', views.project_chat_poll, name='chat_poll'),
    path('<uuid:public_id>/chat/send/', views.project_chat_send, name='chat_send'),
]
