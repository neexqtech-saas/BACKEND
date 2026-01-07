from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Delete ALL data from ALL tables using raw SQL (more aggressive)'

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

        self.stdout.write(self.style.WARNING('Starting aggressive deletion of all data...'))
        
        with connection.cursor() as cursor:
            # Disable foreign key checks
            if connection.vendor == 'sqlite':
                cursor.execute("PRAGMA foreign_keys = OFF")
            
            try:
                # Get all table names
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                tables = [row[0] for row in cursor.fetchall()]
                
                self.stdout.write(f'Found {len(tables)} tables to truncate')
                
                deleted_count = 0
                for table in tables:
                    try:
                        # Get count before deletion
                        cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                        count = cursor.fetchone()[0]
                        
                        if count > 0:
                            # Delete all data
                            cursor.execute(f'DELETE FROM "{table}"')
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'[OK] Deleted {count} records from {table}'
                                )
                            )
                            deleted_count += 1
                        else:
                            self.stdout.write(f'  Skipped {table} (already empty)')
                    except Exception as e:
                        error_msg = str(e).encode('ascii', 'ignore').decode('ascii')
                        self.stdout.write(
                            self.style.ERROR(
                                f'[ERROR] Error deleting from {table}: {error_msg[:100]}'
                            )
                        )
                
                # Reset auto-increment sequences for SQLite
                for table in tables:
                    try:
                        cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
                    except:
                        pass  # Some tables don't have sequences
                
                self.stdout.write(self.style.SUCCESS(f'\n[SUCCESS] Deleted data from {deleted_count} tables!'))
                
            finally:
                # Re-enable foreign key checks
                if connection.vendor == 'sqlite':
                    cursor.execute("PRAGMA foreign_keys = ON")

