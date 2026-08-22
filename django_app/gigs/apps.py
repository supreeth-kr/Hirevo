from django.apps import AppConfig

class GigsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gigs'
    
    def ready(self):
        """Register signal handlers when the app is ready"""
        try:
            from . import signals
        except ImportError as e:
            print(f"Could not import signals: {e}")
