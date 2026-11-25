from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),  # Built-in language switching
    path('accounts/', include('accounts.urls')),
    path('messages/', include('chat.urls')),          # Messaging & Direct Chat
    path('settings/', include('accounts.settings_urls')), # Dedicated Settings Hub
    path('notifications/', include('notifications.urls')),
    path('', include('posts.urls')),                  # Feed, Posts, Reels, Saved
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()
    if settings.STATICFILES_DIRS:
        urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    if settings.STATIC_ROOT and settings.STATIC_ROOT.exists():
        urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
