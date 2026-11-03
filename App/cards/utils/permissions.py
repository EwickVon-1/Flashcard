from cards.models import Set
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest


def authenticate_user_permission(request : HttpRequest, flashcard_set : Set) -> None:
    if not request.user or not request.user.is_authenticated:
        raise PermissionDenied

    if request.user != flashcard_set.owner:
        raise PermissionDenied
