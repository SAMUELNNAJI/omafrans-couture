from django.urls import path

from .views import (
    CollectionCreateView,
    CollectionDeleteView,
    CollectionUpdateView,
    DashboardView,
    SiteSettingsUpdateView,
)


app_name = "dashboard"

urlpatterns = [
    path("", DashboardView.as_view(), name="index"),
    path("collections/add/", CollectionCreateView.as_view(), name="collection-add"),
    path(
        "collections/<int:pk>/edit/",
        CollectionUpdateView.as_view(),
        name="collection-edit",
    ),
    path(
        "collections/<int:pk>/delete/",
        CollectionDeleteView.as_view(),
        name="collection-delete",
    ),
    path("settings/", SiteSettingsUpdateView.as_view(), name="settings"),
]
