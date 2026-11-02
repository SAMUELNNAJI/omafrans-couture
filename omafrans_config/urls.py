from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("auth_app.urls")),
    path(
        "accounts/",
        include(("auth_app.urls", "auth"), namespace="legacy-auth"),
    ),
    path("dashboard/", include("dashboard_app.urls")),
    path("", include("site_app.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
