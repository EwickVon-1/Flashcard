import base64
from datetime import timedelta
import secrets
import string
import hashlib

import requests
from django.conf import settings
from django.utils import timezone
from urllib.parse import urlencode

from cards.models import GoogleToken

POSSIBLE = string.ascii_letters + string.digits + "-._~"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

def generate_code_verifier(length=128):
    if length < 43 or length > 128:
        raise ValueError("Length must be between 43 and 128 characters")
    
    return "".join(secrets.choice(POSSIBLE) for _ in range(length))

def generate_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

def get_auth_url(request) -> str:
    verifier = generate_code_verifier()
    challenge = generate_code_challenge(verifier)

    # Store the verifier in the session for later use
    request.session['google_code_verifier'] = verifier

    params = {
        "response_type": "code",
        "client_id": settings.GOOGLE_CLIENT_ID,
        "scope": settings.GOOGLE_SCOPE,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "access_type": "offline",
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "prompt": "consent"
    }
    return f"{AUTH_URL}?{urlencode(params)}"
    

def request_token(request, code: str) -> bool:
    verifier = request.session.pop('google_code_verifier', None)
    if not verifier:
        return False
    
    payload = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "code_verifier": verifier
    }

    response = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=payload
    )

    if response.status_code != 200:
        return False
    
    data = response.json()
    expires_in = timezone.now() + timedelta(seconds=data["expires_in"])

    GoogleToken.objects.update_or_create(
        user=request.user,
        defaults={
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_at": expires_in
        }
    )
    return True

def refresh_token(token: GoogleToken) -> bool:
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": token.refresh_token,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
    }

    response = requests.post(
        TOKEN_URL,
        headers= {"Content-Type": "application/x-www-form-urlencoded"},
        data=payload
    )

    if response.status_code != 200:
        return False
    
    data = response.json()
    token.access_token = data["access_token"]
    if "refresh_token" in data:
        token.refresh_token = data["refresh_token"]
    token.expires_at = timezone.now() + timedelta(seconds=data["expires_in"])
    token.save()
    return True

def get_valid_token(user):
    try:
        token = user.google_token
    except GoogleToken.DoesNotExist:
        return None
    
    if token.is_expired():
        if not refresh_token(token):
            return None
    
    return token.access_token

