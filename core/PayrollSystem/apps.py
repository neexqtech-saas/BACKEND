from django.apps import AppConfig


class PayrollsystemConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'PayrollSystem'
    
    def ready(self):
        """Import signals when app is ready"""
        import PayrollSystem.signals
