"""
Django Management Command to Load Professional Tax Rules/Slabs
Loads state-wise professional tax slabs for India

Usage: python manage.py load_professional_tax_slabs
       python manage.py load_professional_tax_slabs --clear (to clear existing data first)
"""

from django.core.management.base import BaseCommand
from decimal import Decimal
from PayrollSystem.models import ProfessionalTaxRule


class Command(BaseCommand):
    help = 'Load Professional Tax Rules/Slabs for Indian states'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing professional tax rules before loading',
        )

    def handle(self, *args, **options):
        if options['clear']:
            deleted_count = ProfessionalTaxRule.objects.all().delete()[0]
            self.stdout.write(
                self.style.WARNING(f'Deleted {deleted_count} existing professional tax rules.')
            )

        # Professional Tax Rules Data
        # Format: (state_id, state_name, salary_from, salary_to, tax_amount, applicable_month)
        # applicable_month: None = All Months, 1-12 = Specific month
        
        pt_rules_data = [
            # Maharashtra Professional Tax Slabs
            (1, 'Maharashtra', Decimal('0'), Decimal('5000'), Decimal('0'), None),
            (1, 'Maharashtra', Decimal('5001'), Decimal('10000'), Decimal('150'), None),
            (1, 'Maharashtra', Decimal('10001'), Decimal('15000'), Decimal('175'), None),
            (1, 'Maharashtra', Decimal('15001'), None, Decimal('200'), None),
            
            # Karnataka Professional Tax Slabs
            (2, 'Karnataka', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (2, 'Karnataka', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (2, 'Karnataka', Decimal('15001'), None, Decimal('200'), None),
            
            # West Bengal Professional Tax Slabs
            (3, 'West Bengal', Decimal('0'), Decimal('10000'), Decimal('110'), None),
            (3, 'West Bengal', Decimal('10001'), Decimal('15000'), Decimal('130'), None),
            (3, 'West Bengal', Decimal('15001'), Decimal('25000'), Decimal('150'), None),
            (3, 'West Bengal', Decimal('25001'), None, Decimal('200'), None),
            
            # Tamil Nadu Professional Tax Slabs
            (4, 'Tamil Nadu', Decimal('0'), Decimal('21000'), Decimal('0'), None),
            (4, 'Tamil Nadu', Decimal('21001'), None, Decimal('2500'), None),
            
            # Gujarat Professional Tax Slabs
            (5, 'Gujarat', Decimal('0'), Decimal('5000'), Decimal('0'), None),
            (5, 'Gujarat', Decimal('5001'), Decimal('20000'), Decimal('200'), None),
            (5, 'Gujarat', Decimal('20001'), None, Decimal('300'), None),
            
            # Andhra Pradesh Professional Tax Slabs
            (6, 'Andhra Pradesh', Decimal('0'), Decimal('15000'), Decimal('0'), None),
            (6, 'Andhra Pradesh', Decimal('15001'), Decimal('20000'), Decimal('150'), None),
            (6, 'Andhra Pradesh', Decimal('20001'), None, Decimal('200'), None),
            
            # Telangana Professional Tax Slabs
            (7, 'Telangana', Decimal('0'), Decimal('15000'), Decimal('0'), None),
            (7, 'Telangana', Decimal('15001'), Decimal('20000'), Decimal('150'), None),
            (7, 'Telangana', Decimal('20001'), None, Decimal('200'), None),
            
            # Kerala Professional Tax Slabs
            (8, 'Kerala', Decimal('0'), Decimal('1999'), Decimal('0'), None),
            (8, 'Kerala', Decimal('2000'), Decimal('2999'), Decimal('20'), None),
            (8, 'Kerala', Decimal('3000'), Decimal('4999'), Decimal('30'), None),
            (8, 'Kerala', Decimal('5000'), Decimal('7499'), Decimal('50'), None),
            (8, 'Kerala', Decimal('7500'), Decimal('9999'), Decimal('75'), None),
            (8, 'Kerala', Decimal('10000'), Decimal('12499'), Decimal('100'), None),
            (8, 'Kerala', Decimal('12500'), Decimal('16666'), Decimal('125'), None),
            (8, 'Kerala', Decimal('16667'), None, Decimal('200'), None),
            
            # Madhya Pradesh Professional Tax Slabs
            (9, 'Madhya Pradesh', Decimal('0'), Decimal('18000'), Decimal('0'), None),
            (9, 'Madhya Pradesh', Decimal('18001'), Decimal('30000'), Decimal('150'), None),
            (9, 'Madhya Pradesh', Decimal('30001'), None, Decimal('200'), None),
            
            # Rajasthan Professional Tax Slabs
            (10, 'Rajasthan', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (10, 'Rajasthan', Decimal('10001'), Decimal('20000'), Decimal('150'), None),
            (10, 'Rajasthan', Decimal('20001'), None, Decimal('200'), None),
            
            # Odisha Professional Tax Slabs
            (11, 'Odisha', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (11, 'Odisha', Decimal('10001'), Decimal('15000'), Decimal('100'), None),
            (11, 'Odisha', Decimal('15001'), None, Decimal('200'), None),
            
            # Punjab Professional Tax Slabs
            (12, 'Punjab', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (12, 'Punjab', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (12, 'Punjab', Decimal('15001'), None, Decimal('200'), None),
            
            # Haryana Professional Tax Slabs
            (13, 'Haryana', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (13, 'Haryana', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (13, 'Haryana', Decimal('15001'), None, Decimal('200'), None),
            
            # Uttar Pradesh Professional Tax Slabs
            (14, 'Uttar Pradesh', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (14, 'Uttar Pradesh', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (14, 'Uttar Pradesh', Decimal('15001'), None, Decimal('200'), None),
            
            # Bihar Professional Tax Slabs
            (15, 'Bihar', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (15, 'Bihar', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (15, 'Bihar', Decimal('15001'), None, Decimal('200'), None),
            
            # Jharkhand Professional Tax Slabs
            (16, 'Jharkhand', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (16, 'Jharkhand', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (16, 'Jharkhand', Decimal('15001'), None, Decimal('200'), None),
            
            # Chhattisgarh Professional Tax Slabs
            (17, 'Chhattisgarh', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (17, 'Chhattisgarh', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (17, 'Chhattisgarh', Decimal('15001'), None, Decimal('200'), None),
            
            # Assam Professional Tax Slabs
            (18, 'Assam', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (18, 'Assam', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (18, 'Assam', Decimal('15001'), None, Decimal('200'), None),
            
            # Delhi Professional Tax Slabs (No PT, but adding for completeness)
            (19, 'Delhi', Decimal('0'), None, Decimal('0'), None),
            
            # Goa Professional Tax Slabs
            (20, 'Goa', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (20, 'Goa', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (20, 'Goa', Decimal('15001'), None, Decimal('200'), None),
            
            # Himachal Pradesh Professional Tax Slabs
            (21, 'Himachal Pradesh', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (21, 'Himachal Pradesh', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (21, 'Himachal Pradesh', Decimal('15001'), None, Decimal('200'), None),
            
            # Uttarakhand Professional Tax Slabs
            (22, 'Uttarakhand', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (22, 'Uttarakhand', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (22, 'Uttarakhand', Decimal('15001'), None, Decimal('200'), None),
            
            # Meghalaya Professional Tax Slabs
            (23, 'Meghalaya', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (23, 'Meghalaya', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (23, 'Meghalaya', Decimal('15001'), None, Decimal('200'), None),
            
            # Manipur Professional Tax Slabs
            (24, 'Manipur', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (24, 'Manipur', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (24, 'Manipur', Decimal('15001'), None, Decimal('200'), None),
            
            # Tripura Professional Tax Slabs
            (25, 'Tripura', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (25, 'Tripura', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (25, 'Tripura', Decimal('15001'), None, Decimal('200'), None),
            
            # Mizoram Professional Tax Slabs
            (26, 'Mizoram', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (26, 'Mizoram', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (26, 'Mizoram', Decimal('15001'), None, Decimal('200'), None),
            
            # Nagaland Professional Tax Slabs
            (27, 'Nagaland', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (27, 'Nagaland', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (27, 'Nagaland', Decimal('15001'), None, Decimal('200'), None),
            
            # Arunachal Pradesh Professional Tax Slabs
            (28, 'Arunachal Pradesh', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (28, 'Arunachal Pradesh', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (28, 'Arunachal Pradesh', Decimal('15001'), None, Decimal('200'), None),
            
            # Sikkim Professional Tax Slabs
            (29, 'Sikkim', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (29, 'Sikkim', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (29, 'Sikkim', Decimal('15001'), None, Decimal('200'), None),
            
            # Jammu and Kashmir Professional Tax Slabs
            (30, 'Jammu and Kashmir', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (30, 'Jammu and Kashmir', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (30, 'Jammu and Kashmir', Decimal('15001'), None, Decimal('200'), None),
            
            # Ladakh Professional Tax Slabs
            (31, 'Ladakh', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (31, 'Ladakh', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (31, 'Ladakh', Decimal('15001'), None, Decimal('200'), None),
            
            # Puducherry Professional Tax Slabs
            (32, 'Puducherry', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (32, 'Puducherry', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (32, 'Puducherry', Decimal('15001'), None, Decimal('200'), None),
            
            # Chandigarh Professional Tax Slabs
            (33, 'Chandigarh', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (33, 'Chandigarh', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (33, 'Chandigarh', Decimal('15001'), None, Decimal('200'), None),
            
            # Daman and Diu Professional Tax Slabs
            (34, 'Daman and Diu', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (34, 'Daman and Diu', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (34, 'Daman and Diu', Decimal('15001'), None, Decimal('200'), None),
            
            # Dadra and Nagar Haveli Professional Tax Slabs
            (35, 'Dadra and Nagar Haveli', Decimal('0'), Decimal('10000'), Decimal('0'), None),
            (35, 'Dadra and Nagar Haveli', Decimal('10001'), Decimal('15000'), Decimal('150'), None),
            (35, 'Dadra and Nagar Haveli', Decimal('15001'), None, Decimal('200'), None),
        ]

        created_count = 0
        updated_count = 0

        for state_id, state_name, salary_from, salary_to, tax_amount, applicable_month in pt_rules_data:
            rule, created = ProfessionalTaxRule.objects.update_or_create(
                state_id=state_id,
                state_name=state_name,
                salary_from=salary_from,
                salary_to=salary_to,
                defaults={
                    'tax_amount': tax_amount,
                    'applicable_month': applicable_month,
                    'is_active': True,
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully loaded Professional Tax Rules!\n'
                f'Created: {created_count} rules\n'
                f'Updated: {updated_count} rules\n'
                f'Total: {created_count + updated_count} rules'
            )
        )
        
        # Show summary by state
        state_summary = {}
        for rule in ProfessionalTaxRule.objects.filter(is_active=True).order_by('state_name', 'salary_from'):
            if rule.state_name not in state_summary:
                state_summary[rule.state_name] = 0
            state_summary[rule.state_name] += 1
        
        self.stdout.write('\nSummary by State:')
        for state_name, count in sorted(state_summary.items()):
            self.stdout.write(f'  {state_name}: {count} slab(s)')
