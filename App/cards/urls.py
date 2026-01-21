from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("register", views.register, name="register"),
    path("create", views.create, name="create"),
    path("<int:id>/<str:name>", views.set, name="set"),
    path("<int:id>/<str:name>/edit", views.edit, name="edit"),
    path("<int:set_id>/<str:name>/study/<int:card_id>", views.study, name="study")
]