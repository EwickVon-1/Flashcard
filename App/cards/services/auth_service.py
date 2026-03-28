from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()

def register_user(username, email, password):
    try:
        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()
        return user, None
    except IntegrityError:
        return None, "Username already taken"
