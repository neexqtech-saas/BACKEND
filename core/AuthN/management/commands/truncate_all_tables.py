from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import connection, transaction
from django.core.management.sql import sql_flush
from django.db import reset_queries


class Command(BaseCommand):
    help = 'Truncate all tables in the database (delete all data)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm that you want to delete all data',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    'WARNING: This will delete ALL data from ALL tables!\n'
                    'This action cannot be undone.\n'
                    'Use --confirm flag to proceed.'
                )
            )
            return

        self.stdout.write(self.style.WARNING('Starting truncation of all tables...'))
        
        # Get all models
        all_models = apps.get_models()
        
        # Filter out proxy models and unmanaged models
        models_to_truncate = [
            model for model in all_models 
            if not model._meta.proxy and model._meta.managed
        ]
        
        self.stdout.write(f'Found {len(models_to_truncate)} models to truncate')
        
        # Disable foreign key checks for SQLite
        with connection.cursor() as cursor:
            if connection.vendor == 'sqlite':
                cursor.execute("PRAGMA foreign_keys = OFF")
            
            try:
                with transaction.atomic():
                    # Delete data from each model - try multiple times to handle dependencies
                    max_attempts = 10
                    attempts = 0
                    
                    while attempts < max_attempts:
                        remaining_models = []
                        for model in models_to_truncate:
                            try:
                                # Check if table exists first
                                table_name = model._meta.db_table
                                cursor.execute(
                                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                                    [table_name]
                                )
                                if cursor.fetchone():
                                    if model.objects.all().exists():
                                        remaining_models.append(model)
                            except Exception:
                                # Skip models with issues
                                pass
                        
                        if not remaining_models:
                            break
                        
                        deleted_any = False
                        for model in remaining_models:
                            try:
                                count = model.objects.all().count()
                                if count > 0:
                                    # Use raw SQL delete to bypass foreign key constraints
                                    table_name = model._meta.db_table
                                    cursor.execute(f'DELETE FROM "{table_name}"')
                                    self.stdout.write(
                                        self.style.SUCCESS(
                                            f'[OK] Truncated {model._meta.app_label}.{model.__name__} ({count} records)'
                                        )
                                    )
                                    deleted_any = True
                            except Exception as e:
                                # Try to extract error message without Unicode issues
                                error_msg = str(e).encode('ascii', 'ignore').decode('ascii')
                                if 'no such table' not in error_msg.lower():
                                    self.stdout.write(
                                        self.style.ERROR(
                                            f'[ERROR] Error truncating {model._meta.app_label}.{model.__name__}: {error_msg[:100]}'
                                        )
                                    )
                        
                        if not deleted_any:
                            # If we couldn't delete anything, break to avoid infinite loop
                            break
                        
                        attempts += 1
                    
                    # Reset sequences for PostgreSQL (if needed)
                    if connection.vendor == 'postgresql':
                        for model in models_to_truncate:
                            if model._meta.auto_field:
                                sequence_sql = connection.ops.sequence_reset_sql([model])
                                if sequence_sql:
                                    cursor.execute(sequence_sql[0])
            
            finally:
                # Re-enable foreign key checks for SQLite
                if connection.vendor == 'sqlite':
                    cursor.execute("PRAGMA foreign_keys = ON")
        
        self.stdout.write(self.style.SUCCESS('\n[SUCCESS] All tables truncated successfully!'))

