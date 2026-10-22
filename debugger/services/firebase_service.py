import logging
import json
from django.conf import settings
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

logger = logging.getLogger(__name__)

class FirebaseService:
    """Service to verify Firebase Authentication tokens and interact with Firestore."""

    def __init__(self):
        self.project_id = getattr(settings, 'FIREBASE_PROJECT_ID', 'sutracode-11188')
        self.http_request = google_requests.Request()

    def verify_token(self, auth_header: str) -> dict:
        """
        Verifies the Firebase ID token from 'Authorization: Bearer <token>' header.
        Returns a dict with user information: {'uid', 'email', 'name', 'picture', 'is_authenticated': True}
        If invalid or missing, returns guest user information.
        """
        if not auth_header:
            return self._get_guest_user()

        token = auth_header.strip()
        if token.lower().startswith('bearer '):
            token = token[7:].strip()

        if not token:
            return self._get_guest_user()

        try:
            # Verify the ID token against Google's public certs for this Firebase project
            decoded = google_id_token.verify_firebase_token(
                token,
                self.http_request,
                audience=self.project_id
            )
            return {
                'uid': decoded.get('sub') or decoded.get('user_id'),
                'email': decoded.get('email', ''),
                'name': decoded.get('name', decoded.get('email', 'Developer')),
                'picture': decoded.get('picture', ''),
                'is_authenticated': True,
            }
        except Exception as e:
            logger.warning("Firebase ID token verification failed: %s. Falling back to guest.", str(e))
            return self._get_guest_user()

    def _get_guest_user(self) -> dict:
        """Default anonymous developer identity when not signed in with Firebase."""
        return {
            'uid': 'guest_developer',
            'email': 'guest@sutracode.local',
            'name': 'Guest Developer',
            'picture': '',
            'is_authenticated': False,
        }

# Singleton instance
firebase_service = FirebaseService()
