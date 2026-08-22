from django.core.management.base import BaseCommand
from marketplace.services import check_and_apply_delays


class Command(BaseCommand):
    help = 'Scans active orders for missed deadlines, marks overdue projects as delayed, applies penalties, and notifies administrators.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Running Hirevo automatic delay detection...'))
        delayed_count = check_and_apply_delays()
        if delayed_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully processed {delayed_count} overdue order(s). Penalties recorded and notifications sent.')
            )
        else:
            self.stdout.write(self.style.SUCCESS('All active orders are on schedule. No overdue projects detected.'))
