from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.inbox_view, name='inbox'),
    path('new/<str:username>/', views.start_conversation_view, name='start_conversation'),
    path('<int:conversation_id>/', views.conversation_view, name='conversation'),
    path('<int:conversation_id>/read/', views.mark_conversation_read_view, name='mark_read'),
    path('<int:conversation_id>/poll/', views.poll_messages_view, name='poll_messages'),
    path('message/<int:message_id>/react/', views.message_react_view, name='react_message'),
    path('message/<int:message_id>/delete/', views.delete_message_view, name='delete_message'),
]
