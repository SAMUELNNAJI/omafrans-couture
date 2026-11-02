from django.urls import path

from . import views


app_name = "site"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("collections/", views.collection, name="collection"),
    path("contact/", views.contact, name="contact"),
    path("api/dressing-room/generate/", views.dressing_room_generate, name="dr_generate"),
]
