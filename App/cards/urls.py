from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("register", views.register, name="register"),
    path("google/auth", views.google_auth, name="google_auth"),
    path("accounts/google/login/callback", views.google_callback, name="google_callback"),
    path("google/disconnect", views.google_disconnect, name="google_disconnect"),
    path("google/create", views.google_create_set, name="google_create_set"),
    path("create", views.create, name="create"),
    path("music/search", views.music_search, name="music_search"),
    path("search", views.search, name="search"),
    path("stats", views.stats, name="stats"),
    path("<int:set_id>/<str:name>", views.set_view, name="set_view"),
    path("<int:set_id>/<str:name>/add", views.add, name="add"),
    path("<int:set_id>/<str:name>/delete_set", views.delete_set, name="delete_set"),
    path("<int:set_id>/<str:name>/edit", views.edit_view, name="edit"),
    path("<int:set_id>/<str:name>/edit/<int:card_id>", views.edit_card, name="edit_card"),
    path("<int:set_id>/<str:name>/edit/<int:card_id>/delete", views.delete_card, name="delete_card"),
    path("<int:set_id>/<str:name>/save", views.save_set, name="save_set"),
    path("<int:set_id>/<str:name>/study", views.study, name="study"),
    path("<int:set_id>/<str:name>/stats", views.stats, name="set_stats"),
]
