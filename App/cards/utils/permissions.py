from django.core.exceptions import PermissionDenied


def authenticate_user_permission(request, flashcard_set):
    if request.user != flashcard_set.owner:
        raise PermissionDenied
