import itertools
from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django.utils import timezone

from cards.models import GoogleToken

# Shared settings for Google OAuth Tests
GOOGLE_SETTINGS = {
    "GOOGLE_CLIENT_ID":"test-client-id",
    "GOOGLE_CLIENT_SECRET": "test-client-secret",
    "GOOGLE_SCOPE":"youtube.readonly",
    "GOOGLE_REDIRECT_URI":"http://localhost:8000/auth/callback/",
    }

# Avoid expensive password hashing in tests
FAST_PASSWORD_HASHER = override_settings(
    PASSWORD_HASHERS=[
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]
)

# Make usernames unique using a counter
_user_counter = itertools.count(1)

def make_user(**overrides):
    # Makes a user with defaults and allows overrides
    User = get_user_model()

    counter = next(_user_counter)

    defaults = {
            "username": f"oauth-test-user-{counter}",
            "email": f"oauth-test-{counter}-@email.com",
            "password": "test-password"
            }

    defaults.update(overrides)

    return User.objects.create_user(**defaults) # type: ignore

def make_google_token(user, **overrides):
    defaults = {
            "user": user,
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_at": timezone.now() + timedelta(seconds=3600)
            }

    defaults.update(overrides)

    return GoogleToken.objects.create(**defaults)

def fake_response(json=None, ok=True, status=200, json_error=None):
    # Builds a mock response
    response = Mock()

    response.ok = ok
    response.status_code = status

    if json_error:
        response.json.side_effect = json_error
    else:
        response.json.return_value = json or {}

    return response

def make_request(user = None, method="get", with_session=False, path="/"):
    # Builds a request with request factory
    factory = RequestFactory()

    request_method = getattr(factory, method.lower())
    request = request_method(path)

    if with_session:
        middleware = SessionMiddleware(lambda request: HttpResponse())
        middleware.process_request(request)
        request.session.save()

    if user is not None:
        request.user = user

    return request

class FrozenTime:
    # Helper class for controlling Django's timezones

    def __init__(self, frozen_time = None):
        self.frozen_time = frozen_time or timezone.now()
        self.patch = patch(
                "django.utils.timezone.now",
                return_value = self.frozen_time
                )

    def __enter__(self):
        self.patch.start()
        return self.frozen_time

    def __exit__(self, exc_type, exc_value, traceback):
        self.patch.stop()

class NetworkTripwire:
    # Prevents accidental calls to Youtube when running tests

    # Makes sure we don't burn tokens when running tests

    def __enter__(self):
        self.patches = [
                patch("requests.get", side_effect=AssertionError("Unexpected Network Request")),
                patch("requests.post", side_effect=AssertionError("Unexpected Network Request")),
                patch("googleapiclient.discovery.build", side_effect=AssertionError("Unexpected Google API call"))
                ]

        for mock in self.patches:
            mock.start()

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        for mock in self.patches:
            mock.stop()

