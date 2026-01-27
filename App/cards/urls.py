from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("register", views.register, name="register"),
    path("create", views.create, name="create"),
    path("<int:set_id>/<str:name>", views.set_view, name="set_view"),
    path("<int:set_id>/<str:name>/add", views.add, name="add"),
    path("<int:set_id>/<str:name>/edit", views.edit_view, name="edit"),
    path("<int:set_id>/<str:name>/edit/<int:card_id>", views.edit_card, name="edit_card"),
    path("<int:set_id>/<str:name>/study/", views.study, name="study")
]