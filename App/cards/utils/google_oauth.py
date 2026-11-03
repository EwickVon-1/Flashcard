import base64
import hashlib
import logging
import secrets
import string
from datetime import timedelta
from re import fullmatch
from urllib.parse import urlencode

import requests
from cards.models import GoogleToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

logger = logging.getLogger(__name__)

class GoogleOAuthService:
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    _PKCE_CHARACTERS = string.ascii_letters + string.digits + "-._~"
    _SESSION_KEY = "google_oauth_transactions"

    # Builds a url that requests google for authentication
    @classmethod
    def get_authorization_url(cls, request) -> str:
        verifier = cls._generate_code_verifier()
        challenge = cls._generate_code_challenge(verifier)
        state = secrets.token_urlsafe(32)  # CSRF protection 

        # Store these values in the session for later verification
        request.session[cls._SESSION_KEY] = {
                "verifier": verifier,
                "state": state,
        }
        # Creates a params dictionary, that feeds in all our options
        params = {
            "response_type": "code",
            "client_id": settings.GOOGLE_CLIENT_ID,
            "scope": settings.GOOGLE_SCOPE,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "access_type": "offline",
            "code_challenge_method": "S256",
            "code_challenge": challenge,
            "state": state,
        }
        # urlencode(params) encodes the dictionary params into a key=value url string
        return f"{cls.AUTH_URL}?{urlencode(params)}"



    # Validates the oAuth request and exchange auth code for tokens
    @classmethod
    def request_token(cls, request, code: str, returned_state: str) -> bool:
        if not isinstance(code, str) or not isinstance(returned_state, str):
            raise TypeError("code and returned_state must be a string")

        if not code or not returned_state:
            return False

        if not request.user.is_authenticated:
            return False

        transaction = request.session.get(cls._SESSION_KEY)

        if not isinstance(transaction, dict):
            return False

        state = transaction.get("state")
        verifier = transaction.get("verifier")

        if (
            not isinstance(state, str)
            or not isinstance(verifier, str)
            or not state
            or not verifier
            or not secrets.compare_digest(returned_state, state)
        ):
            return False

        # Explicitly remove the transaction from the session
        request.session.pop(cls._SESSION_KEY, None)

        # Builds the token exchange payload
        payload = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "code_verifier": verifier,
        }

        if (not payload.get("client_id") 
            or not payload.get("client_secret")
            or not payload.get("redirect_uri")):
            raise ImproperlyConfigured("client_id, client_secret and redirect_uri not supplied.")

        data = GoogleOAuthService._exchange_token(payload)
        if not data:
            return False

        access_token = data.get("access_token")
        expires_in = data.get("expires_in")

        expires_at = timezone.now() + timedelta(seconds=expires_in) # type: ignore
        defaults = {"access_token": access_token, "expires_at": expires_at}

        # Google may omit refresh tokens on subsequent authorization
        refresh_token = data.get("refresh_token")
        if isinstance(refresh_token, str) and refresh_token:
            defaults["refresh_token"] = refresh_token

        GoogleToken.objects.update_or_create(
            user=request.user,
            defaults=defaults,
        )
        return True

    # Tries to retrieve a valid token from a user, if the token is expired, we try to 
    # refresh it.
    @classmethod
    def get_valid_token(cls, user):
        try:
            token = user.google_token
        except GoogleToken.DoesNotExist:
            return ""

        # If the token is expired or no access token then we try to refresh it
        if (
            not token.access_token
            or token.expires_at <= timezone.now() + timedelta(seconds=60)
        ):            
            if not token.refresh_token:
                return ""

            if not cls._refresh_token(token):
                return ""

        return token.access_token

    # Refreshes the access_token if there exists a refresh token
    @classmethod
    def _refresh_token(cls, token: GoogleToken) -> bool:
        if not isinstance(token, GoogleToken):
            raise TypeError("token must be a valid GoogleToken")

        if not token.refresh_token:
            logger.warning("Google refresh token is missing")
            return False

        # Builds a valid refresh token payload
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
        }

        if (not payload.get("client_id") 
            or not payload.get("client_secret")):
                    raise ImproperlyConfigured("client_id and client_secret not supplied.")

        data = GoogleOAuthService._exchange_token(payload)
        if not data:
            return False

        access_token = data.get("access_token")
        expires_in = data.get("expires_in")

        token.access_token = access_token

        refresh_token = data.get("refresh_token")
        if isinstance(refresh_token, str) and refresh_token:
            token.refresh_token = refresh_token

        token.expires_at = timezone.now() + timedelta(seconds=expires_in)
        token.save(
                update_fields=[
                    "access_token",
                    "refresh_token",
                    "expires_at",
                    ]
                )
        return True

    # Generates a randomized string with a length of length
    @classmethod
    def _generate_code_verifier(cls, length: int = 128) -> str:
        if not isinstance(length, int) or isinstance(length, bool):
            raise TypeError("Length must be an integer")

        if length < 43 or length > 128:
            raise ValueError("Length must be between 43 and 128 characters")

        return "".join(secrets.choice(cls._PKCE_CHARACTERS) for _ in range(length))


    # Uses SHA256 Algorithim to encode a string code_verifier and converts it into base64
    @staticmethod
    def _generate_code_challenge(code_verifier: str) -> str:
        if not isinstance(code_verifier, str):
            raise TypeError("Code Verifier must be a string")

        # Validates if the string code_verifier is a valid code
        if not 43 <= len(code_verifier) <= 128:
            raise ValueError("Code Verifier must be between 43 and 128 characters")

        if not fullmatch(r"[A-Za-z0-9._~-]+", code_verifier):
            raise ValueError("Code verifier contains invalid characters")

        digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        return (
            base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
        )  # Removes = to make it safe to work with urls

    @classmethod
    def _exchange_token(cls, payload: dict) -> dict:
        if (not isinstance(payload, dict)):
            raise TypeError("payload should be of type dict")

        # Tries to make a post to Google
        try:
            response = requests.post(
                    cls.TOKEN_URL,
                    headers = {"Content-Type": "application/x-www-form-urlencoded"},
                    data=payload,
                    timeout=10
                    )

            if not response.ok:
                logger.warning(
                        "Google token exchange failed with HTTP status %s", response.status_code
                        )
                return {}

            data = response.json()

            # Validate data return type
            if not isinstance(data, dict):
                logger.warning("Google returned an invalid token response")
                return {}
        except requests.RequestException:
           logger.exception("Google token exchange request failed")
           return {}
        except ValueError:
            logger.warning("Google returned invalid JSON")
            return {} 

        access_token = data.get("access_token")
        expires_in = data.get("expires_in")

        # Validating the required response fields
        if (
            not isinstance(access_token, str)
            or not access_token
            or isinstance(expires_in, bool)
            or not isinstance(expires_in, int)
            or expires_in <= 0
        ):
            logger.warning("Google returned an invalid token response")
            return {}

        return data
