from django.urls import path
from . import views

app_name = 'settings'

urlpatterns = [
    path('', views.settings_account_view, name='index'),
    path('account/', views.settings_account_view, name='account'),
    path('profile/', views.settings_profile_view, name='profile'),
    path('privacy/', views.settings_privacy_view, name='privacy'),
    path('notifications/', views.settings_notifications_view, name='notifications'),
    path('appearance/', views.settings_appearance_view, name='appearance'),
    path('language/', views.settings_language_view, name='language'),
    path('security/', views.settings_security_view, name='security'),
    path('help/', views.settings_help_view, name='help'),
    path('account/delete/', views.settings_delete_account_view, name='delete_account'),
]
