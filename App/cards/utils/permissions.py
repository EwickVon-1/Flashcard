from django.shortcuts import redirect
from django.contrib import messages


def authenticate_user_permission(request, flashcard_set, redirect_view, set_id, name):
    if request.user != flashcard_set.owner:
        messages.error(request, f"You do not have permission to access this flashcard set.")
        return redirect(redirect_view, set_id=set_id)
