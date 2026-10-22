from django.conf import settings
import json

def firebase_settings(request):
    """Expose Firebase configuration to all Django templates."""
    return {
        'FIREBASE_CONFIG': settings.FIREBASE_CONFIG,
        'FIREBASE_CONFIG_JSON': json.dumps(settings.FIREBASE_CONFIG),
    }
