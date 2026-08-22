from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = []

# In development, serve application assets before the catch-all marketplace
# routes.  Otherwise ``path('', include(...))`` handles /static/* first and
# returns the application's 404 page instead of the requested CSS or images.
if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.BASE_DIR / 'marketplace' / 'static',
    )

urlpatterns += [
    path('admin/', admin.site.urls),
    path('', include('marketplace.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'marketplace.views.custom_404_view'
handler403 = 'marketplace.views.custom_403_view'
handler500 = 'marketplace.views.custom_500_view'
