from django.core.management.base import BaseCommand
from tickets.sla_service import check_sla_breaches


class Command(BaseCommand):
    help = 'Scan open tickets for SLA breaches and send notifications.'

    def handle(self, *args, **options):
        count = check_sla_breaches()
        self.stdout.write(self.style.SUCCESS(f'{count} newly breached ticket(s).'))
